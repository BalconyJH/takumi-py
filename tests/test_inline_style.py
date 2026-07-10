from takumi_py import Renderer


def test_inline_style_drives_html_layout() -> None:
    measured = Renderer().measure_html(
        '<div style="width: 64px; height: 32px; font-size: 12px"></div>',
        width=None,
        height=None,
    )

    assert measured.width == 64
    assert measured.height == 32


def test_invalid_inline_style_does_not_abort_html_parse() -> None:
    png = Renderer().render_html(
        '<div style="width: 64px; broken; height: 32px"></div>',
        width=64,
        height=32,
    )

    assert png.startswith(b"\x89PNG")


def test_inline_style_ignores_custom_properties() -> None:
    measured = Renderer().measure_html(
        '<div style="--brand-color: red; width: 64px; height: 32px"></div>',
        width=None,
        height=None,
    )

    assert measured.width == 64
    assert measured.height == 32
