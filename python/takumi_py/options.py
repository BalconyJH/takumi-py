from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
from typing import Final, Literal, TypeAlias, TypedDict
from warnings import warn

ImageOutputFormat: TypeAlias = Literal["png", "jpeg", "jpg", "webp", "ico", "raw"]
AnimationOutputFormat: TypeAlias = Literal["webp", "apng", "gif"]
DitheringAlgorithm: TypeAlias = Literal["none", "ordered-bayer", "floyd-steinberg"]
ImageCacheMode: TypeAlias = Literal["auto", "none"]
HtmlStylePresets: TypeAlias = Literal["chromium", "none"]
GenericFontFamily: TypeAlias = Literal[
    "serif",
    "sans-serif",
    "monospace",
    "cursive",
    "fantasy",
    "system-ui",
    "ui-serif",
    "ui-sans-serif",
    "ui-monospace",
    "ui-rounded",
    "emoji",
    "math",
    "fangsong",
]
UnicodeRange: TypeAlias = tuple[int, int]
StyleValue: TypeAlias = str | int | float
StyleMap: TypeAlias = dict[str, StyleValue]
StyleInput: TypeAlias = Mapping[str, StyleValue]


class Keyframe(TypedDict):
    """One structured keyframe and the declarations it applies.

    Attributes:
        offsets: Normalized timeline positions from 0 through 1.
        declarations: CSS declarations applied at those positions.
    """

    offsets: Sequence[float]
    declarations: StyleInput


class KeyframesRule(TypedDict):
    """A structured keyframe rule with a CSS animation name.

    Attributes:
        name: Animation name referenced by the CSS ``animation`` property.
        keyframes: Ordered keyframes that make up the rule.
    """

    name: str
    keyframes: Sequence[Keyframe]


KeyframesMap: TypeAlias = Mapping[str, Mapping[str, StyleInput]]
KeyframesInput: TypeAlias = KeyframesMap | Sequence[KeyframesRule]


class UnsetType:
    __slots__ = ()

    def __repr__(self) -> str:
        return "UNSET"


UNSET: Final = UnsetType()


@dataclass(frozen=True, slots=True)
class ImageResource:
    """Image bytes addressable by an image node's ``src``.

    Attributes:
        src: Identifier matched against the image node's ``src``.
        data: Encoded image bytes, such as PNG, JPEG, WebP, or SVG data.
        cache: Whether the renderer may retain the decoded image in its
            renderer-local resource cache.
    """

    src: str
    data: bytes
    cache: ImageCacheMode = "auto"


@dataclass(frozen=True, slots=True)
class FontResource:
    """Font bytes plus the ``@font-face`` descriptors used to register them.

    Register each subset of a family under the same ``name`` with the
    ``unicode_range`` its ``@font-face`` declares; a subset only serves the
    codepoints in its ranges.

    Attributes:
        data: TrueType, OpenType, WOFF, or WOFF2 font bytes.
        name: Family name to register the font under. Defaults to the name
            stored in the font file.
        weight: Weight override from 1 through 1000.
        style: CSS ``font-style`` override such as ``"italic"``.
        subset_of: Deprecated. Takumi now treats it as the family name and it
            takes precedence over ``name``; use ``name`` with
            ``unicode_range`` instead.
        generic_family: CSS generic family keyword this font resolves.
        unicode_range: Inclusive ``(start, end)`` codepoint ranges the font
            serves, as in ``@font-face`` ``unicode-range``. ``None`` serves
            every codepoint the font covers.
    """

    data: bytes
    name: str | None = None
    weight: float | None = None
    style: str | None = None
    subset_of: str | None = None
    generic_family: GenericFontFamily | None = None
    unicode_range: Sequence[UnicodeRange] | None = None

    def __post_init__(self) -> None:
        if self.subset_of is not None:
            warn(
                "FontResource.subset_of is deprecated and will be removed in 0.6.0; "
                "register each subset under the same name with unicode_range instead",
                DeprecationWarning,
                stacklevel=3,
            )


ImageResourceInput: TypeAlias = ImageResource | tuple[str, bytes]
FontResourceInput: TypeAlias = FontResource | bytes


@dataclass(frozen=True, slots=True)
class HtmlOptions:
    """Inputs that control how the Rust HTML parser builds a node tree.

    Attributes:
        presets: Default element styles to apply. ``"chromium"`` matches
            browser defaults; ``"none"`` applies no preset.
        tailwind_property: HTML attribute that contains Tailwind classes.
            ``None`` reads the ``tw`` attribute.
        max_depth: Maximum element nesting depth, or ``None`` for Takumi's
            default limit.
    """

    presets: HtmlStylePresets = "chromium"
    tailwind_property: str | None = None
    max_depth: int | None = None


