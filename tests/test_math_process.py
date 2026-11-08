from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from importlib.util import find_spec
from pathlib import Path
import subprocess
import sys
from threading import Event
from time import monotonic

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
        def _start(self) -> subprocess.Popen[bytes]:
            return subprocess.Popen(  # noqa: S603
                [sys.executable, "-I", "-u", str(worker)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )

    instance = FaultyRuntime("unused")
    yield instance
    instance.close()


def test_worker_is_reused_only_after_success(runtime: ProcessRuntime) -> None:
    first = request(runtime, "ok")
    second = request(runtime, "ok")
    assert first["pid"] == second["pid"]


@pytest.mark.parametrize("fault", ["exit", "invalid", "large", "syntax"])
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
