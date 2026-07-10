import pytest

from takumi_py import Renderer, StyleSheetError


def test_render_html_accepts_explicit_stylesheet_and_returns_png() -> None:
    png = Renderer().render_html(
        """
        <div class="card">Hello</div>
        """,
        stylesheets=[
            """
        .card {
          width: 240px;
          height: 120px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 32px;
          color: black;
        }
        """
        ],
        width=240,
        height=120,
    )

    assert png.startswith(b"\x89PNG")


def test_render_html_uses_lossy_stylesheet_compile() -> None:
    html = """
    <div class="card">Hello</div>
    """
    stylesheet = """
    @font-face { font-family: Demo; src: url(demo.woff2); }
    a { text-decoration: none; }
    .card { width: 240px; height: 120px; color: black; }
    """

    png = Renderer().render_html(
        html,
        stylesheets=[stylesheet],
        width=240,
        height=120,
    )

    assert png.startswith(b"\x89PNG")


def test_render_html_uses_lossy_stylesheet_merge() -> None:
    html = """
    <div class="card">Hello</div>
    """

    png = Renderer().render_html(
        html,
        stylesheets=[
            "a { text-decoration: none; }",
            ".card { width: 240px; height: 120px; color: black; }",
        ],
        width=240,
        height=120,
    )

    assert png.startswith(b"\x89PNG")


def test_compile_stylesheet_keeps_strict_errors() -> None:
    renderer = Renderer()

    with pytest.raises(StyleSheetError):
        renderer.compile_stylesheet("a { text-decoration: none; }")
