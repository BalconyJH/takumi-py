from __future__ import annotations

from importlib.util import find_spec

import pytest

from takumi_py import (
    ContainerNode,
    Document,
    LayoutOptions,
    RasterOptions,
    Renderer,
)
from takumi_py.document import Fragment, ResourceSet
from takumi_py.math import MathOptions, MathTypesetter

pytestmark = pytest.mark.skipif(
    find_spec("py_mini_racer") is None,
    reason="math extra is not installed",
)


def test_math_svg_conversions_own_resources_and_render_all_outputs() -> None:
    with MathTypesetter(extensions=("mhchem",)) as typesetter:
        formula = typesetter.typeset(
            r"\frac{a}{b}+\sqrt{x}+\ce{2H2 -> 2H2O}",
            options=MathOptions(font_size_px=20, ex_ratio=0.5),
        )
        resource = formula.to_image_resource()
        fragment = formula.to_fragment()
        assert isinstance(fragment, Fragment)
        assert fragment.resources == ResourceSet(images=(resource,))

        document = Document.from_node(fragment)
        renderer = Renderer()
        layout = LayoutOptions(width=320, height=120)
        raster = renderer.render(
            document,
            layout=layout,
            output=RasterOptions(format="png"),
        )
        measured = renderer.measure(document, layout=layout)
        vector = renderer.render_svg(document, layout=layout)
        assert raster.startswith(b"\x89PNG\r\n\x1a\n")
        assert measured.width == pytest.approx(formula.width_px)
        assert measured.height == pytest.approx(formula.height_px)
        assert vector.startswith("<svg")


def test_current_color_inherits_from_takumi_parent_for_raster_and_svg() -> None:
    with MathTypesetter() as typesetter:
        formula = typesetter.typeset("x+y")
        resource = formula.to_image_resource()
        renderer = Renderer()
        layout = LayoutOptions(width=120, height=60)
        outputs: dict[str, tuple[bytes, str]] = {}
        for color in ("red", "blue"):
            node: ContainerNode = {
                "type": "container",
                "style": {
                    "color": color,
                    "width": "120px",
                    "height": "60px",
                },
                "children": [formula.to_node()],
            }
            document = Document.from_node(node, resources=(resource,))
            outputs[color] = (
                renderer.render(document, layout=layout, output=RasterOptions()),
                renderer.render_svg(document, layout=layout),
            )
        assert outputs["red"][0] != outputs["blue"][0]
        assert outputs["red"][1] != outputs["blue"][1]
