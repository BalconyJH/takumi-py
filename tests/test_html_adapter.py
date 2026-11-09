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


def test_parse_html_renders_img_without_src_as_empty_box() -> None:
    parsed = parse_html('<img width="10" height="20">')

    measured = Renderer().measure_compiled(parsed.node, width=None, height=None)

    assert parsed.node.resource_urls() == []
    assert (measured.width, measured.height) == (10.0, 20.0)


def test_parse_html_extracts_style_elements() -> None:
    parsed = parse_html(
        """
        <style>.card { width: 40px; height: 20px; }</style>
        <div class="card">Hello</div>
        """
    )
    measured = Renderer().measure_compiled(
        parsed.node,
        stylesheets=parsed.stylesheets,
        width=None,
        height=None,
    )

    assert len(parsed.stylesheets) == 1
    assert measured.width == 40
    assert measured.height == 20


def test_parse_html_preserves_style_order_media_and_loose_css() -> None:
    parsed = parse_html(
        """
        <style>.card { width: 10px; height: 6px; }</style>
        <style media="screen">
          .card { width: 20px; display: unknown-browser-value; }
        </style>
        <style type="text/plain">.card { width: 99px; }</style>
        <div class="card">Hello</div>
        """
    )
    measured = Renderer().measure_compiled(
        parsed.node,
        stylesheets=parsed.stylesheets,
        width=None,
        height=None,
    )

    assert len(parsed.stylesheets) == 2
    assert measured.width == 20
    assert measured.height == 6


def test_renderer_compile_html_retains_style_elements() -> None:
    compiled = Renderer().compile_html(
        "<style>.card { width: 30px; height: 12px; }</style>"
        '<div class="card">Hello</div>'
    )
    measured = Renderer().measure_compiled(
        compiled.node,
        stylesheets=compiled.stylesheets,
        width=None,
        height=None,
    )

    assert len(compiled.stylesheets) == 1
    assert measured.width == 30
    assert measured.height == 12


def test_renderer_render_html_applies_embedded_css_after_author_css() -> None:
    pixels = Renderer().render_html(
        """
        <style>
          .box { width: 20px; height: 10px; background-color: blue; }
        </style>
        <div class="box"></div>
        """,
        stylesheets=[
            ".box { background-color: red; }",
        ],
        width=20,
        height=10,
        format="raw",
    )

    assert pixels == bytes((0, 0, 255, 255)) * (20 * 10)


def test_renderer_measure_html_applies_embedded_css_after_author_css() -> None:
    measured = Renderer().measure_html(
        """
        <style>
          .box { width: 30px; height: 12px; }
        </style>
        <div class="box"></div>
        """,
        stylesheets=[
            ".box { width: 20px; height: 20px; }",
        ],
        width=None,
        height=None,
    )

    assert (measured.width, measured.height) == (30, 12)


def test_renderer_render_svg_html_applies_embedded_css_after_author_css() -> None:
    html = """
    <style>
      .box { width: 20px; height: 10px; background-color: blue; }
    </style>
    <div class="box"></div>
    """
    renderer = Renderer()

    embedded_only = renderer.render_svg_html(html, width=20, height=10)
    with_earlier_author_css = renderer.render_svg_html(
        html,
        stylesheets=[
            ".box { background-color: red; }",
        ],
        width=20,
        height=10,
    )

    assert with_earlier_author_css == embedded_only


def test_renderer_render_html_appends_keyframes_after_embedded_css() -> None:
    renderer = Renderer()
    html = """
    <style>
      .box {
        width: 8px;
        height: 8px;
        background-color: black;
        animation-name: fade;
        animation-duration: 1000ms;
        animation-fill-mode: both;
      }
    </style>
    <div class="box"></div>
    """
    keyframes = {
        "fade": {
            "from": {"opacity": 0},
            "to": {"opacity": 1},
        }
    }

    first = renderer.render_html(
        html,
        keyframes=keyframes,
        width=8,
        height=8,
        format="raw",
        time_ms=0,
    )
    last = renderer.render_html(
        html,
        keyframes=keyframes,
        width=8,
        height=8,
        format="raw",
        time_ms=1000,
    )

    assert first != last


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
