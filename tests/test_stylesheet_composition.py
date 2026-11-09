from __future__ import annotations

import pytest

from takumi_py import CompiledNode, CompiledStyleSheet, Renderer, StyleSheetError

BLUE = bytes((0, 0, 255, 255))
RED = bytes((255, 0, 0, 255))
BOX: dict[str, object] = {"type": "container", "className": "box"}
CSS = ".box {width:1px;height:1px;background:blue}"


@pytest.mark.parametrize(
    "first",
    [
        "/* unfinished comment",
        ".unused {background:red",
        "@media screen {.unused {background:red",
        ".unused",
        "@unknown unfinished",
        '.unused {content:"unfinished',
        '.unused {content:"bad\n',
        ".unused {background:url(unfinished",
        '.unused {background:url(bad"url',
        '.unused {background:url(bad"' + "\\",
        '.unused {background:url(bad"' + "\\" * 2,
        '.unused {background:url(bad"' + "\\" * 3,
        '.unused[data-name="}/*"] {width:calc(1px + 1px)',
    ],
)
def test_independent_stylesheet_eof_cannot_consume_next_source(first: str) -> None:
    renderer = Renderer(load_default_fonts=False)
    actual = renderer.render_compiled(
        renderer.compile_node(BOX),
        stylesheets=[
            renderer.compile_stylesheet_lossy(first),
            renderer.compile_stylesheet(CSS),
        ],
        width=1,
        height=1,
        format="raw",
    )
    assert actual == BLUE


@pytest.mark.parametrize("backslashes", [1, 2, 3])
def test_bad_url_eof_preserves_prior_declarations(backslashes: int) -> None:
    renderer = Renderer(load_default_fonts=False)
    first = renderer.compile_stylesheet_lossy(
        '.box{width:1px;height:1px;background:red;background-image:url(bad"'
        + "\\" * backslashes
        + "}"
    )
    second = renderer.compile_stylesheet(".box{background:blue}")
    node = renderer.compile_node(BOX)

    def render(stylesheets: list[CompiledStyleSheet]) -> bytes:
        return renderer.render_compiled(
            node, stylesheets=stylesheets, width=1, height=1, format="raw"
        )

    assert render([first]) == RED
    assert render([first, second]) == BLUE


def _render_first_pixel(
    renderer: Renderer, node: CompiledNode, stylesheets: list[CompiledStyleSheet]
) -> bytes:
    return renderer.render_compiled(
        node,
        stylesheets=stylesheets,
        width=4,
        height=4,
        format="raw",
        time_ms=0,
    )[:4]


@pytest.mark.parametrize("structured_last", [False, True])
def test_css_and_structured_keyframes_follow_source_order(
    structured_last: bool,
) -> None:
    renderer = Renderer(load_default_fonts=False)
    node = renderer.compile_node(
        {
            **BOX,
            "style": {"width": "1px", "height": "1px", "animation": "color 1s both"},
        }
    )
    structured = renderer.compile_keyframes(
        {
            "color": {
                "from": {"backgroundColor": "red"},
                "to": {"backgroundColor": "red"},
            }
        }
    )
    css = renderer.compile_stylesheet(
        "@keyframes color {from {background:blue} to {background:blue}}"
    )
    stylesheets = [css, structured] if structured_last else [structured, css]

    actual = _render_first_pixel(renderer, node, stylesheets)

    assert actual == (RED if structured_last else BLUE)


@pytest.mark.parametrize("css_last", [False, True])
def test_css_keyframes_follow_stylesheet_order(css_last: bool) -> None:
    renderer = Renderer(load_default_fonts=False)
    node = renderer.compile_node(
        {
            **BOX,
            "style": {"width": "1px", "height": "1px", "animation": "color 1s both"},
        }
    )
    red = renderer.compile_stylesheet(
        "@keyframes color {from {background:red} to {background:red}}"
    )
    blue = renderer.compile_stylesheet(
        "@keyframes color {from {background:blue} to {background:blue}}"
    )
    stylesheets = [red, blue] if css_last else [blue, red]

    actual = _render_first_pixel(renderer, node, stylesheets)

    assert actual == (BLUE if css_last else RED)


@pytest.mark.parametrize(
    "css",
    [
        '.box {--label:"unfinished',
        ".box {width:1px;height:1px;background:blue",
        "@media screen {.box {width:1px;height:1px;background:blue}",
        '.box {--label:"a\\"b";width:1px;height:1px;background:blue}',
        ".box {--x:1px; width:calc(var(--x) + 0px);height:1px;background:blue}",
    ],
)
def test_adding_empty_sheet_preserves_a_lossy_sheets_meaning(css: str) -> None:
    renderer = Renderer(load_default_fonts=False)
    node = renderer.compile_node(BOX)
    sheet = renderer.compile_stylesheet_lossy(css)

    def render(stylesheets: list[CompiledStyleSheet]) -> bytes:
        return renderer.render_compiled(
            node, stylesheets=stylesheets, width=1, height=1, format="raw"
        )

    assert render([sheet]) == render([sheet, renderer.compile_stylesheet("")])


def test_deep_nested_css_is_compiled_through_renderer_api() -> None:
    depth = 64
    nested_value = "var(--x," * depth + "1px" + ")" * depth
    css = f".box {{width:1px;height:1px;background:blue;--depth:{nested_value}}}"
    renderer = Renderer(load_default_fonts=False)
    sheet = renderer.compile_stylesheet(css)

    actual = renderer.render_compiled(
        renderer.compile_node(BOX),
        stylesheets=[sheet],
        width=1,
        height=1,
        format="raw",
    )

    assert actual == BLUE


def test_deep_nested_structured_keyframes_use_renderer_api() -> None:
    depth = 64
    nested_value = "var(--x," * depth + "1px" + ")" * depth
    renderer = Renderer(load_default_fonts=False)

    sheet = renderer.compile_keyframes(
        {"fade": {"from": {"--depth": nested_value}, "to": {"opacity": 1}}}
    )

    assert isinstance(sheet, CompiledStyleSheet)


@pytest.mark.parametrize(
    "value", ["red; background:blue", "red} } .box {background:blue}"]
)
def test_structured_custom_property_cannot_escape_its_declaration(
    value: str,
) -> None:
    renderer = Renderer(load_default_fonts=False)
    with pytest.raises(StyleSheetError, match="invalid CSS declaration"):
        renderer.compile_keyframes({"fade": {"from": {"--paint": value}}})


@pytest.mark.parametrize("offset", [float("nan"), float("inf"), -0.5, 1.5])
def test_structured_keyframe_offsets_are_validated_before_composition(
    offset: float,
) -> None:
    renderer = Renderer(load_default_fonts=False)
    with pytest.raises(StyleSheetError, match="offsets"):
        renderer.compile_keyframes(
            [
                {
                    "name": "fade",
                    "keyframes": [
                        {"offsets": [offset], "declarations": {"opacity": 1}}
                    ],
                }
            ]
        )
