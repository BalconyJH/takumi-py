from __future__ import annotations

from pathlib import Path

import pytest

from takumi_py import Renderer

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

KNOWN_PANICKING_CORE_FIXTURES = frozenset(
    {
        "style_filter_drop_shadow",
        "style_filter_combined",
        "style_filter_combined_transform",
    }
)
KNOWN_ABORTING_CORE_FIXTURES = frozenset(
    {
        "style_backdrop_filter_with_mask",
    }
)

CORE_HTML_FIXTURE_IDS = tuple(
    fixture_path.stem
    for fixture_path in sorted(CORE_FIXTURE_DIR.glob("*.html"))
    if fixture_path.stem
    not in KNOWN_PANICKING_CORE_FIXTURES | KNOWN_ABORTING_CORE_FIXTURES
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
    sorted(KNOWN_PANICKING_CORE_FIXTURES),
)
def test_core_generated_html_fixture_known_upstream_panic(
    renderer: Renderer,
    fixture_id: str,
) -> None:
    fixture_path = CORE_FIXTURE_DIR / f"{fixture_id}.html"
    html = load_fixture_html(fixture_path)

    with pytest.raises(BaseException) as exc_info:
        renderer.render_html(
            html,
            width=CORE_VIEWPORT_WIDTH,
            height=CORE_VIEWPORT_HEIGHT,
        )

    assert type(exc_info.value).__name__ == "PanicException"
    assert "attempt to subtract with overflow" in str(exc_info.value)


@pytest.mark.parametrize(
    "fixture_id",
    sorted(KNOWN_ABORTING_CORE_FIXTURES),
)
def test_core_generated_html_fixture_known_upstream_abort(fixture_id: str) -> None:
    fixture_path = CORE_FIXTURE_DIR / f"{fixture_id}.html"
    golden_path = CORE_FIXTURE_DIR / f"{fixture_id}.webp"

    assert fixture_path.is_file()
    assert golden_path.is_file()


def load_fixture_html(fixture_path: Path) -> str:
    return fixture_path.read_text(encoding="utf-8")


def png_size(png: bytes) -> tuple[int, int]:
    width = int.from_bytes(png[16:20], byteorder="big")
    height = int.from_bytes(png[20:24], byteorder="big")
    return width, height
