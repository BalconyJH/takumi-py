"""Immutable values and options for the optional math layer."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from html import escape
import sys
from threading import TIMEOUT_MAX
from typing import TYPE_CHECKING, Protocol

from takumi_py.math._validation import (
    MAX_VALIDATED_SVG_BYTES,
    validate_color,
    validate_positive_f32,
    validate_signed_f32,
    validate_svg,
)
from takumi_py.types import ContainerNode, ImageNode, Node

if TYPE_CHECKING:
    from takumi_py.document import Fragment
    from takumi_py.options import ImageResource

__all__ = [
    "MathConverter",
    "MathLimits",
    "MathOptions",
    "MathSvg",
]


@dataclass(frozen=True, slots=True)
class MathOptions:
    """Options that affect one formula's layout and appearance.

    Attributes:
        display: Use TeX display style and block presentation.
        font_size_px: Formula em size in CSS pixels.
        ex_ratio: Input x-height/em ratio used for TeX spacing.
        color: Optional CSS named or hexadecimal foreground color. ``None``
            preserves MathJax's inheritable ``currentColor``.
    """

    display: bool = False
    font_size_px: float = 20.0
    ex_ratio: float = 0.5
    color: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.display, bool):
            raise TypeError("display must be a boolean")
        object.__setattr__(
            self,
            "font_size_px",
            validate_positive_f32("font_size_px", self.font_size_px),
        )
        object.__setattr__(
            self,
            "ex_ratio",
            validate_positive_f32("ex_ratio", self.ex_ratio),
        )
        object.__setattr__(self, "color", validate_color(self.color))


@dataclass(frozen=True, slots=True)
class MathLimits:
    """Resource limits for one :class:`MathTypesetter`.

    ``timeout_ms`` is a wall-clock budget enforced by an isolated worker
    process. ``memory_limit_bytes`` is a V8 heap budget, not a process-wide RSS
    limit. Both must fit the platform's timeout and native integer ranges.
    Cache limits use encoded SVG bytes and entry counts.
    """

    timeout_ms: int = 5_000
    memory_limit_bytes: int = 268_435_456
    max_input_bytes: int = 65_536
    max_svg_bytes: int = MAX_VALIDATED_SVG_BYTES
    max_batch_size: int = 1024
    cache_entries: int = 128
    cache_bytes: int = 16_777_216

    def __post_init__(self) -> None:
        for name in (
            "timeout_ms",
            "memory_limit_bytes",
            "max_input_bytes",
            "max_svg_bytes",
            "max_batch_size",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if self.timeout_ms > int(TIMEOUT_MAX) * 1000:
            raise ValueError("timeout_ms exceeds the platform timeout limit")
        if self.memory_limit_bytes > sys.maxsize:
            raise ValueError("memory_limit_bytes exceeds the native integer limit")
        if self.max_svg_bytes > MAX_VALIDATED_SVG_BYTES:
            raise ValueError(
                "max_svg_bytes cannot exceed the validated SVG byte limit "
                f"({MAX_VALIDATED_SVG_BYTES})"
            )
        for name in ("cache_entries", "cache_bytes"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class MathSvg:
    """A validated, engine-independent SVG formula value.

    Width, height, and depth are CSS pixels. A positive depth extends below the
    baseline; a negative depth places the baseline below the image box. The
    resource identifier is ``sha256:<lowercase hex>`` over ``data``.
    """

    data: bytes
    width_px: float
    height_px: float
    depth_px: float
    display: bool

    def __post_init__(self) -> None:
        if not isinstance(self.display, bool):
            raise TypeError("display must be a boolean")
        object.__setattr__(
            self,
            "width_px",
            validate_positive_f32("width_px", self.width_px),
        )
        object.__setattr__(
            self,
            "height_px",
            validate_positive_f32("height_px", self.height_px),
        )
        object.__setattr__(
            self,
            "depth_px",
            validate_signed_f32("depth_px", self.depth_px),
        )
        object.__setattr__(
            self,
            "data",
            validate_svg(
                self.data,
                width_px=self.width_px,
                height_px=self.height_px,
                depth_px=self.depth_px,
            ),
        )

    @property
    def resource_id(self) -> str:
        """Return the stable content identifier used by Takumi image nodes."""
        return f"sha256:{sha256(self.data).hexdigest()}"

    def to_image_resource(self) -> ImageResource:
        """Return an ``ImageResource`` matching :meth:`to_node` and HTML output."""
        from takumi_py.options import ImageResource

        return ImageResource(self.resource_id, self.data)

    def to_html(self, *, alt: str = "") -> str:
        """Return escaped HTML with explicit image dimensions and baseline styling."""
        if not isinstance(alt, str):
            raise TypeError("alt must be a string")
        width = _format_number(self.width_px)
        height = _format_number(self.height_px)
        style = f"display:inline-block;width:{width}px;height:{height}px;max-width:none"
        if not self.display:
            style += f";vertical-align:{_format_number(-self.depth_px)}px"
        image = (
            f'<img src="{self.resource_id}" width="{width}" '
            f'height="{height}" alt="{escape(alt, quote=True)}" style="{style}" />'
        )
        if not self.display:
            return image
        return f'<div style="display:block;text-align:center">{image}</div>'

    def to_node(self) -> Node:
        """Return an inline image node or a centered block container node."""
        image: ImageNode = {
            "type": "image",
            "src": self.resource_id,
            "width": self.width_px,
            "height": self.height_px,
            "style": {
                "display": "inline-block",
                "width": f"{_format_number(self.width_px)}px",
                "height": f"{_format_number(self.height_px)}px",
                "maxWidth": "none",
            },
        }
        if not self.display:
            image["style"]["verticalAlign"] = f"{_format_number(-self.depth_px)}px"
            return image
        container: ContainerNode = {
            "type": "container",
            "style": {
                "display": "block",
                "textAlign": "center",
            },
            "children": [image],
        }
        return container

    def to_fragment(self) -> Fragment[Node]:
        """Return the node together with the image resource it references."""
        from takumi_py.document import Fragment, ResourceSet

        return Fragment(
            self.to_node(),
            ResourceSet(images=(self.to_image_resource(),)),
        )


class MathConverter(Protocol):
    """Narrow protocol implemented by built-in and application-provided engines."""

    def typeset(
        self,
        tex: str,
        *,
        options: MathOptions | None = None,
    ) -> MathSvg:
        """Typeset one expression without outer Markdown delimiters."""
        ...


def _format_number(value: float) -> str:
    if value == 0:
        return "0"
    return format(value, ".17g")
