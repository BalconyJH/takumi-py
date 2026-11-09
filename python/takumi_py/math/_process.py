"""A bounded, synchronous JSON transport to the optional Python math worker."""

from __future__ import annotations

from contextlib import suppress
import json
import math
import os
import subprocess
import sys
from threading import Condition, Lock, RLock, Thread
from time import monotonic
from typing import Any
from weakref import WeakKeyDictionary, WeakSet

from takumi_py.math.errors import (
    MathError,
    MathLimitError,
    MathRuntimeError,
    MathRuntimeUnavailableError,
    MathSyntaxError,
)

_ERROR_TYPES: dict[str, type[MathError]] = {
    "syntax": MathSyntaxError,
    "limit": MathLimitError,
    "runtime": MathRuntimeError,
    "unavailable": MathRuntimeUnavailableError,
}
_STOP_GUARD = Lock()
_STOP_LOCKS: WeakKeyDictionary[subprocess.Popen[bytes], Lock] = WeakKeyDictionary()
_STOPPED: WeakSet[subprocess.Popen[bytes]] = WeakSet()


class _StartAttempt:
    def __init__(self) -> None:
        self._condition = Condition()
        self._process: subprocess.Popen[bytes] | None = None
        self._error: BaseException | None = None
        self._done = False
        self._cancelled = False
        self._launch_finished = False

    def complete(self, process: subprocess.Popen[bytes]) -> None:
        with self._condition:
            rejected = self._cancelled
            if not rejected:
                self._process = process
                self._done = True
            self._condition.notify_all()
        if rejected:
            _stop(process)

    def fail(self, error: BaseException) -> None:
        with self._condition:
            if not self._cancelled:
                self._error = error
                self._done = True
            self._condition.notify_all()

    def wait(
        self, deadline: float
    ) -> tuple[str, subprocess.Popen[bytes] | None, BaseException | None]:
        with self._condition:
            while not self._done and not self._cancelled:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    return "timeout", None, None
                self._condition.wait(remaining)
            if self._cancelled:
                return "cancelled", None, None
            process, self._process = self._process, None
            return "ready", process, self._error

    def cancel(self) -> subprocess.Popen[bytes] | None:
        with self._condition:
            self._cancelled = True
            process, self._process = self._process, None
            self._condition.notify_all()
            return process

    def finish_launch(self) -> None:
        with self._condition:
            self._launch_finished = True
            self._condition.notify_all()

    @property
    def launch_finished(self) -> bool:
        with self._condition:
            return self._launch_finished

    @property
    def cancelled(self) -> bool:
        with self._condition:
            return self._cancelled


