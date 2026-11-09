"""Isolated JSON worker for the optional MiniRacer math runtime."""

from __future__ import annotations

from contextlib import suppress
from importlib import metadata
import json
import math
import os
from pathlib import Path
import socket
import sys
from time import monotonic
from typing import Any

_MAX_ERROR_CHARS = 4_096
_NETWORK_EVENTS = frozenset(
    {
        "socket.getaddrinfo",
        "socket.gethostbyaddr",
        "socket.gethostbyname",
        "socket.getnameinfo",
        "socket.sethostname",
        "http.client.connect",
        "urllib.Request",
    }
)
_PROCESS_EVENTS = frozenset(
    {
        "os.exec",
        "os.fork",
        "os.posix_spawn",
        "os.spawn",
        "os.system",
        "subprocess.Popen",
    }
)
_INTERNET_FAMILIES = frozenset((socket.AF_INET, socket.AF_INET6))


class _RuntimeState:
    runtime: Any = None
    typeset_function: Any = None
    bundle_path: Path | None = None


_STATE = _RuntimeState()


class _GuardState:
    installed = False


_GUARD_STATE = _GuardState()


def install_worker_guard() -> None:
    """Deny worker network access and child-process creation for smoke tests."""
    if _GUARD_STATE.installed:
        return

    def audit(event: str, args: tuple[object, ...]) -> None:
        if event in _PROCESS_EVENTS:
            raise RuntimeError(f"math worker denied audit event: {event}")
        if event in {"socket.bind", "socket.connect"} and len(args) >= 2:
            family = getattr(args[0], "family", None)
            address = args[1]
            if family in _INTERNET_FAMILIES and not _is_loopback_address(address):
                raise RuntimeError(f"math worker denied audit event: {event}")
            return
        if event in _NETWORK_EVENTS:
            raise RuntimeError(f"math worker denied audit event: {event}")

    sys.addaudithook(audit)
    _GUARD_STATE.installed = True


if os.environ.get("TAKUMI_PY_MATH_SMOKE") == "1":
    install_worker_guard()


def main() -> int:
    for raw_line in sys.stdin.buffer:
        try:
            request = json.loads(raw_line)
            if not isinstance(request, dict):
                raise _WorkerFailure("runtime", "math worker request must be an object")
            operation = request.get("op")
            if operation == "close":
                _close_runtime()
                _write_response({"ok": True, "result": {"closed": True}})
                return 0
            if operation != "typeset":
                raise _WorkerFailure("runtime", "unsupported math worker operation")
            result = _typeset(request)
            _write_response({"ok": True, "result": result})
        except _WorkerFailure as error:
            _close_runtime()
            _write_response(
                {
                    "ok": False,
                    "kind": error.kind,
                    "message": _message(error),
                }
            )
        except BaseException as error:
            _close_runtime()
            _write_response(
                {
                    "ok": False,
                    "kind": "runtime",
                    "message": _message(error),
                }
            )
    _close_runtime()
    return 0


