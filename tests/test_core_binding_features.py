from concurrent.futures import ThreadPoolExecutor
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
GEIST_FONT = Path("takumilib/assets/fonts/geist/Geist[wght].woff2")
GEIST_MONO_FONT = Path("takumilib/assets/fonts/geist/GeistMono[wght].woff2")
GEIST_LAST_RESORT_FONT = Path(
    "takumilib/assets/fonts/geist/geist-latin-wght-300-800.woff2"
)
NOTO_DEVANAGARI_FONT = Path(
    "takumilib/assets/fonts/noto-sans/noto-sans-devanagari-v30-devanagari-regular.woff2"
)
ARCHIVO_FONT = Path("takumilib/assets/fonts/archivo/Archivo-VariableFont_wdth,wght.ttf")
POPPINS_DEVANAGARI_FONT = Path(
    "takumilib/assets/fonts/poppins/poppins-v24-devanagari_latin-regular.woff2"
)


def render_devanagari_raw(renderer: Renderer, family: str) -> bytes:
    return renderer.render_html(
        '<span class="sample">नमस्ते</span>',
        stylesheets=[
            f"""
            .sample {{
              color: black;
              font-size: 72px;
              font-family: {family};
            }}
            """
        ],
        width=400,
        height=140,
        format="raw",
    )


def inked_pixels(raw: bytes) -> int:
    return sum(1 for index in range(3, len(raw), 4) if raw[index] > 0)