class ProcessRuntime:
    """Own one restartable worker; never expose its JS context to callers.

    The transaction lock serializes callers. A separate state lock lets close
    terminate an in-flight worker without waiting for the transaction deadline.
    At most one process-creation attempt can be outstanding. Its daemon helper
    cannot be force-killed if the platform blocks in ``Popen``, but a late
    process is reclaimed when start finishes and retries share the same attempt.
    Pipe reads and writes use a separate thread so blocked I/O and runaway
    JavaScript cannot hold the state lock past the parent deadline.
    """

    def __init__(
        self,
        bundle_path: str,
        worker_module: str = "takumi_py.math._worker",
        executable: str = sys.executable,
    ) -> None:
        self._bundle_path = bundle_path
        self._worker_module = worker_module
        self._executable = executable
        self._transaction = RLock()
        self._state = Lock()
        self._process: subprocess.Popen[bytes] | None = None
        self._starting: _StartAttempt | None = None
        self._closed = False

    def typeset(
        self,
        tex: str,
        *,
        display: bool,
        font_size_px: float,
        ex_ratio: float,
        color: str | None,
        extensions: tuple[str, ...],
        timeout_sec: float,
        memory_limit_bytes: int,
        max_svg_bytes: int,
    ) -> dict[str, object]:
        """Execute one request under a wall-clock deadline, including startup."""
        if not math.isfinite(timeout_sec) or timeout_sec <= 0:
            raise MathLimitError("timeout_sec must be finite and positive")
        if max_svg_bytes <= 0:
            raise MathLimitError("max_svg_bytes must be positive")
        deadline = monotonic() + timeout_sec
        if not self._transaction.acquire(timeout=timeout_sec):
            raise MathLimitError(
                "math worker request timed out waiting for another call"
            )
        process = None
        reader = None
        try:
            with self._state:
                if self._closed:
                    raise MathRuntimeError("math runtime is closed")
            process = self._get_process(deadline)
            request = {
                "op": "typeset",
                "bundle_path": self._bundle_path,
                "tex": tex,
                "display": display,
                "font_size_px": font_size_px,
                "ex_ratio": ex_ratio,
                "color": color,
                "extensions": list(extensions),
                "timeout_sec": timeout_sec,
                "memory_limit_bytes": memory_limit_bytes,
                "max_svg_bytes": max_svg_bytes,
            }
            payload = (
                json.dumps(request, ensure_ascii=True, allow_nan=False) + "\n"
            ).encode()
            replies: list[bytes | Exception] = []
            max_reply_bytes = max_svg_bytes * 6 + 65_536
            reader = Thread(
                target=_exchange,
                args=(process, payload, max_reply_bytes, replies),
                name="takumi-math-transport",
                daemon=True,
            )
            reader.start()
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise MathLimitError("math worker exceeded its execution deadline")
            reader.join(timeout=remaining)
            if reader.is_alive() or not replies:
                raise MathLimitError("math worker exceeded its execution deadline")
            response = replies[0]
            if isinstance(response, Exception):
                raise MathRuntimeError("math worker communication failed") from response
            if not response or not response.endswith(b"\n"):
                raise MathRuntimeError(
                    "math worker exited or exceeded its response budget"
                )
            try:
                reply: Any = json.loads(response)
            except (ValueError, UnicodeError) as error:
                raise MathRuntimeError("math worker returned invalid JSON") from error
            if not isinstance(reply, dict) or type(reply.get("ok")) is not bool:
                raise MathRuntimeError("math worker returned an invalid response")
            if reply["ok"] is False:
                kind = reply.get("kind")
                error_type = _ERROR_TYPES.get(kind) if isinstance(kind, str) else None
                message = reply.get("message")
                if error_type is None or not isinstance(message, str):
                    raise MathRuntimeError("math worker returned an invalid error")
                raise error_type(message[:4096])
            result = reply.get("result")
            if not isinstance(result, dict) or not isinstance(result.get("svg"), str):
                raise MathRuntimeError("math worker returned an invalid formula")
            if len(result["svg"].encode("utf-8")) > max_svg_bytes:
                raise MathLimitError("math worker SVG exceeds the output byte budget")
            for name in ("width_px", "height_px", "depth_px"):
                value = result.get(name)
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not -3.4028234663852886e38 <= value <= 3.4028234663852886e38
                    or not math.isfinite(value)
                ):
                    raise MathRuntimeError("math worker returned invalid geometry")
            return result
        except BaseException:
            if process is not None:
                self._discard(process)
            raise
        finally:
            if reader is not None:
                reader.join(timeout=0.25)
            self._transaction.release()

    def close(self) -> None:
        """Reject future calls and terminate any in-flight worker."""
        with self._state:
            if self._closed:
                return
            self._closed = True
            process, self._process = self._process, None
            starting, self._starting = self._starting, None
        if starting is not None:
            late_process = starting.cancel()
            if late_process is not None:
                _stop(late_process)
        if process is not None:
            _stop(process)

    def reset(self) -> None:
        """Discard a worker after validation of its result fails."""
        with self._state:
            process, self._process = self._process, None
            starting = self._starting
        if starting is not None:
            late_process = self._abandon_start(starting)
            if late_process is not None:
                _stop(late_process)
        if process is not None:
            _stop(process)

    def _get_process(self, deadline: float) -> subprocess.Popen[bytes]:
        start_attempt = False
        with self._state:
            if self._closed:
                raise MathRuntimeError("math runtime is closed")
            if self._process is not None:
                return self._process
            attempt = self._starting
            if attempt is None:
                attempt = _StartAttempt()
                self._starting = attempt
                start_attempt = True

        if start_attempt:
            starter = Thread(
                target=self._launch_start,
                args=(attempt,),
                name="takumi-math-start",
                daemon=True,
            )
            try:
                starter.start()
            except BaseException as error:
                attempt.finish_launch()
                late_process = self._abandon_start(attempt)
                if late_process is not None:
                    _stop(late_process)
                raise MathRuntimeUnavailableError(
                    "could not start the Python math worker"
                ) from error

        try:
            outcome, process, error = attempt.wait(deadline)
        except BaseException:
            late_process = self._abandon_start(attempt)
            if late_process is not None:
                _stop(late_process)
            raise
        if outcome == "timeout":
            late_process = self._abandon_start(attempt)
            if late_process is not None:
                _stop(late_process)
            raise MathLimitError("math worker exceeded its execution deadline")
        if outcome == "cancelled":
            with self._state:
                closed = self._closed
            if closed:
                raise MathRuntimeError("math runtime is closed")
            if not attempt.launch_finished:
                raise MathLimitError("math worker startup is still being cancelled")
            raise MathRuntimeError("math worker startup was cancelled")
        if error is not None:
            with self._state:
                if self._starting is attempt:
                    self._starting = None
            raise error
        if process is None:
            raise MathRuntimeError("math worker startup returned no process")
        try:
            with self._state:
                if self._closed or self._starting is not attempt:
                    accepted = False
                else:
                    self._starting = None
                    self._process = process
                    accepted = True
            if not accepted:
                raise MathRuntimeError("math runtime is closed")
            return process
        except BaseException:
            with self._state:
                if self._process is process:
                    self._process = None
            _stop(process)
            raise

    def _launch_start(self, attempt: _StartAttempt) -> None:
        try:
            try:
                process = self._start()
            except BaseException as error:
                attempt.fail(error)
                return
            attempt.complete(process)
        finally:
            attempt.finish_launch()
            with self._state:
                if self._starting is attempt and attempt.cancelled:
                    self._starting = None

    def _abandon_start(self, attempt: _StartAttempt) -> subprocess.Popen[bytes] | None:
        with self._state:
            process = attempt.cancel()
            if self._starting is attempt and attempt.launch_finished:
                self._starting = None
        return process

    def _start(self) -> subprocess.Popen[bytes]:
        environment = os.environ.copy()
        for name in (
            "PYTHONPATH",
            "PYTHONHOME",
            "PYTHONSTARTUP",
            "PYTHONINSPECT",
            "LD_PRELOAD",
            "DYLD_INSERT_LIBRARIES",
        ):
            environment.pop(name, None)
        try:
            return subprocess.Popen(  # noqa: S603
                [self._executable, "-I", "-u", "-m", self._worker_module],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=environment,
                creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
            )
        except OSError as error:
            raise MathRuntimeUnavailableError(
                "could not start the Python math worker"
            ) from error

    def _discard(self, process: subprocess.Popen[bytes]) -> None:
        with self._state:
            if self._process is not process:
                return
            self._process = None
        _stop(process)

    def __del__(self) -> None:
        # Best effort only. Applications use close()/the typesetter context manager.
        with suppress(Exception):
            self.close()


def _exchange(
    process: subprocess.Popen[bytes],
    payload: bytes,
    max_reply_bytes: int,
    replies: list[bytes | Exception],
) -> None:
    try:
        if process.stdin is None or process.stdout is None:
            raise OSError("math worker pipes are not available")
        process.stdin.write(payload)
        process.stdin.flush()
        replies.append(process.stdout.readline(max_reply_bytes + 1))
    except Exception as error:
        replies.append(error)


def _stop(process: subprocess.Popen[bytes]) -> None:
    with _STOP_GUARD:
        lock = _STOP_LOCKS.setdefault(process, Lock())
    with lock:
        with _STOP_GUARD:
            if process in _STOPPED:
                return
        try:
            if process.poll() is None:
                with suppress(ProcessLookupError):
                    process.terminate()
                try:
                    process.wait(timeout=0.25)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1.0)
        finally:
            for stream in (process.stdin, process.stdout):
                if stream is not None:
                    with suppress(OSError, ValueError):
                        stream.close()
            with _STOP_GUARD:
                _STOPPED.add(process)
