from __future__ import annotations

from importlib.util import find_spec
from time import monotonic
from unittest.mock import patch
from xml.etree import ElementTree as ET

import pytest

from takumi_py.math import (
    MathLimitError,
    MathLimits,
    MathOptions,
    MathRuntimeError,
    MathSvg,
    MathSyntaxError,
    MathTypesetter,
    MathValidationError,
)

pytestmark = pytest.mark.skipif(
    find_spec("py_mini_racer") is None,
    reason="math extra is not installed",
)

SVG_NS = "http://www.w3.org/2000/svg"


@pytest.mark.parametrize("font_size_px", [20.0, 40.0, 1000.0])
@pytest.mark.parametrize("ex_ratio", [0.4, 0.5])
def test_requested_formula_scale_matrix_is_complete(
    font_size_px: float,
    ex_ratio: float,
) -> None:
    expected_paths = {
        r"\frac{x^2+y^2}{a+b}": 8,
        "a+b": 3,
        "E = mc^2": 5,
        r"\sqrt{x}": 2,
        "{}^{2}": 1,
    }
    with MathTypesetter() as typesetter:
        for tex, path_count in expected_paths.items():
            formula = typesetter.typeset(
                tex,
                options=MathOptions(
                    font_size_px=font_size_px,
                    ex_ratio=ex_ratio,
                ),
            )
            root = ET.fromstring(formula.data)  # noqa: S314
            assert root.tag == f"{{{SVG_NS}}}svg"
            actual_paths = len(list(root.iter(f"{{{SVG_NS}}}path")))
            assert actual_paths == path_count, (
                f"{tex!r} produced {actual_paths} paths, expected {path_count}"
            )
            assert formula.width_px > 0
            assert formula.height_px > 0


def test_inline_operators_ams_matrix_and_geometry_are_complete() -> None:
    with MathTypesetter() as typesetter:
        inline = typesetter.typeset("a+b")
        inline_root = ET.fromstring(inline.data)  # noqa: S314
        assert [
            node.get("data-mml-node")
            for node in inline_root.iter()
            if node.get("data-mml-node") is not None
        ][:4] == ["math", "mi", "mo", "mi"]
        assert len(list(inline_root.iter(f"{{{SVG_NS}}}path"))) == 3

        fractional = typesetter.typeset(r"\frac{x^2+y^2}{a+b}")
        fractional_root = ET.fromstring(fractional.data)  # noqa: S314
        assert len(list(fractional_root.iter(f"{{{SVG_NS}}}path"))) >= 8

        matrix = typesetter.typeset(
            r"\begin{pmatrix}a&b\\c&d\end{pmatrix}",
            options=MathOptions(display=True),
        )
        matrix_root = ET.fromstring(matrix.data)  # noqa: S314
        assert matrix.display is True
        assert any(node.get("data-mml-node") == "mtable" for node in matrix_root.iter())
        assert matrix.height_px > 0

        small = typesetter.typeset("x+y", options=MathOptions(font_size_px=20))
        large = typesetter.typeset("x+y", options=MathOptions(font_size_px=40))
        assert large.width_px == pytest.approx(small.width_px * 2, abs=0.02)
        assert large.height_px == pytest.approx(small.height_px * 2, abs=0.02)
        assert large.depth_px == pytest.approx(small.depth_px * 2, abs=0.02)


def test_mhchem_is_explicit_and_macro_state_does_not_leak() -> None:
    with MathTypesetter() as disabled, pytest.raises(MathSyntaxError):
        disabled.typeset(r"\ce{2H2 -> 2H2O}")

    with MathTypesetter(extensions=("mhchem",)) as enabled:
        chemistry = enabled.typeset(r"\ce{2H2 -> 2H2O}")
        assert (
            b'data-mml-node="mtable"' in chemistry.data or b"mspace" in chemistry.data
        )
        assert b"<text" not in chemistry.data

        defined = enabled.typeset(r"\newcommand{\local}{x}\local")
        assert defined.width_px > 0
        with pytest.raises(MathSyntaxError):
            enabled.typeset(r"\local")
        assert enabled.typeset("a+b").width_px > defined.width_px
        for unsupported in (
            r"\tag{1}x",
            r"x\label{target}",
            r"\ref{target}",
            r"\newcommand{\badref}{\tag}\badref{1}x",
        ):
            with pytest.raises(MathSyntaxError):
                enabled.typeset(unsupported)