def pixel_diff(left: bytes, right: bytes) -> int:
    return sum(
        1
        for left_pixel, right_pixel in zip(left, right, strict=True)
        if left_pixel != right_pixel
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
        renderer.load_font(FontResource(data=GEIST_FONT.read_bytes()))
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


def test_inline_image_bytes_can_be_rendered() -> None:
    png = Renderer().render_node(
        {"type": "image", "src": SVG_1X1, "width": 1, "height": 1},
        width=4,
        height=4,
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
    families = renderer.register_font(FontResource(data=GEIST_FONT.read_bytes()))

    assert families


def test_register_font_accepts_raw_bytes() -> None:
    families = Renderer(load_default_fonts=False).register_font(GEIST_FONT.read_bytes())

    assert families


def test_register_font_accepts_v2_descriptor_fields() -> None:
    renderer = Renderer(load_default_fonts=False)
    families = renderer.register_font(
        FontResource(
            data=GEIST_FONT.read_bytes(),
            name="Descriptor Geist",
            weight=500,
            style="normal",
            subset_of="DescriptorLogical",
            generic_family="sans-serif",
        )
    )

    assert families == ("Descriptor Geist",)


def test_registered_generic_font_family_is_used_for_resolution() -> None:
    renderer = Renderer()
    renderer.register_font(
        FontResource(
            data=GEIST_MONO_FONT.read_bytes(),
            generic_family="monospace",
        )
    )

    def render_with_family(font_family: str) -> bytes:
        return renderer.render_node(
            {
                "type": "text",
                "text": "mono 0O1lI",
                "style": {
                    "fontFamily": font_family,
                    "fontSize": "32px",
                    "color": "black",
                },
            },
            width=256,
            height=64,
            format="raw",
        )

    assert render_with_family("monospace") == render_with_family("Geist Mono")


def test_register_font_rejects_invalid_style_descriptor() -> None:
    renderer = Renderer(load_default_fonts=False)

    with pytest.raises(FontError, match="unsupported font style"):
        renderer.register_font(
            FontResource(
                data=GEIST_FONT.read_bytes(),
                style="banana",
            )
        )


@pytest.mark.parametrize("weight", [0.0, 1001.0, float("nan"), float("inf")])
def test_register_font_rejects_invalid_weight(weight: float) -> None:
    renderer = Renderer(load_default_fonts=False)

    with pytest.raises(ValueError, match="font weight must be a finite number"):
        renderer.register_font(
            FontResource(
                data=GEIST_FONT.read_bytes(),
                weight=weight,
            )
        )


def test_validate_node_accepts_lang_metadata() -> None:
    node = validate_node({"type": "text", "text": "こんにちは", "lang": "ja"})

    assert node["lang"] == "ja"


def test_lang_selector_matches_html_lang_ancestor() -> None:
    measured = Renderer().measure_html(
        '<section lang="zh-Hant"><div class="box"></div></section>',
        stylesheets=[
            """
            .box { width: 11px; height: 7px; }
            .box:lang(zh-Hant) { width: 37px; height: 13px; }
            """
        ],
        width=None,
        height=None,
    )

    assert measured.width == 37
    assert measured.height == 13


def test_invalid_render_language_is_rejected_across_render_paths() -> None:
    renderer = Renderer()
    node: dict[str, object] = {
        "type": "container",
        "style": {"width": "2px", "height": "2px"},
    }
    expected = "lang must be a valid BCP-47 language tag"

    with pytest.raises(ValueError, match=expected):
        renderer.render_node(node, width=2, height=2, lang="not valid!")
    with pytest.raises(ValueError, match=expected):
        renderer.measure_node(node, width=2, height=2, lang="not valid!")
    with pytest.raises(ValueError, match=expected):
        renderer.render_svg_node(node, width=2, height=2, lang="not valid!")
    with pytest.raises(ValueError, match=expected):
        renderer.render_animation(
            [AnimationScene(node, duration_ms=100)],
            width=2,
            height=2,
            fps=1,
            lang="not valid!",
        )


def test_default_font_matches_upstream_geist_last_resort() -> None:
    node: dict[str, object] = {
        "type": "text",
        "text": "Hello",
        "style": {"fontSize": "48px", "fontWeight": 300, "color": "black"},
    }
    expected = Renderer(load_default_fonts=False)
    expected.register_font(
        FontResource(GEIST_LAST_RESORT_FONT.read_bytes(), name="Geist")
    )

    default = Renderer().render_node(
        node,
        width=160,
        height=80,
        format="raw",
        font_families=["Geist"],
    )
    explicit = expected.render_node(
        node,
        width=160,
        height=80,
        format="raw",
        font_families=["Geist"],
    )

    assert default == explicit


def test_font_subset_groups_route_per_family() -> None:
    renderer = Renderer(load_default_fonts=False)
    for path, unique_name, logical_name in [
        (GEIST_FONT, "Alpha-latin", "Alpha"),
        (NOTO_DEVANAGARI_FONT, "Alpha-deva", "Alpha"),
        (ARCHIVO_FONT, "Beta-latin", "Beta"),
        (POPPINS_DEVANAGARI_FONT, "Beta-deva", "Beta"),
    ]:
        renderer.register_font(
            FontResource(
                path.read_bytes(),
                name=unique_name,
                subset_of=logical_name,
                generic_family="sans-serif",
            )
        )

    alpha = render_devanagari_raw(renderer, "Alpha")
    beta = render_devanagari_raw(renderer, "Beta")
    beta_explicit = render_devanagari_raw(renderer, '"Beta-latin", "Beta-deva"')

    assert inked_pixels(alpha) > 500
    assert inked_pixels(beta) > 500
    assert pixel_diff(alpha, beta) > 1000
    assert pixel_diff(beta, beta_explicit) == 0


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


def test_concurrent_render_and_measure_calls_resolve() -> None:
    renderer = Renderer()

    def render(index: int) -> bytes:
        return renderer.render_node(
            {
                "type": "text",
                "text": f"concurrent render {index}",
                "style": {
                    "fontSize": "24px",
                    "color": "#111827",
                    "backgroundColor": f"rgb({index * 8}, {255 - index * 8}, 128)",
                },
            },
            width=320,
            height=80,
        )

    def measure(index: int) -> tuple[float, float]:
        measured = renderer.measure_node(
            {
                "type": "text",
                "text": f"concurrent measure {index}",
                "style": {"fontSize": "24px"},
            },
            width=320,
            height=80,
        )
        return measured.width, measured.height

    with ThreadPoolExecutor(max_workers=8) as executor:
        render_results = list(executor.map(render, range(8)))
        measure_results = list(executor.map(measure, range(8)))

    assert all(result.startswith(b"\x89PNG") for result in render_results)
    assert all(width > 0 and height > 0 for width, height in measure_results)


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


def test_animation_rejects_zero_duration_scenes_and_frames() -> None:
    renderer = Renderer()
    node: dict[str, object] = {
        "type": "container",
        "style": {"width": "2px", "height": "2px"},
    }
    scenes = [AnimationScene(node, duration_ms=0)]

    with pytest.raises(ValueError, match="scene duration_ms must be greater than zero"):
        renderer.render_sequence_at_time(scenes, 0, width=2, height=2)
    with pytest.raises(ValueError, match="scene duration_ms must be greater than zero"):
        renderer.render_animation(scenes, width=2, height=2)
    with pytest.raises(ValueError, match="frame duration_ms must be greater than zero"):
        renderer.encode_frames([RawAnimationFrame(bytes([0, 0, 0, 255] * 4), 2, 2, 0)])


def test_render_options_dataclass_can_drive_rendering() -> None:
    raw = Renderer().render_node(
        {"type": "container", "style": {"width": "3px", "height": "2px"}},
        options=RenderOptions(width=None, height=None, format="raw"),
    )

    assert len(raw) == 3 * 2 * 4
