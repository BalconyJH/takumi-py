from collections.abc import Sequence
from typing import Literal, TypeAlias, TypedDict, final, type_check_only

from takumi_py.options import (
    AnimationEncodeOptions,
    FontResource,
    NativeRenderSettings,
    RenderOptions,
)
from takumi_py.types import RawAnimationFrame

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

_FontInput: TypeAlias = bytes | FontResource

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
        fonts: Sequence[_FontInput] | None = None,
        cache_max_bytes: int | None = None,
        font_cache_max_bytes: int | None = None,
    ) -> NativeRenderer: ...
    def compile_node(self, node: object) -> CompiledNode: ...
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
    def register_font(self, font: _FontInput) -> list[str]: ...
    def register_fonts(self, fonts: Sequence[_FontInput]) -> list[str]: ...
    def cache_font(self, font: _FontInput, key: str) -> list[str]: ...
    def cached_fonts(self, key: str, pin: bool = False) -> list[str] | None: ...
    def unregister_font(self, family: str) -> bool: ...
    def clear_fonts(self) -> None: ...
    def render_compiled(
        self,
        node: CompiledNode,
        stylesheets: Sequence[CompiledStyleSheet],
        settings: NativeRenderSettings,
        encoding: RenderOptions,
    ) -> bytes: ...
    def measure_compiled(
        self,
        node: CompiledNode,
        stylesheets: Sequence[CompiledStyleSheet],
        settings: NativeRenderSettings,
    ) -> _MeasuredNodeOutput: ...
    def render_svg_compiled(
        self,
        node: CompiledNode,
        stylesheets: Sequence[CompiledStyleSheet],
        settings: NativeRenderSettings,
    ) -> str: ...
    def render_sequence_at_time_compiled(
        self,
        scenes: Sequence[tuple[CompiledNode, int]],
        time_ms: int,
        stylesheets: Sequence[CompiledStyleSheet],
        settings: NativeRenderSettings,
        encoding: RenderOptions,
    ) -> bytes: ...
    def render_animation_compiled(
        self,
        scenes: Sequence[tuple[CompiledNode, int]],
        stylesheets: Sequence[CompiledStyleSheet],
        settings: NativeRenderSettings,
        fps: int,
        encoding: AnimationEncodeOptions,
    ) -> bytes: ...
    def encode_frames(
        self,
        frames: Sequence[RawAnimationFrame],
        encoding: AnimationEncodeOptions,
    ) -> bytes: ...
