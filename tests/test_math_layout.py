from __future__ import annotations

from base64 import b64decode
from importlib.util import find_spec
from xml.etree import ElementTree as ET

import pytest

from takumi_py import (
    Document,
    HtmlOptions,
    LayoutOptions,
    RasterOptions,
    Renderer,
    RenderOptions,
    compile_document,
)
from takumi_py.math import MathOptions, MathTypesetter

pytestmark = pytest.mark.skipif(
    find_spec("py_mini_racer") is None, reason="math extra is not installed"
)


def test_formula_baseline_matches_html_and_node_with_dpr() -> None:
    with MathTypesetter() as typesetter:
        formula = typesetter.typeset(r"\frac{a}{b}+\sqrt{x}")
    images = (formula.to_image_resource(),)
    style = {"display": "block", "fontSize": 20, "lineHeight": "80px"}
    before = {"type": "text", "text": "Ag"}
    after = {"type": "text", "text": "Ag"}
    shifted = formula.to_node()
    unshifted = dict(shifted)
    unshifted["style"] = dict(shifted["style"], verticalAlign="0px")
    renderer = Renderer()
    for dpr in (1, 2):
        options = RenderOptions(
            width=500, height=200, device_pixel_ratio=dpr, images=images
        )
        node: dict[str, object] = {
            "type": "container",
            "style": style,
            "children": [before, shifted, after],
        }
        shifted_layout = renderer.measure_node(node, options=options)
        node["children"] = [before, unshifted, after]
        base_layout = renderer.measure_node(node, options=options)
        delta = (
            shifted_layout.children[0].transform[5]
            - base_layout.children[0].transform[5]
        )
        assert delta == pytest.approx(formula.depth_px * dpr, abs=1 / 32)
        assert shifted_layout.runs[0].y == base_layout.runs[0].y
        html = (
            '<div style="display:block;font-size:20px;line-height:80px">Ag'
            + formula.to_html()
            + "Ag</div>"
        )
        html_layout = renderer.measure_html(
            html, html_options=HtmlOptions(presets="none"), options=options
        )
        assert html_layout == shifted_layout


def test_formula_block_centers_and_vector_keeps_svg_paths() -> None:
    with MathTypesetter() as typesetter:
        formula = typesetter.typeset(r"\frac{a}{b}", options=MathOptions(display=True))
    document = compile_document(Document.from_node(formula.to_fragment()))
    renderer = Renderer()
    layout = LayoutOptions(width=300, height=100)
    measured = renderer.measure(document, layout=layout)
    image = measured.children[0]
    assert image.transform[4] == pytest.approx((300 - formula.width_px) / 2, abs=1 / 32)
    vector = ET.fromstring(renderer.render_svg(document, layout=layout))  # noqa: S314
    embedded = list(vector.iter("{http://www.w3.org/2000/svg}image"))
    assert len(embedded) == 1
    uri = embedded[0].get("href") or embedded[0].get(
        "{http://www.w3.org/1999/xlink}href"
    )
    assert uri is not None and uri.startswith("data:image/svg+xml;base64,")
    svg = b64decode(uri.split(",", 1)[1])
    assert b"<path" in svg and b"<text" not in svg
    assert b"data:image/png" not in svg
    raw = renderer.render(
        document, layout=layout, output=RasterOptions(format="raw", scale=2)
    )
    assert len(raw) == 600 * 200 * 4
