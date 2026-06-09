import pytest

from takumi_py import HtmlParseError, parse_html


def test_parse_html_extracts_stylesheet_and_nodes() -> None:
    parsed = parse_html(
        """
        <div class="card" data-kind="demo">
          <h1>Hello</h1>
          <br>
          <img src="asset:demo" width="16">
        </div>
        <style>.card { color: white; }</style>
        """
    )

    assert parsed.stylesheets == (".card { color: white; }",)
    assert parsed.node["type"] == "container"
    assert parsed.node["className"] == "card"
    assert parsed.node["attributes"] == {"data-kind": "demo"}
    children = parsed.node["children"]
    elements = [child for child in children if child["type"] != "text"]
    assert elements[0]["tagName"] == "h1"
    assert {"type": "text", "text": "\n"} in children
    assert elements[1]["type"] == "image"
    assert elements[1]["width"] == 16.0


def test_parse_html_wraps_multiple_roots() -> None:
    parsed = parse_html("<h1>Hello</h1><p>World</p>")

    assert parsed.node == {
        "type": "container",
        "style": {"width": "100%", "height": "100%"},
        "children": [
            {
                "type": "container",
                "tagName": "h1",
                "children": [{"type": "text", "text": "Hello"}],
            },
            {
                "type": "container",
                "tagName": "p",
                "children": [{"type": "text", "text": "World"}],
            },
        ],
    }


def test_parse_html_rejects_img_without_src() -> None:
    with pytest.raises(HtmlParseError):
        parse_html("<img>")


def test_parse_html_drops_hidden_img_without_src() -> None:
    parsed = parse_html('<img style="display:none"><div>Hello</div>')

    assert parsed.node == {
        "type": "container",
        "tagName": "div",
        "children": [{"type": "text", "text": "Hello"}],
    }


def test_parse_html_drops_unsupported_stylesheet_at_rules() -> None:
    parsed = parse_html(
        """
        <style>
        @font-face { font-family: Demo; src: url(demo.woff2); }
        @view-transition { navigation: none; }
        @-webkit-keyframes fade { from { opacity: 0; } to { opacity: 1; } }
        @keyframes fade { from { opacity: 0; } to { opacity: 1; } }
        .card { color: white; }
        </style>
        <div class="card">Hello</div>
        """
    )

    stylesheet = parsed.stylesheets[0]
    assert "@font-face" not in stylesheet
    assert "@view-transition" not in stylesheet
    assert "@-webkit-keyframes" not in stylesheet
    assert "@keyframes fade" in stylesheet
    assert ".card { color: white; }" in stylesheet
