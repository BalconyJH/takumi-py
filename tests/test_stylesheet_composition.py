from __future__ import annotations

import pytest

from takumi_py import (
    CompiledNode,
    CompiledStyleSheet,
    Document,
    LayoutOptions,
    RasterOptions,
    Renderer,
    StyleSheetError,
    _core,
)

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
@pytest.mark.parametrize("entry", ["document", "html", "compiled"])
def test_independent_stylesheet_eof_cannot_consume_next_source(
    first: str, entry: str
) -> None:
    renderer = Renderer(load_default_fonts=False)
    if entry == "document":
        actual = renderer.render(
            Document.from_html('<div class="box"></div>', stylesheets=[first, CSS]),
            layout=LayoutOptions(width=1, height=1),
            output=RasterOptions(format="raw"),
        )
    elif entry == "html":
        actual = renderer.render_html(
            f'<style>{first}</style><style>{CSS}</style><div class="box"></div>',
            width=1,
            height=1,
            format="raw",
        )
    else:
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
    renderer: Renderer, node: CompiledNode, stylesheet: CompiledStyleSheet
) -> bytes:
    return renderer.render_compiled(
        node,
        stylesheets=[stylesheet],
        width=4,
        height=4,
        format="raw",
        time_ms=0,
    )[:4]


def test_null_keyframe_name_is_canonical_before_and_after_merge() -> None:
    renderer = Renderer(load_default_fonts=False)
    node = renderer.compile_node(
        {
            "type": "container",
            "style": {
                "width": "4px",
                "height": "4px",
                "backgroundColor": "black",
                "animationName": '"fade\ufffd"',
                "animationDuration": "1s",
                "animationFillMode": "both",
            },
        }
    )
    sheet = renderer.compile_keyframes(
        [
            {
                "name": "fade\0",
                "keyframes": [
                    {
                        "offsets": [0, 1],
                        "declarations": {"backgroundColor": "red"},
                    }
                ],
            }
        ]
    )
    merged = _core.merge_stylesheets([sheet, renderer.compile_stylesheet("")])

    assert _render_first_pixel(renderer, node, sheet) == RED
    assert _render_first_pixel(renderer, node, merged) == RED


def test_null_custom_property_name_is_canonical_before_and_after_merge() -> None:
    renderer = Renderer(load_default_fonts=False)
    node = renderer.compile_node(
        {
            "type": "container",
            "style": {
                "width": "4px",
                "height": "4px",
                "backgroundColor": "var(--paint\ufffd, black)",
                "animation": "paint 1s both",
            },
        }
    )
    sheet = renderer.compile_keyframes(
        {
            "paint": {
                "from": {"--paint\0": "red"},
                "to": {"opacity": 1},
            }
        }
    )
    merged = _core.merge_stylesheets([sheet, renderer.compile_stylesheet("")])

    assert _render_first_pixel(renderer, node, sheet) == RED
    assert _render_first_pixel(renderer, node, merged) == RED


@pytest.mark.parametrize("remerge", [False, True])
@pytest.mark.parametrize("structured_last", [False, True])
def test_css_and_structured_keyframes_follow_source_order(
    remerge: bool, structured_last: bool
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
    sheets = [css, structured] if structured_last else [structured, css]
    if remerge:
        sheets = [
            _core.merge_stylesheets(
                [_core.merge_stylesheets(sheets), renderer.compile_stylesheet("")]
            )
        ]
    actual = renderer.render_compiled(
        node, stylesheets=sheets, width=1, height=1, format="raw", time_ms=500
    )
    assert actual == (RED if structured_last else BLUE)


def test_composition_preserves_global_layers_media_and_custom_properties() -> None:
    renderer = Renderer(load_default_fonts=False)
    sources = [
        "@layer base, overrides; @layer overrides {.box {background:var(--paint)}}",
        "@layer base {.box {background:red}}",
        "@media (min-width:1px) {.box {--paint:blue;width:1px;height:1px}}",
    ]
    actual = renderer.render(
        Document.from_node(BOX, stylesheets=sources),
        layout=LayoutOptions(width=1, height=1),
        output=RasterOptions(format="raw"),
    )
    assert actual == BLUE


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

    def render(sheets: list[CompiledStyleSheet]) -> bytes:
        return renderer.render_compiled(
            node, stylesheets=sheets, width=1, height=1, format="raw"
        )

    assert render([sheet]) == render([sheet, renderer.compile_stylesheet("")])


@pytest.mark.parametrize(
    "value", ["red; background:blue", "red} } .box {background:blue}"]
)
def test_structured_custom_property_cannot_escape_its_declaration(value: str) -> None:
    with pytest.raises(StyleSheetError, match="invalid CSS declaration"):
        _core.compile_keyframes({"fade": {"from": {"--paint": value}}})


@pytest.mark.parametrize("offset", [float("nan"), float("inf"), -0.5, 1.5])
def test_structured_keyframe_offsets_are_validated_before_composition(
    offset: float,
) -> None:
    with pytest.raises(StyleSheetError, match="offsets"):
        _core.compile_keyframes(
            [
                {
                    "name": "fade",
                    "keyframes": [
                        {"offsets": [offset], "declarations": {"opacity": 1}}
                    ],
                }
            ]
        )
