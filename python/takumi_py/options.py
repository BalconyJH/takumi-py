from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

ImageOutputFormat: TypeAlias = Literal["png", "jpeg", "jpg", "webp", "ico", "raw"]


@dataclass(frozen=True, slots=True)
class RenderOptions:
    width: int = 1200
    height: int = 630
    format: ImageOutputFormat = "png"
    quality: int | None = None
