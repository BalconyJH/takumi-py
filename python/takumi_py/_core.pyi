from collections.abc import Sequence
from typing import Literal, TypeAlias, final, type_check_only
from typing_extensions import TypedDict

__all__ = [
    "AnimationError",
    "CompiledNode",
    "CompiledStyleSheet",
    "FontError",
    "HtmlParseError",
    "NativeRenderer",
    "NodeDecodeError",
    "NodeValidationError",
    "RenderError",
    "ResourceError",
    "StyleSheetError",
    "TakumiError",
    "UnsupportedFormatError",
    "set_glyph_cache_max_bytes",
]

class TakumiError(Exception): ...
class HtmlParseError(TakumiError): ...
class NodeValidationError(TakumiError): ...
class NodeDecodeError(TakumiError): ...
class StyleSheetError(TakumiError): ...
class RenderError(TakumiError): ...
class ResourceError(TakumiError): ...
class FontError(TakumiError): ...
class AnimationError(TakumiError): ...
class UnsupportedFormatError(TakumiError): ...

@final
class CompiledNode:
    def resource_urls(self) -> list[str]: ...

@final
class CompiledStyleSheet: ...

_ImageOutputFormat: TypeAlias = Literal["png", "jpeg", "jpg", "webp", "ico", "raw"]
_AnimationOutputFormat: TypeAlias = Literal["webp", "apng", "gif"]
_DitheringAlgorithm: TypeAlias = Literal["none", "ordered-bayer", "floyd-steinberg"]
_ImageCacheMode: TypeAlias = Literal["auto", "none"]
_ImageResourceInput: TypeAlias = tuple[str, bytes, _ImageCacheMode]
_FontResourceInput: TypeAlias = tuple[
    bytes, str | None, float | None, str | None, str | None, str | None
]
_RawAnimationFrameInput: TypeAlias = tuple[bytes, int, int, int]

def set_glyph_cache_max_bytes(max_bytes: int) -> None: ...

@type_check_only
class _MeasuredTextRunOutput(TypedDict):
    text: str
    x: float
    y: float
    width: float
    height: float

@type_check_only
class _MeasuredNodeOutput(TypedDict):
    width: float
    height: float
    transform: list[float]
    children: list[_MeasuredNodeOutput]
    runs: list[_MeasuredTextRunOutput]

@final
class NativeRenderer:
    def __new__(
        cls,
        *,
        load_default_fonts: bool = True,
        fonts: Sequence[_FontResourceInput] | None = None,
        persistent_images: Sequence[_ImageResourceInput] | None = None,
        cache_max_bytes: int | None = None,
    ) -> NativeRenderer: ...
    def compile_node_py(self, node: object) -> CompiledNode: ...
    def compile_html(
        self,
        html: str,
        *,
        presets: Literal["chromium", "none"] = "chromium",
        tailwind_property: str | None = None,
        max_depth: int | None = None,
    ) -> CompiledNode: ...
    def compile_stylesheet(self, css: str) -> CompiledStyleSheet: ...
    def compile_stylesheet_lossy(self, css: str) -> CompiledStyleSheet: ...
    def compile_keyframes(self, keyframes: object) -> CompiledStyleSheet: ...
    def register_font(self, font: _FontResourceInput) -> list[str]: ...
    def register_fonts(self, fonts: Sequence[_FontResourceInput]) -> list[str]: ...
    def load_font(self, font: _FontResourceInput) -> None: ...
    def load_fonts(self, fonts: Sequence[_FontResourceInput]) -> None: ...
    def put_persistent_image(
        self, src: str, data: bytes, cache: _ImageCacheMode = "auto"
    ) -> None: ...
    def clear_image_store(self) -> None: ...
    def render_compiled(
        self,
        node: CompiledNode,
        *,
        stylesheets: Sequence[CompiledStyleSheet] | None = None,
        width: int | None = 1200,
        height: int | None = 630,
        font_size: float = 16.0,
        device_pixel_ratio: float = 1.0,
        draw_debug_border: bool = False,
        time_ms: int = 0,
        dithering: _DitheringAlgorithm = "none",
        fetched_resources: Sequence[_ImageResourceInput] | None = None,
        images: Sequence[_ImageResourceInput] | None = None,
        font_families: Sequence[str] | None = None,
        lang: str | None = None,
        format: _ImageOutputFormat = "png",
        quality: int | None = None,
        lossless: bool | None = None,
    ) -> bytes: ...
    def measure_compiled(
        self,
        node: CompiledNode,
        *,
        stylesheets: Sequence[CompiledStyleSheet] | None = None,
        width: int | None = 1200,
        height: int | None = 630,
        font_size: float = 16.0,
        device_pixel_ratio: float = 1.0,
        draw_debug_border: bool = False,
        time_ms: int = 0,
        dithering: _DitheringAlgorithm = "none",
        fetched_resources: Sequence[_ImageResourceInput] | None = None,
        images: Sequence[_ImageResourceInput] | None = None,
        font_families: Sequence[str] | None = None,
        lang: str | None = None,
    ) -> _MeasuredNodeOutput: ...
    def render_svg_compiled(
        self,
        node: CompiledNode,
        *,
        stylesheets: Sequence[CompiledStyleSheet] | None = None,
        width: int | None = 1200,
        height: int | None = 630,
        font_size: float = 16.0,
        time_ms: int = 0,
        fetched_resources: Sequence[_ImageResourceInput] | None = None,
        images: Sequence[_ImageResourceInput] | None = None,
        font_families: Sequence[str] | None = None,
        lang: str | None = None,
    ) -> str: ...
    def render_sequence_at_time_compiled(
        self,
        scenes: Sequence[tuple[CompiledNode, int]],
        time_ms: int,
        *,
        stylesheets: Sequence[CompiledStyleSheet] | None = None,
        width: int | None = 1200,
        height: int | None = 630,
        font_size: float = 16.0,
        device_pixel_ratio: float = 1.0,
        draw_debug_border: bool = False,
        dithering: _DitheringAlgorithm = "none",
        fetched_resources: Sequence[_ImageResourceInput] | None = None,
        images: Sequence[_ImageResourceInput] | None = None,
        font_families: Sequence[str] | None = None,
        lang: str | None = None,
        format: _ImageOutputFormat = "png",
        quality: int | None = None,
        lossless: bool | None = None,
    ) -> bytes: ...
    def render_animation_compiled(
        self,
        scenes: Sequence[tuple[CompiledNode, int]],
        *,
        stylesheets: Sequence[CompiledStyleSheet] | None = None,
        width: int | None = 1200,
        height: int | None = 630,
        font_size: float = 16.0,
        device_pixel_ratio: float = 1.0,
        draw_debug_border: bool = False,
        dithering: _DitheringAlgorithm = "none",
        fetched_resources: Sequence[_ImageResourceInput] | None = None,
        images: Sequence[_ImageResourceInput] | None = None,
        font_families: Sequence[str] | None = None,
        lang: str | None = None,
        fps: int = 30,
        format: _AnimationOutputFormat = "webp",
        quality: int | None = None,
        lossless: bool | None = None,
        loop_count: int | None = None,
        webp_blend: bool = True,
        webp_dispose: bool = False,
        webp_speed: int | None = None,
    ) -> bytes: ...
    def encode_frames(
        self,
        frames: Sequence[_RawAnimationFrameInput],
        *,
        format: _AnimationOutputFormat = "webp",
        quality: int | None = None,
        lossless: bool | None = None,
        loop_count: int | None = None,
        webp_blend: bool = True,
        webp_dispose: bool = False,
        webp_speed: int | None = None,
    ) -> bytes: ...
