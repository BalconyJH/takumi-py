from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from importlib.util import find_spec
from pathlib import Path
import subprocess
import sys
from threading import Event
from time import monotonic, sleep
from typing import Any, Callable, cast
from unittest.mock import Mock

import pytest

from takumi_py.math._process import ProcessRuntime
from takumi_py.math.errors import MathLimitError, MathRuntimeError, MathSyntaxError


def request(
    runtime: ProcessRuntime, tex: str, timeout: float = 2.0
) -> dict[str, object]:
    return runtime.typeset(
        tex,
        display=False,
        font_size_px=20,
        ex_ratio=0.5,
        color=None,
        extensions=(),
        timeout_sec=timeout,
        memory_limit_bytes=128 * 1024 * 1024,
        max_svg_bytes=1024,
    )


@pytest.fixture
def runtime(tmp_path: Path) -> Iterator[ProcessRuntime]:
    # Reuse the real process/pipe transport with a deliberately faulty worker.
    worker = tmp_path / "faulty_worker.py"
    worker.write_text(
        """
import json
import os
import sys
import time

for line in sys.stdin:
    request = json.loads(line)
    tex = request['tex']
    if tex == 'hang':
        while True:
            pass
    if tex == 'microtask':
        from py_mini_racer import MiniRacer
        context = MiniRacer()
        promise = context.eval('Promise.resolve().then(() => {while (true) {}})', timeout_sec=0.1)
        promise.get(timeout=0.1)
    if tex == 'exit':
        sys.exit(1)
    if tex == 'crash':
        os._exit(1)
    if tex == 'invalid':
        print('not-json', flush=True)
    elif tex == 'large':
        print('x' * 100000, flush=True)
    elif tex == 'syntax':
        print(json.dumps({'ok': False, 'kind': 'syntax', 'message': 'bad TeX'}), flush=True)
    else:
        print(json.dumps({'ok': True, 'result': {
            'svg': '<svg/>', 'width_px': 20, 'height_px': 10, 'depth_px': 2,
            'pid': os.getpid(),
        }}), flush=True)
""",
        encoding="utf-8",
    )

    class FaultyRuntime(ProcessRuntime):
        start_gate: Event | None = None
        ready_gate: Event | None = None
        start_entered = Event()
        ready_entered = Event()
        spawned: list[subprocess.Popen[bytes]]
        start_calls: int

        def __init__(self, bundle_path: str) -> None:
            super().__init__(bundle_path)
            self.spawned = []
            self.start_calls = 0

        def _start(self) -> subprocess.Popen[bytes]:
            self.start_calls += 1
            self.start_entered.set()
            if self.start_gate is not None and not self.start_gate.wait(timeout=5):
                raise TimeoutError("test start gate was not released")
            process = subprocess.Popen(  # noqa: S603
                [sys.executable, "-I", "-u", str(worker)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            self.spawned.append(process)
            self.ready_entered.set()
            if self.ready_gate is not None and not self.ready_gate.wait(timeout=5):
                raise TimeoutError("test ready gate was not released")
            return process

    instance = FaultyRuntime("unused")
    yield instance
    instance.close()


def test_worker_is_reused_only_after_success(runtime: ProcessRuntime) -> None:
    first = request(runtime, "ok")
    second = request(runtime, "ok")
    assert first["pid"] == second["pid"]


@pytest.mark.parametrize("fault", ["exit", "crash", "invalid", "large", "syntax"])
def test_worker_failure_discards_process(runtime: ProcessRuntime, fault: str) -> None:
    first = request(runtime, "ok")
    error = MathSyntaxError if fault == "syntax" else MathRuntimeError
    with pytest.raises(error):
        request(runtime, fault)
    assert request(runtime, "ok")["pid"] != first["pid"]


def test_worker_cpu_timeout_is_hard_and_recoverable(runtime: ProcessRuntime) -> None:
    request(runtime, "ok")
    started = monotonic()
    with pytest.raises(MathLimitError, match="deadline"):
        request(runtime, "hang", timeout=0.1)
    assert monotonic() - started < 2
    assert request(runtime, "ok")["width_px"] == 20


@pytest.mark.skipif(
    find_spec("py_mini_racer") is None, reason="math extra not installed"
)
def test_worker_recovers_from_runaway_javascript_microtask(
    runtime: ProcessRuntime,
) -> None:
    request(runtime, "ok")
    started = monotonic()
    with pytest.raises(MathLimitError, match="deadline"):
        request(runtime, "microtask", timeout=0.75)
    assert monotonic() - started < 3
    assert request(runtime, "ok")["width_px"] == 20


def test_close_interrupts_inflight_worker(runtime: ProcessRuntime) -> None:
    request(runtime, "ok")
    ready = Event()
    original_start = runtime._process

    def call() -> None:
        ready.set()
        request(runtime, "hang", timeout=10)

    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(call)
        assert ready.wait(timeout=1)
        started = monotonic()
        runtime.close()
        with pytest.raises(MathRuntimeError):
            result.result(timeout=2)
        assert monotonic() - started < 2
    assert original_start is not None and original_start.poll() is not None
    runtime.close()
    with pytest.raises(MathRuntimeError, match="closed"):
        request(runtime, "ok")


def test_deadlines_share_and_cancel_one_delayed_start_attempt(
    runtime: ProcessRuntime,
) -> None:
    instance = cast(Any, runtime)
    instance.start_gate = Event()
    try:
        for _ in range(2):
            started = monotonic()
            with pytest.raises(MathLimitError, match=r"deadline|being cancelled"):
                request(instance, "ok", timeout=0.1)
            assert monotonic() - started < 1

        assert instance.start_entered.wait(timeout=1)
        assert instance.start_calls == 1

        instance.start_gate.set()
        _wait_until(lambda: bool(instance.spawned), timeout=2)
        late_process = instance.spawned[0]
        _wait_until(lambda: late_process.poll() is not None, timeout=2)
        _wait_until(lambda: instance._starting is None, timeout=2)

        assert request(instance, "ok")["width_px"] == 20
        assert instance.start_calls == 2
    finally:
        instance.start_gate.set()


def test_close_interrupts_delayed_start_and_reclaims_the_late_process(
    runtime: ProcessRuntime,
) -> None:
    instance = cast(Any, runtime)
    instance.start_gate = Event()
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(request, instance, "ok", 10)
        assert instance.start_entered.wait(timeout=1)
        started = monotonic()
        instance.close()
        with pytest.raises(MathRuntimeError, match="closed"):
            result.result(timeout=2)
        assert monotonic() - started < 2

        instance.start_gate.set()
        _wait_until(lambda: bool(instance.spawned), timeout=2)
        late_process = instance.spawned[0]
        _wait_until(lambda: late_process.poll() is not None, timeout=2)


def test_close_during_ready_start_reclaims_the_unaccepted_process(
    runtime: ProcessRuntime,
) -> None:
    instance = cast(Any, runtime)
    instance.ready_gate = Event()
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(request, instance, "ok", 10)
        assert instance.ready_entered.wait(timeout=1)
        started = monotonic()
        instance.close()
        with pytest.raises(MathRuntimeError, match="closed"):
            result.result(timeout=2)
        assert monotonic() - started < 2

        instance.ready_gate.set()
        _wait_until(lambda: bool(instance.spawned), timeout=2)
        late_process = instance.spawned[0]
        _wait_until(lambda: late_process.poll() is not None, timeout=2)


def test_keyboard_interrupt_abandons_a_pending_start(
    runtime: ProcessRuntime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from takumi_py.math import _process

    instance = cast(Any, runtime)
    instance.start_gate = Event()
    original_wait = _process._StartAttempt.wait

    def interrupt(_attempt: object, _deadline: float) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(_process._StartAttempt, "wait", interrupt)
    try:
        with pytest.raises(KeyboardInterrupt):
            request(instance, "ok", timeout=2)
        assert instance.start_entered.wait(timeout=1)
        assert instance._starting is not None

        monkeypatch.setattr(_process._StartAttempt, "wait", original_wait)
        with pytest.raises(MathLimitError, match="being cancelled"):
            request(instance, "ok", timeout=2)
        assert instance.start_calls == 1

        instance.start_gate.set()
        _wait_until(lambda: bool(instance.spawned), timeout=2)
        late_process = instance.spawned[0]
        _wait_until(lambda: late_process.poll() is not None, timeout=2)
        _wait_until(lambda: instance._starting is None, timeout=2)
        assert request(instance, "ok")["width_px"] == 20
        assert instance.start_calls == 2
    finally:
        instance.start_gate.set()


def test_abandon_start_cannot_leave_a_finished_attempt_as_a_tombstone(
    runtime: ProcessRuntime,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from takumi_py.math import _process

    instance = cast(Any, runtime)
    attempt = _process._StartAttempt()
    instance._starting = attempt
    original_cancel = attempt.cancel

    def cancel_then_finish_launch() -> subprocess.Popen[bytes] | None:
        result = original_cancel()
        attempt.finish_launch()
        return result

    monkeypatch.setattr(attempt, "cancel", cancel_then_finish_launch)

    assert instance._abandon_start(attempt) is None
    assert instance._starting is None


@pytest.mark.parametrize(
    ("platform", "preload", "expected_preload"),
    [
        pytest.param(
            "linux",
            "/lib/libgcompat.so.0",
            "/lib/libgcompat.so.0",
            id="linux-gcompat",
        ),
        pytest.param("linux", "/opt/libgcompat.so.0", None, id="linux-other-path"),
        pytest.param(
            "linux",
            "/lib/libgcompat.so.0:/tmp/libother.so.0 /tmp/libspace.so.0",
            None,
            id="linux-list-or-space",
        ),
        pytest.param("linux", "libgcompat.so.0", None, id="linux-relative"),
        pytest.param(
            "darwin",
            "/lib/libgcompat.so.0",
            None,
            id="darwin-gcompat-path",
        ),
        pytest.param(
            "win32",
            "/lib/libgcompat.so.0",
            None,
            id="windows-gcompat-path",
        ),
        pytest.param("linux", None, None, id="linux-absent"),
    ],
)
def test_start_scrubs_process_environment_except_linux_gcompat(
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
    preload: str | None,
    expected_preload: str | None,
) -> None:
    from takumi_py.math import _process

    if preload is None:
        monkeypatch.delenv("LD_PRELOAD", raising=False)
    else:
        monkeypatch.setenv("LD_PRELOAD", preload)
    for name in (
        "DYLD_INSERT_LIBRARIES",
        "PYTHONHOME",
        "PYTHONPATH",
        "PYTHONSTARTUP",
        "PYTHONINSPECT",
    ):
        monkeypatch.setenv(name, f"unsafe-{name.lower()}")
    monkeypatch.setenv("TAKUMI_MATH_ORDINARY_ENV", "inherited")
    monkeypatch.setattr(_process.sys, "platform", platform)
    popen = Mock()
    monkeypatch.setattr(_process.subprocess, "Popen", popen)

    ProcessRuntime("unused")._start()

    popen.assert_called_once()
    environment = popen.call_args.kwargs["env"]
    assert isinstance(environment, dict)
    if expected_preload is None:
        assert "LD_PRELOAD" not in environment
    else:
        assert environment["LD_PRELOAD"] == expected_preload
    for name in (
        "DYLD_INSERT_LIBRARIES",
        "PYTHONHOME",
        "PYTHONPATH",
        "PYTHONSTARTUP",
        "PYTHONINSPECT",
    ):
        assert name not in environment
    assert environment["TAKUMI_MATH_ORDINARY_ENV"] == "inherited"


def test_stopping_a_process_is_idempotent_under_concurrency() -> None:
    from takumi_py.math._process import _stop

    process = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(10)"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: _stop(process), range(4)))

    assert process.poll() is not None
    assert process.stdin is not None and process.stdin.closed
    assert process.stdout is not None and process.stdout.closed


def test_null_promise_reason_uses_the_runtime_memory_marker() -> None:
    pytest.importorskip("py_mini_racer")
    from py_mini_racer import JSPromiseError

    from takumi_py.math import _worker

    class MemoryLimitedRuntime:
        @staticmethod
        def was_hard_memory_limit_reached() -> bool:
            return True

    failure = _worker._classify_runtime_error(
        JSPromiseError(None),
        MemoryLimitedRuntime(),
    )

    assert failure.kind == "limit"
    assert failure.args == ("JavaScript memory limit reached",)


def test_geometry_limit_error_is_not_misclassified_as_syntax() -> None:
    pytest.importorskip("py_mini_racer")
    from py_mini_racer import JSPromiseError

    from takumi_py.math import _worker

    failure = _worker._classify_runtime_error(
        JSPromiseError("GeometryLimit: height exceeds the finite f32 range")
    )

    assert failure.kind == "limit"


def _wait_until(predicate: Callable[[], bool], *, timeout: float) -> None:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        if predicate():
            return
        sleep(0.01)
    raise AssertionError("condition was not satisfied before the test deadline")