@dataclass(frozen=True, slots=True)
class RenderOptions:
    """Reusable render settings shared by raster, SVG, and measurement APIs.

    Explicit keyword arguments on a render method override matching fields.

    Attributes:
        width: Viewport width in CSS pixels, or ``None`` to infer it from
            layout. The default is 1200.
        height: Viewport height in CSS pixels, or ``None`` to infer it from
            layout. The default is 630.
        format: Static output format. ``"raw"`` returns row-major RGBA bytes.
        quality: Lossy encoder quality from 0 through 100 where supported.
        lossless: Whether to use lossless WebP encoding.
        font_size: Root font size in CSS pixels.
        device_pixel_ratio: Scale factor for raster output and layout.
        draw_debug_border: Draw Takumi's layout debug borders.
        time_ms: Animation sampling time in milliseconds.
        dithering: Color-dithering algorithm for supported formats.
        images: Per-render image resources addressable by their ``src`` values.
        keyframes: Structured animation rules appended to the stylesheets.
        font_families: Preferred fallback font-family order.
        lang: BCP-47 language tag used for text shaping and font selection.
    """

    width: int | None = 1200
    height: int | None = 630
    format: ImageOutputFormat = "png"
    quality: int | None = None
    lossless: bool | None = None
    font_size: float = 16.0
    device_pixel_ratio: float = 1.0
    draw_debug_border: bool = False
    time_ms: int = 0
    dithering: DitheringAlgorithm = "none"
    images: Sequence[ImageResourceInput] | None = None
    keyframes: KeyframesInput | None = None
    font_families: Sequence[str] | None = None
    lang: str | None = None


@dataclass(frozen=True, slots=True)
class LayoutOptions:
    """Document layout in CSS pixels, independent of raster output scale.

    ``None`` infers the corresponding canvas dimension from the content. An
    explicit dimension is a positive integer number of CSS pixels. Measurement
    and SVG use these same dimensions. Font registration remains renderer-local;
    ``font_families`` selects the fallback order for this document operation.
    """

    width: int | None = 1200
    height: int | None = None
    font_size: float = 16.0
    time_ms: int = 0
    font_families: Sequence[str] | None = None
    lang: str | None = None

    def __post_init__(self) -> None:
        for name in ("width", "height"):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 0 < value <= 2**32 - 1
            ):
                raise ValueError(f"{name} must be a positive 32-bit integer or None")
        _positive_native_float("font_size", self.font_size)
        if (
            isinstance(self.time_ms, bool)
            or not isinstance(self.time_ms, int)
            or not 0 <= self.time_ms <= 2**63 - 1
        ):
            raise ValueError("time_ms must be a non-negative signed 64-bit integer")
        if self.font_families is not None:
            if isinstance(self.font_families, str) or any(
                not isinstance(name, str) for name in self.font_families
            ):
                raise TypeError("font_families must be a sequence of strings")
            object.__setattr__(self, "font_families", tuple(self.font_families))


@dataclass(frozen=True, slots=True)
class RasterOptions:
    """Raster output settings for ``Renderer.render(document)``.

    ``scale`` converts the document's CSS pixels to output pixels. Explicit
    canvas dimensions are multiplied by it and rounded up. It never changes the
    units returned by ``Renderer.measure``. SVG has no raster options.
    """

    format: ImageOutputFormat = "png"
    scale: float = 1.0
    quality: int | None = None
    lossless: bool | None = None
    dithering: DitheringAlgorithm = "none"
    draw_debug_border: bool = False

    def __post_init__(self) -> None:
        _positive_native_float("scale", self.scale)


def _positive_native_float(name: str, value: float) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not 1.401298464324817e-45 <= value <= 3.4028234663852886e38
        or not math.isfinite(value)
    ):
        raise ValueError(f"{name} must be a finite positive native float")


@dataclass(frozen=True, slots=True)
class AnimationEncodeOptions:
    """Reusable encoder settings for animated output.

    Explicit keyword arguments on ``render_animation`` or ``encode_frames``
    override matching fields.

    Attributes:
        format: Animation container format.
        quality: Lossy encoder quality from 0 through 100 where supported.
        lossless: Whether to use lossless WebP encoding.
        loop_count: Number of animation repetitions, or ``None`` for the
            format-specific default.
        webp_blend: Blend each WebP frame with the previous canvas.
        webp_dispose: Dispose each WebP frame before drawing the next one.
        webp_speed: WebP encoder speed/effort setting from 0 through 6.
    """

    format: AnimationOutputFormat = "webp"
    quality: int | None = None
    lossless: bool | None = None
    loop_count: int | None = None
    webp_blend: bool = True
    webp_dispose: bool = False
    webp_speed: int | None = None


@dataclass(frozen=True, slots=True)
class NativeRenderSettings:
    """Resolved render settings in the shape the native extension reads."""

    width: int | None
    height: int | None
    font_size: float
    device_pixel_ratio: float
    draw_debug_border: bool
    time_ms: int
    dithering: DitheringAlgorithm
    images: list[ImageResource]
    font_families: list[str] | None
    lang: str | None


def native_render_settings(
    options: RenderOptions,
    *,
    raster: bool = True,
    time_ms: int | None = None,
) -> NativeRenderSettings:
    """Flatten resolved options for the native extension.

    ``raster=False`` drops the raster-only settings that SVG output ignores, and
    ``time_ms`` overrides the sampling time for scene sequences, which keep their own
    timeline.
    """
    return NativeRenderSettings(
        width=options.width,
        height=options.height,
        font_size=options.font_size,
        device_pixel_ratio=options.device_pixel_ratio if raster else 1.0,
        draw_debug_border=options.draw_debug_border if raster else False,
        time_ms=options.time_ms if time_ms is None else time_ms,
        dithering=options.dithering if raster else "none",
        images=normalize_image_resources(options.images),
        font_families=(
            None if options.font_families is None else list(options.font_families)
        ),
        lang=options.lang,
    )


def normalize_image_resources(
    resources: Sequence[ImageResourceInput] | None,
) -> list[ImageResource]:
    return [normalize_image_resource(resource) for resource in resources or ()]


def normalize_image_resource(resource: ImageResourceInput) -> ImageResource:
    if isinstance(resource, ImageResource):
        return resource
    src, data = resource
    return ImageResource(src, data)
