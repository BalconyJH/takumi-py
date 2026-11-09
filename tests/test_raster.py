from concurrent.futures import ThreadPoolExecutor
import struct
from typing import Any, cast

import pytest

from takumi_py import Document, LayoutOptions, RasterImage, RasterOptions, Renderer


def box() -> Document:
    return Document.from_node(
        {
            "type": "container",
            "style": {
                "width": "20.25px",
                "height": "10.5px",
                "backgroundColor": "rgba(255, 0, 0, 0.5)",
            },
        }
    )


@pytest.mark.parametrize("scale", [1.0, 1.5, 2.0])
def test_raster_image_reports_actual_inferred_canvas_and_straight_alpha(
    scale: float,
) -> None:
    renderer = Renderer()
    layout = LayoutOptions(width=None, height=None)
    image = renderer.rasterize(box(), layout=layout, scale=scale)
    png = renderer.render(box(), layout=layout, output=RasterOptions(scale=scale))
    assert image.size == struct.unpack(">II", png[16:24])
    assert image.stride == image.width * 4
    assert len(image.data) == image.nbytes == image.stride * image.height
    assert image.encode("raw") == image.tobytes()
    # A straight-alpha red channel stays near 255; premultiplied would be ~128.
    assert image.data[0] >= 250
    assert 120 <= image.data[3] <= 130


def test_raster_image_can_encode_after_renderer_and_document_are_gone() -> None:
    image = Renderer().rasterize(box(), layout=LayoutOptions(width=32, height=24))
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(image.encode, ("png", "webp", "jpeg")))
    assert results[0].startswith(b"\x89PNG\r\n\x1a\n")
    assert struct.unpack(">II", results[0][16:24]) == (32, 24)
    assert results[1][:4] == b"RIFF" and results[1][8:12] == b"WEBP"
    assert results[2].startswith(b"\xff\xd8")
    assert image.size == (32, 24)


def test_raw_pixels_round_trip_without_encoding_or_losing_dimensions() -> None:
    data = bytes((255, 0, 0, 255, 0, 0, 255, 255))
    image = RasterImage.from_raw(data, width=2, height=1)
    assert image.tobytes() == data
    assert image.to_raw_source()["premultiplied"] is False
    document = Document.from_node(image.to_fragment())
    rendered = Renderer().rasterize(
        document, layout=LayoutOptions(width=None, height=None)
    )
    assert rendered.size == image.size
    assert rendered.data == data
    with pytest.raises(AttributeError):
        cast(Any, image)._native = image._native


@pytest.mark.parametrize("width,height", [(0, 1), (1, 0), (-1, 1), (True, 1)])
def test_raw_bitmap_rejects_invalid_dimensions(width: int, height: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        RasterImage.from_raw(b"\x00" * 4, width=width, height=height)


def test_raw_bitmap_rejects_mismatched_or_overflowing_geometry() -> None:
    for width, height in ((2, 1), (2**32 - 1, 2**32 - 1)):
        with pytest.raises(ValueError, match="buffer size"):
            RasterImage.from_raw(b"\x00" * 4, width=width, height=height)


def test_encoding_existing_pixels_validates_format_combinations() -> None:
    image = RasterImage.from_raw(b"\x00" * 4, width=1, height=1)
    with pytest.raises(ValueError, match="lossless"):
        image.encode("png", lossless=True)
    with pytest.raises(ValueError, match="quality"):
        image.encode("webp", lossless=True, quality=75)
    with pytest.raises(ValueError, match="quality"):
        image.encode("jpeg", quality=101)
