from collections.abc import Sequence
from typing import Literal, TypeAlias
from typing_extensions import TypedDict

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
class CompiledNode: ...
class CompiledStyleSheet: ...

ImageOutputFormat: TypeAlias = Literal["png", "jpeg", "jpg", "webp", "ico", "raw"]
AnimationOutputFormat: TypeAlias = Literal["webp", "apng", "gif"]
DitheringAlgorithm: TypeAlias = Literal["none", "ordered-bayer", "floyd-steinberg"]
ImageResourceInput: TypeAlias = tuple[str, bytes]
RawAnimationFrameInput: TypeAlias = tuple[bytes, int, int, int]

class MeasuredTextRunOutput(TypedDict):
    text: str
    x: float
    y: float
    width: float
    height: float

class MeasuredNodeOutput(TypedDict):
    width: float
    height: float
    transform: list[float]
    children: list[MeasuredNodeOutput]
    runs: list[MeasuredTextRunOutput]

class NativeRenderer:
    def __init__(
        self,
        *,
        load_default_fonts: bool = True,
        fonts: Sequence[bytes] | None = None,
        persistent_images: Sequence[ImageResourceInput] | None = None,
    ) -> None: ...
    def compile_node_py(self, node: object) -> CompiledNode: ...
    def compile_stylesheet(self, css: str) -> CompiledStyleSheet: ...
    def compile_stylesheet_lossy(self, css: str) -> CompiledStyleSheet: ...
    def load_font(self, data: bytes) -> None: ...
    def load_fonts(self, fonts: Sequence[bytes]) -> None: ...
    def put_persistent_image(self, src: str, data: bytes) -> None: ...
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
        dithering: DitheringAlgorithm = "none",
        fetched_resources: Sequence[ImageResourceInput] | None = None,
        format: ImageOutputFormat = "png",
        quality: int | None = None,
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
        dithering: DitheringAlgorithm = "none",
        fetched_resources: Sequence[ImageResourceInput] | None = None,
    ) -> MeasuredNodeOutput: ...
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
        dithering: DitheringAlgorithm = "none",
        fetched_resources: Sequence[ImageResourceInput] | None = None,
        format: ImageOutputFormat = "png",
        quality: int | None = None,
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
        dithering: DitheringAlgorithm = "none",
        fetched_resources: Sequence[ImageResourceInput] | None = None,
        fps: int = 30,
        format: AnimationOutputFormat = "webp",
        quality: int | None = None,
        loop_count: int | None = None,
        webp_blend: bool = True,
        webp_dispose: bool = False,
        webp_speed: int | None = None,
    ) -> bytes: ...
    def encode_frames(
        self,
        frames: Sequence[RawAnimationFrameInput],
        *,
        format: AnimationOutputFormat = "webp",
        quality: int | None = None,
        loop_count: int | None = None,
        webp_blend: bool = True,
        webp_dispose: bool = False,
        webp_speed: int | None = None,
    ) -> bytes: ...
