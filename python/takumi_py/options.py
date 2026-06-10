from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal, TypeAlias

ImageOutputFormat: TypeAlias = Literal["png", "jpeg", "jpg", "webp", "ico", "raw"]
AnimationOutputFormat: TypeAlias = Literal["webp", "apng", "gif"]
DitheringAlgorithm: TypeAlias = Literal["none", "ordered-bayer", "floyd-steinberg"]
StyleValue: TypeAlias = str | int | float
StyleMap: TypeAlias = dict[str, StyleValue]


class UnsetType:
    __slots__ = ()

    def __repr__(self) -> str:
        return "UNSET"


UNSET: Final = UnsetType()


@dataclass(frozen=True, slots=True)
class ImageResource:
    src: str
    data: bytes


@dataclass(frozen=True, slots=True)
class FontResource:
    data: bytes


ImageResourceInput: TypeAlias = ImageResource | tuple[str, bytes]
FontResourceInput: TypeAlias = FontResource | bytes


@dataclass(frozen=True, slots=True)
class RenderOptions:
    width: int | None = 1200
    height: int | None = 630
    format: ImageOutputFormat = "png"
    quality: int | None = None
    font_size: float = 16.0
    device_pixel_ratio: float = 1.0
    draw_debug_border: bool = False
    time_ms: int = 0
    dithering: DitheringAlgorithm = "none"
    fetched_resources: Sequence[ImageResourceInput] | None = None


@dataclass(frozen=True, slots=True)
class AnimationEncodeOptions:
    format: AnimationOutputFormat = "webp"
    quality: int | None = None
    loop_count: int | None = None
    webp_blend: bool = True
    webp_dispose: bool = False
    webp_speed: int | None = None


def normalize_image_resources(
    resources: Sequence[ImageResourceInput] | None,
) -> list[tuple[str, bytes]] | None:
    if resources is None:
        return None

    normalized: list[tuple[str, bytes]] = []
    for resource in resources:
        if isinstance(resource, ImageResource):
            normalized.append((resource.src, resource.data))
        else:
            src, data = resource
            normalized.append((src, data))
    return normalized


def normalize_image_resource(
    resource: ImageResourceInput,
) -> tuple[str, bytes]:
    if isinstance(resource, ImageResource):
        return resource.src, resource.data
    return resource


def normalize_font_resources(
    resources: Sequence[FontResourceInput] | None,
) -> list[bytes] | None:
    if resources is None:
        return None

    normalized: list[bytes] = []
    for resource in resources:
        if isinstance(resource, FontResource):
            normalized.append(resource.data)
        else:
            normalized.append(resource)
    return normalized
