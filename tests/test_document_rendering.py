from __future__ import annotations

import struct

import pytest

from takumi_py import (
    Document,
    Fragment,
    ImageResource,
    LayoutOptions,
    RasterOptions,
    Renderer,
    ResourceSet,
    compile_document,
)

SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="30" height="20">'
    b'<path fill="currentColor" d="M0 0H30V20H0Z"/></svg>'
)


def test_document_keeps_resources_across_compilation_and_renderers() -> None:
    fragment = Fragment(
        {"type": "image", "src": "formula", "width": 30, "height": 20},
        ResourceSet(images=(ImageResource("formula", SVG),)),
    )
    compiled = compile_document(
        Document.from_node(
            {
                "type": "container",
                "style": {"display": "block", "color": "red"},
                "children": [fragment],
            }
        )
    )
    layout = LayoutOptions(width=30, height=20)
    first = Renderer().render(
        compiled, layout=layout, output=RasterOptions(format="raw")
    )
    second = Renderer().render(
        compiled, layout=layout, output=RasterOptions(format="raw")
    )
    assert first == second
    assert bytes((255, 0, 0, 255)) in first
    assert "data:image/svg+xml" in Renderer().render_svg(compiled, layout=layout)


def test_document_canvas_uses_css_pixels_and_scale() -> None:
    document = Document.from_node(
        {"type": "container", "style": {"width": "20px", "height": "10px"}}
    )
    renderer = Renderer()
    layout = LayoutOptions(width=40, height=30)
    png = renderer.render(document, layout=layout, output=RasterOptions(scale=2))
    assert struct.unpack(">II", png[16:24]) == (80, 60)
    measured = renderer.measure(document, layout=layout)
    assert (measured.width, measured.height) == (20, 10)
    svg = renderer.render_svg(document, layout=layout)
    assert 'width="40"' in svg and 'height="30"' in svg


def test_document_inferred_canvas_scales_once() -> None:
    document = Document.from_node(
        {"type": "container", "style": {"width": "20px", "height": "10px"}}
    )
    png = Renderer().render(
        document,
        layout=LayoutOptions(width=None, height=None),
        output=RasterOptions(scale=2),
    )
    assert struct.unpack(">II", png[16:24]) == (40, 20)


def test_document_scaling_preserves_width_media_query() -> None:
    document = Document.from_html(
        '<div class="box"></div>',
        stylesheets=(
            (
                ".box { width: 100vw; height: 10px; background: blue }"
                "@media (min-width: 50px) { .box { background: red } }"
            ),
        ),
    )
    renderer = Renderer()
    for scale in (1, 2):
        pixels = renderer.render(
            document,
            layout=LayoutOptions(width=40, height=10),
            output=RasterOptions(format="raw", scale=scale),
        )
        assert pixels == bytes((0, 0, 255, 255)) * (40 * 10 * scale * scale)


@pytest.mark.parametrize(
    "value", [float("inf"), float("nan"), -1, 0, True, 1e40, 1e-50]
)
def test_document_output_rejects_invalid_scale(value: float) -> None:
    with pytest.raises(ValueError, match="scale"):
        RasterOptions(scale=value)


@pytest.mark.parametrize("width", [0, -1, True, 1.5, 2**32])
def test_document_layout_rejects_invalid_dimension(width: int) -> None:
    with pytest.raises(ValueError, match="width"):
        LayoutOptions(width=width)


def test_document_output_rejects_scaled_dimension_overflow() -> None:
    document = Document.from_html("hello")
    with pytest.raises(ValueError, match="scaled canvas"):
        Renderer().render(
            document,
            layout=LayoutOptions(width=2**32 - 1),
            output=RasterOptions(scale=2),
        )


def test_document_layout_copies_font_families() -> None:
    names = ["Geist"]
    options = LayoutOptions(font_families=names)
    names.append("Other")
    assert options.font_families == ("Geist",)


def test_legacy_canvas_dimensions_remain_output_pixels() -> None:
    png = Renderer().render_html(
        '<div style="width:20px;height:10px"></div>',
        width=40,
        height=30,
        device_pixel_ratio=2,
    )
    assert struct.unpack(">II", png[16:24]) == (40, 30)
