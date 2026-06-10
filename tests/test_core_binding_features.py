from pathlib import Path

import pytest

from takumi_py import (
    AnimationEncodeOptions,
    AnimationError,
    AnimationScene,
    FontResource,
    ImageResource,
    RawAnimationFrame,
    Renderer,
    RenderOptions,
)

SVG_1X1 = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1">'
    b'<rect width="1" height="1" fill="red"/></svg>'
)


def test_render_options_support_auto_viewport_and_dithering() -> None:
    raw = Renderer().render_node(
        {
            "type": "container",
            "style": {
                "width": "24px",
                "height": "12px",
                "backgroundColor": "white",
            },
        },
        width=None,
        height=None,
        format="raw",
        dithering="ordered-bayer",
    )

    assert len(raw) == 24 * 12 * 4


def test_measure_node_returns_layout_tree() -> None:
    measured = Renderer().measure_node(
        {
            "type": "container",
            "style": {"width": "240px", "height": "120px"},
            "children": [{"type": "text", "text": "hello"}],
        },
        width=240,
        height=120,
    )

    assert measured.width == 240
    assert measured.height == 120
    assert len(measured.transform) == 6
    assert measured.children or measured.runs


def test_measure_html_uses_stylesheets() -> None:
    measured = Renderer().measure_html(
        """
        <div class="card">hello</div>
        <style>
        .card { width: 90px; height: 30px; font-size: 12px; }
        </style>
        """,
        width=None,
        height=None,
    )

    assert measured.width == 90
    assert measured.height == 30


def test_font_and_image_resources_can_be_loaded() -> None:
    renderer = Renderer(load_default_fonts=False)
    renderer.load_font(
        FontResource(
            data=Path(
                "takumilib/assets/fonts/manrope/manrope-latin-wght-normal.woff2"
            ).read_bytes()
        )
    )
    renderer.put_persistent_image(ImageResource("memory://pixel", SVG_1X1))

    png = renderer.render_node(
        {
            "type": "container",
            "style": {"width": "16px", "height": "16px"},
            "children": [
                {"type": "image", "src": "memory://pixel", "width": 1, "height": 1},
                {"type": "text", "text": "ok"},
            ],
        },
        width=32,
        height=24,
    )

    assert png.startswith(b"\x89PNG")


def test_per_render_fetched_resources_can_resolve_images() -> None:
    png = Renderer().render_node(
        {"type": "image", "src": "memory://fetched", "width": 1, "height": 1},
        width=4,
        height=4,
        fetched_resources=[ImageResource("memory://fetched", SVG_1X1)],
    )

    assert png.startswith(b"\x89PNG")


def test_css_animation_can_be_sampled_by_time_ms() -> None:
    html = """
    <div class="box"></div>
    <style>
    @keyframes fade {
      from { opacity: 0; }
      to { opacity: 1; }
    }
    .box {
      width: 8px;
      height: 8px;
      background-color: black;
      animation-name: fade;
      animation-duration: 1000ms;
      animation-fill-mode: both;
    }
    </style>
    """
    renderer = Renderer()

    first = renderer.render_html(html, width=8, height=8, format="raw", time_ms=0)
    second = renderer.render_html(html, width=8, height=8, format="raw", time_ms=1000)

    assert first != second


def test_render_sequence_at_time_samples_active_scene() -> None:
    renderer = Renderer()
    scenes = [
        AnimationScene(
            {
                "type": "container",
                "style": {
                    "width": "100%",
                    "height": "100%",
                    "backgroundColor": "black",
                },
            },
            duration_ms=100,
        ),
        AnimationScene(
            {
                "type": "container",
                "style": {
                    "width": "100%",
                    "height": "100%",
                    "backgroundColor": "white",
                },
            },
            duration_ms=100,
        ),
    ]

    first = renderer.render_sequence_at_time(
        scenes,
        0,
        width=2,
        height=2,
        format="raw",
    )
    second = renderer.render_sequence_at_time(
        scenes,
        150,
        width=2,
        height=2,
        format="raw",
    )

    assert first != second


def test_render_animation_and_encode_frames_write_animated_formats() -> None:
    renderer = Renderer()
    scenes = [
        AnimationScene(
            {
                "type": "container",
                "style": {
                    "width": "100%",
                    "height": "100%",
                    "backgroundColor": "black",
                },
            },
            duration_ms=100,
        ),
        AnimationScene(
            {
                "type": "container",
                "style": {
                    "width": "100%",
                    "height": "100%",
                    "backgroundColor": "white",
                },
            },
            duration_ms=100,
        ),
    ]

    webp = renderer.render_animation(scenes, width=2, height=2, fps=20)
    apng = renderer.encode_frames(
        [
            RawAnimationFrame(bytes([0, 0, 0, 255] * 4), 2, 2, 50),
            RawAnimationFrame(bytes([255, 255, 255, 255] * 4), 2, 2, 50),
        ],
        encode_options=AnimationEncodeOptions(format="apng"),
    )
    gif = renderer.encode_frames(
        [
            RawAnimationFrame(bytes([0, 0, 0, 255] * 4), 2, 2, 50),
            RawAnimationFrame(bytes([255, 255, 255, 255] * 4), 2, 2, 50),
        ],
        format="gif",
    )

    assert webp.startswith(b"RIFF")
    assert webp[8:12] == b"WEBP"
    assert apng.startswith(b"\x89PNG")
    assert gif.startswith(b"GIF")


def test_encode_frames_rejects_empty_frames() -> None:
    with pytest.raises(AnimationError):
        Renderer().encode_frames([])


def test_render_options_dataclass_can_drive_rendering() -> None:
    raw = Renderer().render_node(
        {"type": "container", "style": {"width": "3px", "height": "2px"}},
        options=RenderOptions(width=None, height=None, format="raw"),
    )

    assert len(raw) == 3 * 2 * 4
