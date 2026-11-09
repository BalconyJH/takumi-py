"""Owned static images, separate from layout and image encoding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from takumi_py import _core
from takumi_py.options import ImageOutputFormat

if TYPE_CHECKING:
    from takumi_py.document import Fragment
    from takumi_py.types import ImageNode, RawRgbaImage


@dataclass(frozen=True, slots=True)
class RasterImage:
    """An immutable native bitmap with its actual output dimensions.

    Pixels are tightly packed, row-major, straight-alpha RGBA8. Encoding borrows
    the native bitmap without laying out or drawing the document again. Reading
    ``data`` or calling ``tobytes()`` copies pixels into Python-owned bytes.
    The image remains usable after the originating renderer is released.
    """

    _native: _core.RasterImage

    def __post_init__(self) -> None:
        if not isinstance(self._native, _core.RasterImage):
            raise TypeError("use Renderer.rasterize() or RasterImage.from_raw()")

    @classmethod
    def from_raw(cls, data: bytes, *, width: int, height: int) -> RasterImage:
        """Copy tightly packed straight-alpha RGBA8 pixels into an owned bitmap."""
        for name, value in (("width", width), ("height", height)):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 0 < value <= 2**32 - 1
            ):
                raise ValueError(f"{name} must be a positive 32-bit integer")
        if not isinstance(data, bytes):
            raise TypeError("data must be bytes containing straight-alpha RGBA8")
        return cls(_core.RasterImage.from_raw(data, width, height))

    @property
    def width(self) -> int:
        """Actual output width in pixels, including raster rounding."""
        return self._native.width

    @property
    def height(self) -> int:
        """Actual output height in pixels, including raster rounding."""
        return self._native.height

    @property
    def size(self) -> tuple[int, int]:
        """Return ``(width, height)`` in output pixels."""
        return self.width, self.height

    @property
    def stride(self) -> int:
        """Number of bytes per tightly packed RGBA row."""
        return self.width * 4

    @property
    def nbytes(self) -> int:
        """Number of uncompressed RGBA bytes owned by this image."""
        return self.stride * self.height

    @property
    def data(self) -> bytes:
        """Copy the native pixels to immutable Python bytes."""
        return self.tobytes()

    def tobytes(self) -> bytes:
        """Copy the native pixels as tightly packed straight-alpha RGBA8."""
        return self._native.tobytes()

    def encode(
        self,
        format: ImageOutputFormat = "png",
        *,
        quality: int | None = None,
        lossless: bool | None = None,
    ) -> bytes:
        """Encode existing pixels as PNG, JPEG, WebP, ICO, or raw RGBA.

        Encoder rules match ``Renderer.render``. WebP defaults to lossless when
        no quality is supplied. Encoding releases the GIL and may run concurrently.
        """
        if quality is not None and (
            isinstance(quality, bool)
            or not isinstance(quality, int)
            or not 0 <= quality <= 100
        ):
            raise ValueError("quality must be an integer from 0 through 100")
        if lossless is not None and not isinstance(lossless, bool):
            raise TypeError("lossless must be a boolean or None")
        return self._native.encode(format=format, quality=quality, lossless=lossless)

    def to_raw_source(self) -> RawRgbaImage:
        """Copy pixels to a raw image source for another Takumi document."""
        return {
            "width": self.width,
            "height": self.height,
            "data": self.tobytes(),
            "premultiplied": False,
        }

    def to_fragment(self) -> Fragment[ImageNode]:
        """Compose the bitmap into a document without encoding and decoding it.

        The returned image uses the bitmap's intrinsic pixel dimensions. Set the
        node's CSS dimensions explicitly to place a high-resolution bitmap at a
        smaller CSS size. This copies the pixel buffer into the fragment snapshot.
        """
        from takumi_py.document import Fragment

        node: ImageNode = {"type": "image", "src": self.to_raw_source()}
        return Fragment(node)
