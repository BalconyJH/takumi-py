import pytest

from takumi_py import CompiledNode, HtmlOptions, HtmlParseError, Renderer, parse_html


def test_parse_html_returns_rust_compiled_node() -> None:
    parsed = parse_html(
        """
        <div class="card" data-kind="demo" style="width: 16px; height: 8px">
          <h1>Hello</h1>
          <br>
        </div>
        """
    )

    assert isinstance(parsed.node, CompiledNode)
    assert parsed.stylesheets == ()


def test_parse_html_compiled_node_can_render() -> None:
    parsed = parse_html("<h1>Hello</h1><p>World</p>")

    png = Renderer().render_compiled(parsed.node, width=160, height=80)

    assert png.startswith(b"\x89PNG")


def test_parse_html_rejects_img_without_src() -> None:
    with pytest.raises(HtmlParseError, match="src"):
        parse_html("<img>")


def test_parse_html_drops_style_elements() -> None:
    parsed = parse_html(
        """
        <style>.card { width: 40px; height: 20px; }</style>
        <div class="card" style="width: 8px; height: 4px">Hello</div>
        """
    )
    measured = Renderer().measure_compiled(parsed.node, width=None, height=None)

    assert measured.width == 8
    assert measured.height == 4


def test_parse_html_honors_tailwind_property_alias() -> None:
    parsed = parse_html(
        '<div class="w-[10px] h-[6px]"></div>',
        options=HtmlOptions(presets="none", tailwind_property="class"),
    )
    measured = Renderer().measure_compiled(parsed.node, width=None, height=None)

    assert measured.width == 10
    assert measured.height == 6


def test_parse_html_honors_max_depth() -> None:
    with pytest.raises(HtmlParseError, match="maximum depth"):
        parse_html("<div><span>Hello</span></div>", options=HtmlOptions(max_depth=1))
