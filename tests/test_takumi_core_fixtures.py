from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
from selectolax.lexbor import LexborHTMLParser

from takumi_py import NodeDecodeError, Renderer

CORE_VIEWPORT_WIDTH = 1200
CORE_VIEWPORT_HEIGHT = 630
CORE_FIXTURE_DIR = (
    Path(__file__).resolve().parents[1]
    / "takumilib"
    / "takumi"
    / "tests"
    / "fixtures-generated"
)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

KNOWN_UNSUPPORTED_CORE_FIXTURES = frozenset(
    {
        "style_backdrop_filter",
        "style_background_image_gradient_color_space_comparison",
        "style_filter_combined",
        "style_filter_combined_transform",
    }
)

CORE_HTML_FIXTURE_IDS = tuple(
    fixture_path.stem
    for fixture_path in sorted(CORE_FIXTURE_DIR.glob("*.html"))
    if fixture_path.stem not in KNOWN_UNSUPPORTED_CORE_FIXTURES
)


@pytest.fixture(scope="module")
def renderer() -> Renderer:
    return Renderer()


def test_core_fixture_directory_is_available() -> None:
    assert CORE_FIXTURE_DIR.is_dir()
    assert CORE_HTML_FIXTURE_IDS


@pytest.mark.parametrize("fixture_id", CORE_HTML_FIXTURE_IDS)
def test_core_generated_html_fixture_renders_png(
    renderer: Renderer,
    fixture_id: str,
) -> None:
    fixture_path = CORE_FIXTURE_DIR / f"{fixture_id}.html"
    golden_path = CORE_FIXTURE_DIR / f"{fixture_id}.webp"

    html = load_fixture_html(fixture_path)
    png = renderer.render_html(
        html,
        width=CORE_VIEWPORT_WIDTH,
        height=CORE_VIEWPORT_HEIGHT,
    )

    assert golden_path.is_file()
    assert png.startswith(PNG_SIGNATURE)
    assert png_size(png) == (CORE_VIEWPORT_WIDTH, CORE_VIEWPORT_HEIGHT)


@pytest.mark.parametrize(
    "fixture_id",
    sorted(KNOWN_UNSUPPORTED_CORE_FIXTURES),
)
def test_core_generated_html_fixture_known_css_limitations(
    renderer: Renderer,
    fixture_id: str,
) -> None:
    fixture_path = CORE_FIXTURE_DIR / f"{fixture_id}.html"
    html = load_fixture_html(fixture_path)

    with pytest.raises(NodeDecodeError):
        renderer.render_html(
            html,
            width=CORE_VIEWPORT_WIDTH,
            height=CORE_VIEWPORT_HEIGHT,
        )


def load_fixture_html(fixture_path: Path) -> str:
    html = fixture_path.read_text(encoding="utf-8")
    return inline_local_stylesheets(html, base_dir=fixture_path.parent)


def inline_local_stylesheets(html: str, *, base_dir: Path) -> str:
    parser = LexborHTMLParser(html)
    for link_node in parser.css("link"):
        attrs = dict(link_node.attributes or {})
        if "stylesheet" not in (attrs.get("rel") or "").lower():
            continue

        css_path = local_href_path(attrs.get("href"), base_dir=base_dir)
        if css_path is None:
            continue

        style_node = parser.create_node("style")
        style_node.insert_child(css_path.read_text(encoding="utf-8"))
        link_node.insert_before(style_node)
        link_node.decompose()

    rendered = parser.html
    return rendered if rendered is not None else html


def local_href_path(href: str | None, *, base_dir: Path) -> Path | None:
    if not href:
        return None

    parts = urlsplit(href)
    if parts.scheme or parts.netloc or parts.path.startswith("/"):
        return None

    path = (base_dir / unquote(parts.path)).resolve()
    if not path.is_file():
        return None

    return path


def png_size(png: bytes) -> tuple[int, int]:
    width = int.from_bytes(png[16:20], byteorder="big")
    height = int.from_bytes(png[20:24], byteorder="big")
    return width, height
