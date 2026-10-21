from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal, TypeAlias
from typing_extensions import TypedDict
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
    offsets: Sequence[float]
    declarations: StyleInput


class KeyframesRule(TypedDict):
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
                "FontResource.subset_of is deprecated; register each subset "
                "under the same name with unicode_range instead",
                DeprecationWarning,
                stacklevel=3,
            )


ImageResourceInput: TypeAlias = ImageResource | tuple[str, bytes]
FontResourceInput: TypeAlias = FontResource | bytes


@dataclass(frozen=True, slots=True)
class HtmlOptions:
    presets: HtmlStylePresets = "chromium"
    tailwind_property: str | None = None
    max_depth: int | None = None


@dataclass(frozen=True, slots=True)
class RenderOptions:
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
    fetched_resources: Sequence[ImageResourceInput] | None = None


@dataclass(frozen=True, slots=True)
class AnimationEncodeOptions:
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
        # Later resources replace earlier ones with the same src.
        images=[
            *normalize_image_resources(options.fetched_resources),
            *normalize_image_resources(options.images),
        ],
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
