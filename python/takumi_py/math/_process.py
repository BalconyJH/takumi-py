"""A bounded, synchronous JSON transport to the optional Python math worker."""

from __future__ import annotations

from contextlib import suppress
import json
import math
import os
from queue import Empty, Queue
import subprocess
import sys
from threading import Lock, RLock, Thread
from time import monotonic
from typing import Any

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


class ProcessRuntime:
    """Own one restartable worker; never expose its JS context to callers.

    The transaction lock serializes callers. A separate state lock lets close
    terminate an in-flight worker without waiting for the transaction deadline.
    Pipe reads and writes happen in a short-lived reader thread so a blocked
    pipe or a runaway JavaScript microtask cannot bypass the parent deadline.
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
                if self._process is None:
                    self._process = self._start()
                process = self._process
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
            replies: Queue[bytes | Exception] = Queue(maxsize=1)
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
            try:
                response = replies.get(timeout=remaining)
            except Empty:
                raise MathLimitError(
                    "math worker exceeded its execution deadline"
                ) from None
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
        if process is not None:
            _stop(process)

    def reset(self) -> None:
        """Discard a worker after validation of its result fails."""
        with self._state:
            process, self._process = self._process, None
        if process is not None:
            _stop(process)

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
    replies: Queue[bytes | Exception],
) -> None:
    try:
        if process.stdin is None or process.stdout is None:
            raise OSError("math worker pipes are not available")
        process.stdin.write(payload)
        process.stdin.flush()
        replies.put(process.stdout.readline(max_reply_bytes + 1))
    except Exception as error:
        replies.put(error)


def _stop(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        with suppress(ProcessLookupError):
            process.terminate()
        try:
            process.wait(timeout=0.25)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=1.0)
    for stream in (process.stdin, process.stdout):
        if stream is not None:
            stream.close()
