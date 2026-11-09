"""Lifecycle, caching, batching, and the public math typesetter."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable
from contextlib import suppress
from dataclasses import dataclass
from hashlib import sha256
from importlib import resources
import json
import math
import os
from pathlib import Path
from threading import Lock, RLock
from time import monotonic
from types import TracebackType
from typing import Literal, Self

from takumi_py.math._process import ProcessRuntime
from takumi_py.math._validation import validate_tex_nesting_depth
from takumi_py.math.errors import (
    MathBatchError,
    MathError,
    MathLimitError,
    MathRuntimeError,
    MathRuntimeUnavailableError,
    MathValidationError,
)
from takumi_py.math.models import MathLimits, MathOptions, MathSvg

__all__ = ["MathTypesetter"]

MathExtension = Literal["mhchem"]
_SUPPORTED_EXTENSIONS = frozenset(("mhchem",))
_BUNDLE_FILE = "mathjax.bundle.js"
_MANIFEST_FILE = "manifest.json"
_RUNTIME_PACKAGE = "mini-racer"
_RUNTIME_VERSION = "0.14.1"

CacheKey = tuple[str, bool, float, float, str | None, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class _Bundle:
    path: Path
    sha256: str


class MathTypesetter:
    """Typeset TeX in an isolated worker and cache immutable SVG values.

    Construction validates the packaged bundle and manifest. The optional
    Python/JavaScript runtime is started lazily on the first uncached formula;
    no network, Node.js, or browser is used.
    """

    def __init__(
        self,
        *,
        limits: MathLimits | None = None,
        cache: bool = True,
        extensions: Iterable[MathExtension] = (),
    ) -> None:
        if limits is not None and not isinstance(limits, MathLimits):
            raise TypeError("limits must be a MathLimits value or None")
        if not isinstance(cache, bool):
            raise TypeError("cache must be a boolean")
        self._limits = MathLimits() if limits is None else limits
        self._cache_enabled = cache
        self._extensions = _normalize_extensions(extensions)
        self._bundle = _load_bundle()
        self._runtime: ProcessRuntime | None = None
        self._transaction = RLock()
        self._state = Lock()
        self._cache_lock = Lock()
        self._cache: OrderedDict[CacheKey, MathSvg] = OrderedDict()
        self._cache_size = 0
        self._closed = False

    @property
    def extensions(self) -> tuple[str, ...]:
        """Return the fixed extensions enabled for this instance."""
        return self._extensions

    def typeset(self, tex: str, *, options: MathOptions | None = None) -> MathSvg:
        """Typeset one expression without Markdown delimiters."""
        resolved = _normalize_options(options)
        self._validate_tex(tex)
        key = self._cache_key(tex, resolved)
        timeout_sec = self._limits.timeout_ms / 1000
        deadline = monotonic() + timeout_sec
        if not self._transaction.acquire(timeout=timeout_sec):
            raise MathLimitError("math typesetter exceeded its execution deadline")
        try:
            self._ensure_open()
            cached = self._cache_get(key)
            if cached is not None:
                return cached
            try:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise MathLimitError(
                        "math typesetter exceeded its execution deadline"
                    )
                result = self._typeset_uncached(
                    tex,
                    resolved,
                    timeout_sec=remaining,
                )
            except MathLimitError:
                raise
            except BaseException:
                self._discard_after_failure()
                raise
            self._cache_put(key, result)
            return result
        finally:
            self._transaction.release()

    def typeset_many(
        self,
        expressions: Iterable[str],
        *,
        options: MathOptions | None = None,
    ) -> tuple[MathSvg, ...]:
        """Typeset expressions in order, deduplicating identical requests."""
        if isinstance(expressions, (str, bytes)):
            raise TypeError("expressions must be an iterable of TeX strings")
        self._ensure_open()
        snapshot: list[object] = []
        for expression in expressions:
            if len(snapshot) >= self._limits.max_batch_size:
                raise MathLimitError(
                    "expression batch exceeds the configured max_batch_size"
                )
            snapshot.append(expression)
        resolved = _normalize_options(options)
        results: list[MathSvg] = []
        by_key: dict[CacheKey, MathSvg] = {}
        for index, tex in enumerate(snapshot):
            try:
                self._ensure_open()
                if not isinstance(tex, str):
                    raise MathValidationError("tex must be a string")
                self._validate_tex(tex)
                key = self._cache_key(tex, resolved)
                formula = by_key.get(key)
                if formula is None:
                    formula = self.typeset(tex, options=resolved)
                    by_key[key] = formula
                results.append(formula)
            except MathError as error:
                if isinstance(error, MathBatchError):
                    raise
                raise MathBatchError(index, error) from error
        return tuple(results)

    def close(self) -> None:
        """Cancel an in-flight conversion and release the worker and cache."""
        with self._state:
            if self._closed:
                return
            self._closed = True
            runtime, self._runtime = self._runtime, None
        if runtime is not None:
            runtime.close()
        with self._cache_lock:
            self._cache.clear()
            self._cache_size = 0

    def __enter__(self) -> Self:
        self._ensure_open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def __del__(self) -> None:
        with suppress(Exception):
            self.close()

    def _typeset_uncached(
        self,
        tex: str,
        options: MathOptions,
        *,
        timeout_sec: float,
    ) -> MathSvg:
        runtime = self._get_runtime()
        result = runtime.typeset(
            tex,
            display=options.display,
            font_size_px=options.font_size_px,
            ex_ratio=options.ex_ratio,
            color=options.color,
            extensions=self._extensions,
            timeout_sec=timeout_sec,
            memory_limit_bytes=self._limits.memory_limit_bytes,
            max_svg_bytes=self._limits.max_svg_bytes,
        )
        svg = result.get("svg")
        width_px = result.get("width_px")
        height_px = result.get("height_px")
        depth_px = result.get("depth_px")
        if not isinstance(svg, str):
            raise MathRuntimeError("math worker returned a non-string SVG")
        data = svg.encode("utf-8")
        geometry = (
            _runtime_float("width_px", width_px),
            _runtime_float("height_px", height_px),
            _runtime_float("depth_px", depth_px),
        )
        if len(data) > self._limits.max_svg_bytes:
            raise MathLimitError("math worker SVG exceeds the output byte budget")
        try:
            return MathSvg(
                data=data,
                width_px=geometry[0],
                height_px=geometry[1],
                depth_px=geometry[2],
                display=options.display,
            )
        except MathValidationError:
            raise
        except (TypeError, ValueError) as error:
            raise MathRuntimeError(
                "math worker returned invalid SVG geometry"
            ) from error

    def _get_runtime(self) -> ProcessRuntime:
        runtime = self._runtime
        if runtime is not None:
            return runtime
        self._ensure_open()
        runtime = ProcessRuntime(str(self._bundle.path))
        with self._state:
            self._ensure_open_unlocked()
            self._runtime = runtime
        return runtime

    def _discard_after_failure(self) -> None:
        with self._state:
            runtime = self._runtime
        if runtime is not None:
            with suppress(Exception):
                runtime.reset()

    def _cache_key(self, tex: str, options: MathOptions) -> CacheKey:
        return (
            tex,
            options.display,
            options.font_size_px,
            options.ex_ratio,
            options.color,
            self._extensions,
        )

    def _cache_get(self, key: CacheKey) -> MathSvg | None:
        if not self._cache_enabled:
            return None
        with self._cache_lock:
            value = self._cache.get(key)
            if value is not None:
                self._cache.move_to_end(key)
            return value

    def _cache_put(self, key: CacheKey, value: MathSvg) -> None:
        if not self._cache_enabled or not value.data:
            return
        size = len(key[0].encode("utf-8")) + len(value.data)
        if (
            size > self._limits.cache_bytes
            or self._limits.cache_entries == 0
            or self._limits.cache_bytes == 0
        ):
            return
        with self._state, self._cache_lock:
            if self._closed:
                return
            existing = self._cache.pop(key, None)
            if existing is not None:
                self._cache_size -= len(key[0].encode("utf-8")) + len(existing.data)
            self._cache[key] = value
            self._cache_size += size
            while (
                len(self._cache) > self._limits.cache_entries
                or self._cache_size > self._limits.cache_bytes
            ):
                evicted_key, evicted = self._cache.popitem(last=False)
                self._cache_size -= len(evicted_key[0].encode("utf-8")) + len(
                    evicted.data
                )

    def _validate_tex(self, tex: object) -> None:
        if not isinstance(tex, str):
            raise MathValidationError("tex must be a string")
        if len(tex) > self._limits.max_input_bytes:
            raise MathValidationError(
                f"tex exceeds the {self._limits.max_input_bytes}-byte input limit"
            )
        if not tex.strip():
            raise MathValidationError("tex must contain a non-whitespace expression")
        try:
            encoded = tex.encode("utf-8")
        except UnicodeEncodeError as error:
            raise MathValidationError("tex must contain valid Unicode text") from error
        if len(encoded) > self._limits.max_input_bytes:
            raise MathValidationError(
                f"tex exceeds the {self._limits.max_input_bytes}-byte input limit"
            )
        if any(
            (ord(char) < 0x20 and char not in "\t\n\r") or ord(char) == 0x7F
            for char in tex
        ):
            raise MathValidationError("tex contains a forbidden control character")
        validate_tex_nesting_depth(tex, self._limits.max_nesting_depth)

    def _ensure_open(self) -> None:
        with self._state:
            self._ensure_open_unlocked()

    def _ensure_open_unlocked(self) -> None:
        if self._closed:
            raise MathRuntimeError("math typesetter is closed")


def _normalize_options(options: MathOptions | None) -> MathOptions:
    if options is None:
        return MathOptions()
    if not isinstance(options, MathOptions):
        raise TypeError("options must be a MathOptions value or None")
    return options


def _normalize_extensions(extensions: Iterable[MathExtension]) -> tuple[str, ...]:
    if isinstance(extensions, (str, bytes)):
        raise TypeError("extensions must be an iterable of extension names")
    unique: list[str] = []
    for extension in extensions:
        if extension not in _SUPPORTED_EXTENSIONS:
            raise ValueError(f"unsupported math extension: {extension!r}")
        if extension not in unique:
            unique.append(extension)
    return tuple(unique)


def _load_bundle() -> _Bundle:
    try:
        root = resources.files("takumi_py.math").joinpath("assets")
        manifest_source = root.joinpath(_MANIFEST_FILE)
        bundle_source = root.joinpath(_BUNDLE_FILE)
        if not isinstance(bundle_source, os.PathLike):
            raise MathRuntimeUnavailableError(
                "the packaged math bundle is not available as a worker-accessible file"
            )
        bundle_path = Path(os.fspath(bundle_source))
        manifest = json.loads(manifest_source.read_bytes())
        data = bundle_path.read_bytes()
    except MathRuntimeUnavailableError:
        raise
    except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError) as error:
        raise MathRuntimeUnavailableError(
            "the packaged math bundle or manifest is unavailable"
        ) from error

    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise MathRuntimeUnavailableError("the packaged math manifest is invalid")
    bundle_metadata = manifest.get("bundle")
    runtime = manifest.get("runtime")
    if not isinstance(bundle_metadata, dict) or not isinstance(runtime, dict):
        raise MathRuntimeUnavailableError("the packaged math manifest is incomplete")
    digest = sha256(data).hexdigest()
    if (
        bundle_metadata.get("file") != _BUNDLE_FILE
        or bundle_metadata.get("bytes") != len(data)
        or bundle_metadata.get("sha256") != digest
    ):
        raise MathRuntimeUnavailableError(
            "the packaged math bundle does not match its manifest"
        )
    if (
        runtime.get("package") != _RUNTIME_PACKAGE
        or runtime.get("version") != _RUNTIME_VERSION
    ):
        raise MathRuntimeUnavailableError(
            "the packaged math manifest has an unsupported runtime contract"
        )
    return _Bundle(path=bundle_path, sha256=digest)


def _runtime_float(name: str, value: object) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or abs(value) > 3.4028234663852886e38
    ):
        raise MathRuntimeError(f"math worker returned invalid {name}")
    return float(value)
