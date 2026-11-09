from pathlib import Path

import pytest

from takumi_py import Document, FontError, LayoutOptions, Renderer, compile_document


def test_needs_uses_the_cascade_viewport_and_visibility() -> None:
    document = compile_document(
        Document.from_html(
            '<div class="card"><img src="logo"><img class="hidden" src="hidden"></div>',
            stylesheets=[
                (
                    ".card { --image: url(chosen); background-image: var(--image) }"
                    ".hidden { display: none }"
                    ".absent { background-image: url(unused) }"
                    "@media (min-width: 500px) { .card { background-image: url(wide) } }"
                )
            ],
        )
    )
    renderer = Renderer()
    assert renderer.needs(document, layout=LayoutOptions(width=300)).images == (
        "chosen",
        "logo",
    )
    assert renderer.needs(document, layout=LayoutOptions(width=600)).images == (
        "logo",
        "wide",
    )


def font_document() -> Document:
    return Document.from_html(
        '<div style="font-family: Article; font-size: 32px">Hello</div>',
        stylesheets=[
            (
                '@font-face { font-family: Article; src: url("first.woff2"), '
                'url("second.woff2"); font-weight: 400; }'
            )
        ],
    )


def test_needs_matches_raster_resolution_queries() -> None:
    document = Document.from_html(
        '<div class="photo"></div>',
        stylesheets=[
            (
                ".photo {width:20px;height:10px;background-image:url(normal)}"
                "@media (min-resolution: 2dppx) {"
                " .photo {background-image:url(retina)} }"
            )
        ],
    )
    renderer = Renderer()
    layout = LayoutOptions(width=20, height=10)
    assert renderer.needs(document, layout=layout).images == ("normal",)
    assert renderer.needs(document, layout=layout, scale=2).images == ("retina",)
    with pytest.raises(ValueError, match="scale"):
        renderer.needs(document, scale=float("nan"))


def test_css_font_files_load_forget_and_failures_are_per_operation() -> None:
    renderer = Renderer(load_default_fonts=False)
    document = compile_document(font_document())
    assert renderer.needs(document).font_files == ("first.woff2",)
    failed = LayoutOptions(failed_font_files=("first.woff2",))
    assert renderer.needs(document, layout=failed).font_files == ("second.woff2",)
    assert renderer.needs(document).font_files == ("first.woff2",)

    font = Path("takumilib/assets/fonts/geist/Geist[wght].woff2").read_bytes()
    renderer.load_font_file("first.woff2", font)
    assert renderer.needs(document).font_files == ()
    image = renderer.rasterize(document, layout=LayoutOptions(width=150, height=50))
    assert any(image.data[index] > 0 for index in range(3, image.nbytes, 4))
    assert renderer.forget_font_file("first.woff2") is True
    assert renderer.forget_font_file("first.woff2") is False
    assert renderer.needs(document).font_files == ("first.woff2",)


def test_failed_font_decoding_does_not_silently_mark_a_url_failed() -> None:
    renderer = Renderer(load_default_fonts=False)
    with pytest.raises(FontError):
        renderer.load_font_file("first.woff2", b"not a font")
    assert renderer.needs(font_document()).font_files == ("first.woff2",)


def test_layout_snapshots_failed_font_sources() -> None:
    failed = ["font.woff2"]
    options = LayoutOptions(failed_font_files=failed)
    failed.clear()
    assert options.failed_font_files == ("font.woff2",)
