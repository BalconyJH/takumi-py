from takumi_py.html import parse_html


def test_inline_style_uses_camel_case() -> None:
    parsed = parse_html(
        '<div style="font-size: 64px; background-color: #111827"></div>'
    )

    assert parsed.node["style"] == {
        "fontSize": "64px",
        "backgroundColor": "#111827",
    }


def test_inline_style_skips_invalid_declarations() -> None:
    parsed = parse_html('<div style="font-size: 64px; broken; color: white"></div>')

    assert parsed.node["style"] == {
        "fontSize": "64px",
        "color": "white",
    }


def test_inline_style_drops_unsupported_display_values() -> None:
    parsed = parse_html('<div style="display: contents; color: white"></div>')

    assert parsed.node["style"] == {"color": "white"}


def test_inline_style_keeps_supported_display_values() -> None:
    parsed = parse_html('<div style="display: none"></div>')

    assert parsed.node["style"] == {"display": "none"}


def test_inline_style_drops_custom_properties() -> None:
    parsed = parse_html('<div style="--brand-color: red; color: white"></div>')

    assert parsed.node["style"] == {"color": "white"}


def test_inline_style_drops_ie_css_hacks() -> None:
    parsed = parse_html('<div style="display: none \\9; color: white"></div>')

    assert parsed.node["style"] == {"color": "white"}