def test_cache_hits_are_bounded_and_options_are_semantic() -> None:
    limits = MathLimits(cache_entries=2, cache_bytes=200_000)
    with MathTypesetter(limits=limits) as typesetter:
        first = typesetter.typeset("x+y")
        runtime = typesetter._runtime
        assert runtime is not None
        with patch.object(runtime, "typeset", wraps=runtime.typeset) as typeset_call:
            assert typesetter.typeset("x+y") is first
            assert typeset_call.call_count == 0
            colored = typesetter.typeset("x+y", options=MathOptions(color="red"))
            assert typeset_call.call_count == 1
            assert colored.resource_id != first.resource_id
            assert typesetter.typeset("x").width_px > 0
            assert typesetter.typeset("y").width_px > 0
        assert len(typesetter._cache) == limits.cache_entries


def test_batch_preserves_order_deduplicates_and_enforces_limit() -> None:
    limits = MathLimits(max_batch_size=3)
    with MathTypesetter(limits=limits) as typesetter:
        first, second, third = typesetter.typeset_many(("x", "x", "y"))
        assert first is second
        assert first.resource_id != third.resource_id
        with pytest.raises(MathLimitError, match="max_batch_size"):
            typesetter.typeset_many(("x", "y", "z", "w"))


def test_current_color_and_explicit_color_are_distinct() -> None:
    with MathTypesetter() as typesetter:
        inherited = typesetter.typeset("x+y")
        red = typesetter.typeset("x+y", options=MathOptions(color="red"))
        assert b"currentColor" in inherited.data
        assert b"currentColor" not in red.data
        assert inherited.resource_id != red.resource_id
        assert inherited.width_px == pytest.approx(red.width_px, abs=1e-9)


def test_runtime_failure_is_recovered_and_close_rejects_calls() -> None:
    typesetter = MathTypesetter()
    with pytest.raises(MathSyntaxError):
        typesetter.typeset(r"\definitelyUndefined")
    assert typesetter.typeset("a+b").width_px > 0
    typesetter.close()
    typesetter.close()
    with pytest.raises(MathRuntimeError, match="closed"):
        typesetter.typeset("x")
    with pytest.raises(MathRuntimeError, match="closed"):
        typesetter.typeset_many(())


def test_wall_clock_limit_rejects_cold_start_and_does_not_hang() -> None:
    started = monotonic()
    typesetter = MathTypesetter(limits=MathLimits(timeout_ms=1))
    try:
        with pytest.raises(MathLimitError):
            typesetter.typeset("x")
        assert monotonic() - started < 2.0
    finally:
        typesetter.close()


def test_cjk_path_only_boundary_and_html_escaping() -> None:
    with MathTypesetter() as typesetter:
        formula = typesetter.typeset(r"\frac{a}{b}")
        html = formula.to_html(alt='a < b "quoted"')
        assert "&lt;" in html
        assert "&quot;" in html
        assert f'width="{formula.width_px:.17g}"' in html
        with pytest.raises(MathValidationError):
            typesetter.typeset(r"\text{中文}")


@pytest.mark.parametrize("tex", ["", " ", "\t\n"])
def test_empty_and_whitespace_tex_are_rejected(tex: str) -> None:
    with (
        MathTypesetter() as typesetter,
        pytest.raises(
            MathValidationError,
            match="non-whitespace",
        ),
    ):
        typesetter.typeset(tex)


def test_signed_negative_depth_is_preserved_in_conversions() -> None:
    data = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="8px" height="12px" '
        b'viewBox="0 0 8 12"><path d="M0 0L1 1Z"/></svg>'
    )
    formula = MathSvg(
        data=data,
        width_px=8,
        height_px=12,
        depth_px=-3,
        display=False,
    )
    assert "vertical-align:3px" in formula.to_html()
    node = formula.to_node()
    assert node["type"] == "image"
    assert node["style"]["verticalAlign"] == "3px"
