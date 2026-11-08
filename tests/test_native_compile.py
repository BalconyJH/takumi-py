import pytest

from takumi_py import CompiledNode, CompiledStyleSheet, Renderer, StyleSheetError, _core

FREE_COMPILERS = (
    "compile_html",
    "compile_keyframes",
    "compile_node",
    "compile_stylesheet",
    "merge_stylesheets",
)


def test_free_compilers_are_exported() -> None:
    assert set(FREE_COMPILERS) <= set(_core.__all__)
    assert all(callable(getattr(_core, name)) for name in FREE_COMPILERS)


def test_free_compile_node_and_html_do_not_require_a_renderer() -> None:
    node = _core.compile_node({"type": "text", "text": "hello"})
    html = _core.compile_html(
        '<div tw="w-[10px] h-[6px]"><span>hello</span></div>',
        presets="none",
    )

    assert isinstance(node, CompiledNode)
    assert isinstance(html, CompiledNode)


def test_free_compile_stylesheet_supports_strict_and_lossy_modes() -> None:
    with pytest.raises(StyleSheetError):
        _core.compile_stylesheet(".box { display: not-a-display-value; }")

    stylesheet = _core.compile_stylesheet(
        ".box { display: not-a-display-value; width: 10px; }",
        strict=False,
    )

    assert isinstance(stylesheet, CompiledStyleSheet)


def test_merged_stylesheet_preserves_cascade_when_merged_again() -> None:
    node = _core.compile_node({"type": "container", "className": "box", "children": []})
    first = _core.compile_stylesheet(".box { width: 10px; height: 10px; }")
    second = _core.compile_stylesheet(".box { width: 20px; height: 20px; }")
    third = _core.compile_stylesheet(".box { width: 30px; height: 30px; }")

    merged = _core.merge_stylesheets([first, second])
    remerged = _core.merge_stylesheets([merged, third])
    measured = Renderer().measure_compiled(
        node,
        stylesheets=[remerged],
        width=None,
        height=None,
    )

    assert isinstance(merged, CompiledStyleSheet)
    assert (measured.width, measured.height) == (30.0, 30.0)


def test_merged_stylesheet_preserves_keyframe_order() -> None:
    renderer = Renderer()
    node = _core.compile_node(
        {
            "type": "container",
            "className": "box",
            "children": [],
        }
    )
    css = _core.compile_stylesheet(
        """
        .box {
          width: 8px;
          height: 8px;
          background-color: black;
          animation-name: fade;
          animation-duration: 1000ms;
          animation-fill-mode: both;
        }
        """
    )
    first_keyframes = _core.compile_keyframes(
        {
            "fade": {
                "from": {"opacity": 0},
                "to": {"opacity": 1},
            }
        }
    )
    second_keyframes = _core.compile_keyframes(
        {
            "fade": {
                "from": {"opacity": 1},
                "to": {"opacity": 0},
            }
        }
    )

    earlier = _core.merge_stylesheets([css, first_keyframes])
    merged = _core.merge_stylesheets([earlier, second_keyframes])
    expected = _core.merge_stylesheets([css, first_keyframes, second_keyframes])

    def render(stylesheet: CompiledStyleSheet) -> bytes:
        return renderer.render_compiled(
            node,
            stylesheets=[stylesheet],
            width=8,
            height=8,
            format="raw",
            time_ms=250,
        )

    assert render(merged) == render(expected)
    assert render(merged) != render(_core.merge_stylesheets([css, first_keyframes]))
