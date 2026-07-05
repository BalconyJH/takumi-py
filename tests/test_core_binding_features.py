from pathlib import Path

import pytest

from takumi_py import (
    AnimationEncodeOptions,
    AnimationError,
    AnimationScene,
    FontError,
    FontResource,
    HtmlOptions,
    ImageResource,
    RawAnimationFrame,
    Renderer,
    RenderOptions,
    validate_node,
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


def test_measure_html_uses_explicit_stylesheets() -> None:
    measured = Renderer().measure_html(
        """
        <div class="card">hello</div>
        """,
        stylesheets=[".card { width: 90px; height: 30px; font-size: 12px; }"],
        width=None,
        height=None,
    )

    assert measured.width == 90
    assert measured.height == 30


def test_font_and_image_resources_can_be_loaded() -> None:
    renderer = Renderer(load_default_fonts=False)
    with pytest.warns(DeprecationWarning, match="load_font is deprecated"):
        renderer.load_font(
            FontResource(
                data=Path(
                    "takumilib/assets/fonts/manrope/manrope-latin-wght-normal.woff2"
                ).read_bytes()
            )
        )
    with pytest.warns(DeprecationWarning, match="put_persistent_image is deprecated"):
        renderer.put_persistent_image(
            ImageResource("memory://pixel", SVG_1X1, cache="none")
        )

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


def test_per_render_images_can_resolve_images() -> None:
    png = Renderer().render_node(
        {"type": "image", "src": "memory://fetched", "width": 1, "height": 1},
        width=4,
        height=4,
        images=[ImageResource("memory://fetched", SVG_1X1)],
    )

    assert png.startswith(b"\x89PNG")


def test_per_render_images_respect_cache_mode_shape() -> None:
    png = Renderer().render_node(
        {"type": "image", "src": "memory://uncached", "width": 1, "height": 1},
        width=4,
        height=4,
        images=[ImageResource("memory://uncached", SVG_1X1, cache="none")],
    )

    assert png.startswith(b"\x89PNG")


def test_per_render_fetched_resources_warns_and_still_resolves_images() -> None:
    with pytest.warns(DeprecationWarning, match="fetched_resources is deprecated"):
        png = Renderer().render_node(
            {"type": "image", "src": "memory://fetched", "width": 1, "height": 1},
            width=4,
            height=4,
            fetched_resources=[ImageResource("memory://fetched", SVG_1X1)],
        )

    assert png.startswith(b"\x89PNG")


def test_register_font_returns_registered_families() -> None:
    renderer = Renderer(load_default_fonts=False)
    families = renderer.register_font(
        FontResource(
            data=Path(
                "takumilib/assets/fonts/manrope/manrope-latin-wght-normal.woff2"
            ).read_bytes()
        )
    )

    assert families


def test_register_font_accepts_v2_descriptor_fields() -> None:
    renderer = Renderer(load_default_fonts=False)
    families = renderer.register_font(
        FontResource(
            data=Path(
                "takumilib/assets/fonts/manrope/manrope-latin-wght-normal.woff2"
            ).read_bytes(),
            name="Descriptor Manrope",
            weight=500,
            style="normal",
            subset_of="DescriptorLogical",
            generic_family="sans-serif",
        )
    )

    assert families == ("Descriptor Manrope",)


def test_register_font_rejects_invalid_style_descriptor() -> None:
    renderer = Renderer(load_default_fonts=False)

    with pytest.raises(FontError, match="unsupported font style"):
        renderer.register_font(
            FontResource(
                data=Path(
                    "takumilib/assets/fonts/manrope/manrope-latin-wght-normal.woff2"
                ).read_bytes(),
                style="banana",
            )
        )


def test_validate_node_accepts_lang_metadata() -> None:
    node = validate_node({"type": "text", "text": "こんにちは", "lang": "ja"})

    assert node["lang"] == "ja"


def test_compiled_node_collects_resource_urls() -> None:
    compiled = Renderer().compile_node(
        {
            "type": "container",
            "children": [
                {
                    "type": "image",
                    "src": "https://example.com/logo.png",
                    "width": 1,
                    "height": 1,
                }
            ],
        }
    )

    assert compiled.resource_urls() == ["https://example.com/logo.png"]


def test_html_options_can_disable_default_presets() -> None:
    measured = Renderer().measure_html(
        "<body><div style='width: 10px; height: 6px'></div></body>",
        html_options=HtmlOptions(presets="none"),
        width=None,
        height=None,
    )

    assert measured.width == 10
    assert measured.height == 6


def test_render_svg_html_returns_svg_document() -> None:
    svg = Renderer().render_svg_html(
        """
        <div class="card">Hello</div>
        """,
        stylesheets=[".card { width: 64px; height: 32px; color: black; }"],
        width=64,
        height=32,
    )

    assert svg.startswith("<svg")
    assert 'width="64"' in svg


def test_lossless_webp_rejects_quality_conflict() -> None:
    with pytest.raises(ValueError, match="quality cannot be set"):
        Renderer().render_node(
            {"type": "container", "style": {"width": "1px", "height": "1px"}},
            width=1,
            height=1,
            format="webp",
            quality=80,
            lossless=True,
        )


def test_render_options_images_can_drive_rendering() -> None:
    png = Renderer().render_node(
        {"type": "image", "src": "memory://fetched", "width": 1, "height": 1},
        width=4,
        height=4,
        options=RenderOptions(images=[ImageResource("memory://fetched", SVG_1X1)]),
    )

    assert png.startswith(b"\x89PNG")


def test_css_animation_can_be_sampled_by_time_ms() -> None:
    html = """
    <div class="box"></div>
    """
    stylesheet = """
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
    """
    renderer = Renderer()

    first = renderer.render_html(
        html,
        stylesheets=[stylesheet],
        width=8,
        height=8,
        format="raw",
        time_ms=0,
    )
    second = renderer.render_html(
        html,
        stylesheets=[stylesheet],
        width=8,
        height=8,
        format="raw",
        time_ms=1000,
    )

    assert first != second


def test_structured_keyframes_can_be_sampled_by_time_ms() -> None:
    renderer = Renderer()
    node: dict[str, object] = {
        "type": "container",
        "className": "box",
        "children": [],
    }
    stylesheets = [
        """
        .box {
          width: 8px;
          height: 8px;
          background-color: black;
          animation-name: fade;
          animation-duration: 1000ms;
          animation-fill-mode: both;
        }
        """
    ]
    keyframes = {
        "fade": {
            "from": {"opacity": 0},
            "to": {"opacity": 1},
        }
    }

    first = renderer.render_node(
        node,
        stylesheets=stylesheets,
        keyframes=keyframes,
        width=8,
        height=8,
        format="raw",
        time_ms=0,
    )
    second = renderer.render_node(
        node,
        stylesheets=stylesheets,
        options=RenderOptions(keyframes=keyframes),
        width=8,
        height=8,
        format="raw",
        time_ms=1000,
    )

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
