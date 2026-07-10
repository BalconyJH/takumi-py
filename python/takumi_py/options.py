from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal, TypeAlias
from typing_extensions import TypedDict

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
    data: bytes
    name: str | None = None
    weight: float | None = None
    style: str | None = None
    subset_of: str | None = None
    generic_family: GenericFontFamily | None = None


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


def normalize_image_resources(
    resources: Sequence[ImageResourceInput] | None,
) -> list[tuple[str, bytes, ImageCacheMode]] | None:
    if resources is None:
        return None

    normalized: list[tuple[str, bytes, ImageCacheMode]] = []
    for resource in resources:
        if isinstance(resource, ImageResource):
            normalized.append((resource.src, resource.data, resource.cache))
        else:
            src, data = resource
            normalized.append((src, data, "auto"))
    return normalized


def normalize_image_resource(
    resource: ImageResourceInput,
) -> tuple[str, bytes, ImageCacheMode]:
    if isinstance(resource, ImageResource):
        return resource.src, resource.data, resource.cache
    src, data = resource
    return src, data, "auto"


def normalize_font_resources(
    resources: Sequence[FontResourceInput] | None,
) -> (
    list[tuple[bytes, str | None, float | None, str | None, str | None, str | None]]
    | None
):
    if resources is None:
        return None

    normalized: list[
        tuple[bytes, str | None, float | None, str | None, str | None, str | None]
    ] = []
    for resource in resources:
        if isinstance(resource, FontResource):
            normalized.append(
                (
                    resource.data,
                    resource.name,
                    resource.weight,
                    resource.style,
                    resource.subset_of,
                    resource.generic_family,
                )
            )
        else:
            normalized.append((resource, None, None, None, None, None))
    return normalized