def _typeset(request: dict[str, object]) -> dict[str, object]:
    timeout_sec = _positive_float(request.get("timeout_sec"), "timeout_sec")
    memory_limit_bytes = _positive_int(
        request.get("memory_limit_bytes"),
        "memory_limit_bytes",
    )
    max_svg_bytes = _positive_int(request.get("max_svg_bytes"), "max_svg_bytes")
    bundle_path_value = request.get("bundle_path")
    tex = request.get("tex")
    display = request.get("display")
    color = request.get("color")
    extensions = request.get("extensions")
    if not isinstance(bundle_path_value, str) or not isinstance(tex, str):
        raise _WorkerFailure("runtime", "math worker received invalid text inputs")
    if not isinstance(display, bool):
        raise _WorkerFailure("runtime", "math worker received invalid display mode")
    if color is not None and not isinstance(color, str):
        raise _WorkerFailure("runtime", "math worker received an invalid color")
    if (
        not isinstance(extensions, list)
        or any(not isinstance(item, str) for item in extensions)
        or any(item != "mhchem" for item in extensions)
    ):
        raise _WorkerFailure("runtime", "math worker received invalid extensions")
    font_size_px = _positive_float(request.get("font_size_px"), "font_size_px")
    ex_ratio = _positive_float(request.get("ex_ratio"), "ex_ratio")

    deadline = monotonic() + timeout_sec
    _ensure_runtime(bundle_path_value, memory_limit_bytes, _remaining(deadline))
    runtime = _STATE.runtime
    if runtime is None or _STATE.typeset_function is None:
        raise _WorkerFailure("runtime", "math runtime was not initialized")

    try:
        promise = _STATE.typeset_function(
            tex,
            display,
            font_size_px,
            ex_ratio,
            color,
            "mhchem" in extensions,
            timeout_sec=_remaining(deadline),
        )
        result = promise.get(timeout=_remaining(deadline))
    except BaseException as error:
        raise _classify_runtime_error(error, runtime) from error

    try:
        svg = result["svg"]
        width_px = result["widthPx"]
        height_px = result["heightPx"]
        depth_px = result["depthPx"]
    except (KeyError, TypeError) as error:
        raise _WorkerFailure(
            "runtime", "math runtime returned invalid values"
        ) from error
    if not isinstance(svg, str):
        raise _WorkerFailure("runtime", "math runtime returned a non-string SVG")
    if len(svg.encode("utf-8")) > max_svg_bytes:
        raise _WorkerFailure("limit", "math SVG exceeds the output byte budget")
    geometry: list[float] = []
    for name, value in (
        ("width_px", width_px),
        ("height_px", height_px),
        ("depth_px", depth_px),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise _WorkerFailure(
                "runtime",
                f"math runtime returned invalid {name}",
            )
        if abs(value) > 3.4028234663852886e38:
            raise _WorkerFailure(
                "limit",
                f"math geometry {name} exceeds the f32 output range",
            )
        if name in {"width_px", "height_px"} and value <= 0:
            raise _WorkerFailure(
                "runtime",
                f"math runtime returned non-positive {name}",
            )
        geometry.append(float(value))
    return {
        "svg": svg,
        "width_px": geometry[0],
        "height_px": geometry[1],
        "depth_px": geometry[2],
    }


def _ensure_runtime(
    bundle_path_value: str,
    memory_limit_bytes: int,
    timeout_sec: float,
) -> None:
    bundle_path = Path(bundle_path_value)
    if _STATE.runtime is not None and bundle_path == _STATE.bundle_path:
        _STATE.runtime.set_hard_memory_limit(memory_limit_bytes)
        return
    _close_runtime()
    try:
        installed_version = metadata.version("mini-racer")
    except metadata.PackageNotFoundError as error:
        raise _WorkerFailure(
            "unavailable",
            'math rendering requires the optional "mini-racer==0.14.1" dependency',
        ) from error
    if installed_version != "0.14.1":
        raise _WorkerFailure(
            "unavailable",
            "math rendering requires mini-racer==0.14.1",
        )
    try:
        from py_mini_racer import MiniRacer
    except ImportError as error:
        raise _WorkerFailure(
            "unavailable",
            "the installed mini-racer package cannot be imported",
        ) from error
    try:
        bundle = bundle_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise _WorkerFailure(
            "unavailable",
            "the packaged math bundle is unavailable",
        ) from error
    runtime: Any = None
    try:
        runtime = MiniRacer()
        runtime.set_hard_memory_limit(memory_limit_bytes)
        runtime.eval(bundle, timeout_sec=timeout_sec)
        typeset = runtime.eval(
            "TakumiMathJax.typeset",
            timeout_sec=_remaining(deadline=monotonic() + timeout_sec),
        )
    except BaseException as error:
        with suppress(Exception):
            runtime.close()
        raise _classify_runtime_error(error, runtime) from error
    _STATE.runtime = runtime
    _STATE.typeset_function = typeset
    _STATE.bundle_path = bundle_path


def _classify_runtime_error(
    error: BaseException, runtime: Any = None
) -> _WorkerFailure:
    if runtime is not None:
        with suppress(Exception):
            if runtime.was_hard_memory_limit_reached():
                return _WorkerFailure("limit", "JavaScript memory limit reached")
    try:
        from py_mini_racer import (
            JSEvalException,
            JSOOMException,
            JSPromiseError,
            JSTimeoutException,
        )
    except ImportError:
        return _WorkerFailure("unavailable", "mini-racer is not importable")
    if isinstance(error, (JSTimeoutException, JSOOMException)):
        return _WorkerFailure("limit", _message(error))
    if isinstance(error, JSPromiseError):
        reason = error.reason
        if isinstance(reason, str):
            error_id = reason.split(":", 1)[0].strip()
            if error_id == "GeometryLimit":
                return _WorkerFailure("limit", reason)
            if error_id and error_id not in {
                "Error",
                "MathJaxError",
                "RangeError",
                "TypeError",
            }:
                return _WorkerFailure("syntax", reason)
            return _WorkerFailure("runtime", reason)
        return _WorkerFailure("runtime", _message(error))
    if isinstance(error, JSEvalException):
        return _WorkerFailure("runtime", _message(error))
    return _WorkerFailure("runtime", _message(error))


def _positive_float(value: object, name: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise _WorkerFailure("runtime", f"math worker received invalid {name}")
    return float(value)


def _positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise _WorkerFailure("runtime", f"math worker received invalid {name}")
    return value


def _remaining(deadline: float) -> float:
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise _WorkerFailure("limit", "math runtime exceeded its execution deadline")
    return remaining


def _close_runtime() -> None:
    runtime, _STATE.runtime = _STATE.runtime, None
    _STATE.typeset_function = None
    _STATE.bundle_path = None
    if runtime is not None:
        with suppress(Exception):
            runtime.close()


def _write_response(response: dict[str, object]) -> None:
    try:
        payload = json.dumps(
            response,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        payload = json.dumps(
            {
                "ok": False,
                "kind": "runtime",
                "message": _message(error),
            },
            separators=(",", ":"),
        )
    sys.stdout.write(payload + "\n")
    sys.stdout.flush()


def _message(error: BaseException) -> str:
    text = str(error).strip()
    if not text:
        text = error.__class__.__name__
    return text[:_MAX_ERROR_CHARS]


def _is_loopback_address(address: object) -> bool:
    if not isinstance(address, tuple) or not address:
        return False
    host = address[0]
    return isinstance(host, str) and host.lower() in {"127.0.0.1", "::1"}


class _WorkerFailure(Exception):
    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


if __name__ == "__main__":
    raise SystemExit(main())
