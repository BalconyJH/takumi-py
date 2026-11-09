from pathlib import Path

from jinja2 import DictLoader, Environment, StrictUndefined, select_autoescape
import pytest

from takumi_py import (
    Document,
    HtmlOptions,
    ImageResource,
    LayoutOptions,
    Renderer,
    ResourceSet,
    TemplateRenderer,
    compile_document,
)
from takumi_py.template import render_template_to_document, render_template_to_html

GEIST_FONT = Path("takumilib/assets/fonts/geist/Geist[wght].woff2")


def test_template_renderer_loads_template_dir(tmp_path) -> None:
    template = tmp_path / "card.html.jinja"
    template.write_text(
        """
        <div class="card">{{ title }}</div>
        """,
        encoding="utf-8",
    )

    png = TemplateRenderer(tmp_path).render(
        "card.html.jinja",
        {"title": "Hello"},
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


def test_template_renderer_with_filters(tmp_path):
    template = tmp_path / "card.html.jinja"
    template.write_text(
        """
        <div class="card">{{ title | reverse }}</div>
        """,
        encoding="utf-8",
    )

    calls: list[str] = []

    def reverse_filter(value: str) -> str:
        calls.append(value)
        return value[::-1]

    png = TemplateRenderer(
        tmp_path,
        filters={"reverse": reverse_filter},
    ).render(
        "card.html.jinja",
        {"title": "Hello"},
        stylesheets=[".card { width: 240px; height: 120px; color: black; }"],
        width=240,
        height=120,
    )

    html = render_template_to_html(
        "card.html.jinja",
        {"title": "Hello"},
        template_dir=tmp_path,
        filters={"reverse": reverse_filter},
    )

    assert png.startswith(b"\x89PNG")
    assert '<div class="card">olleH</div>' in html
    assert calls == ["Hello", "Hello"]


def test_template_renderer_accepts_full_jinja_environment() -> None:
    def is_featured(value: str) -> bool:
        return value == "Hello"

    environment = Environment(
        loader=DictLoader(
            {
                "card.html.jinja": """
                {% if title is featured %}
                <div class="card">{{ decorate(value=title).value | reverse }}</div>
                {% endif %}
                """,
            }
        ),
        autoescape=select_autoescape(
            enabled_extensions=("html", "xml", "jinja"),
            default_for_string=False,
        ),
        undefined=StrictUndefined,
    )
    environment.globals["decorate"] = dict
    environment.tests["featured"] = is_featured

    template_renderer = TemplateRenderer(
        environment=environment,
        filters={"reverse": lambda value: value[::-1]},
    )
    png = template_renderer.render(
        "card.html.jinja",
        {"title": "Hello"},
        stylesheets=[".card { width: 240px; height: 120px; color: black; }"],
        width=240,
        height=120,
    )
    html = render_template_to_html(
        "card.html.jinja",
        {"title": "Hello"},
        environment=environment,
    )

    assert template_renderer.environment is environment
    assert png.startswith(b"\x89PNG")
    assert '<div class="card">olleH</div>' in html


def test_render_template_to_document_snapshots_document_inputs() -> None:
    environment = Environment(
        loader=DictLoader(
            {
                "card.html.jinja": (
                    '<div class="card">{{ title | reverse }}</div>'
                    '<img src="memory://logo">'
                ),
            }
        ),
        autoescape=select_autoescape(("html", "xml", "jinja")),
    )
    resources = [ImageResource("memory://logo", b"logo")]
    stylesheets = [".card { width: 240px; height: 120px; }"]

    document = render_template_to_document(
        "card.html.jinja",
        {"title": "Hello"},
        environment=environment,
        filters={"reverse": lambda value: value[::-1]},
        resources=ResourceSet(resources),
        stylesheets=stylesheets,
        html_options=HtmlOptions(presets="none"),
    )
    resources.append(ImageResource("memory://later", b"later"))
    stylesheets.append(".card { width: 1px; }")

    assert isinstance(document, Document)
    assert document.html == ('<div class="card">olleH</div><img src="memory://logo">')
    assert document.resources.images == (ImageResource("memory://logo", b"logo"),)
    assert document.stylesheets == (".card { width: 240px; height: 120px; }",)
    assert document.html_options == HtmlOptions(presets="none")


def test_template_renderer_document_does_not_require_a_renderer() -> None:
    environment = Environment(
        loader=DictLoader({"text.html.jinja": "{{ value }}"}),
        autoescape=True,
    )
    template_renderer = TemplateRenderer(environment=environment)

    document = template_renderer.document(
        "text.html.jinja",
        {"value": "Prepared once"},
        stylesheets=["body { color: black; }"],
    )

    assert isinstance(document, Document)
    assert document.html == "Prepared once"
    assert document.stylesheets == ("body { color: black; }",)


def test_template_document_compiles_embedded_style_elements() -> None:
    environment = Environment(
        loader=DictLoader(
            {
                "card.html.jinja": """
                <style>
                  .card { width: 36px; height: 18px; }
                </style>
                <div class="card">{{ value }}</div>
                """,
            }
        ),
        autoescape=True,
    )
    document = TemplateRenderer(environment=environment).document(
        "card.html.jinja",
        {"value": "Styled"},
    )
    compiled = compile_document(document)
    measured = Renderer().measure(
        compiled,
        layout=LayoutOptions(width=None, height=None),
    )

    assert len(compiled.stylesheets) == 1
    assert (measured.width, measured.height) == (36, 18)


def test_template_renderer_rejects_ambiguous_environment_source(tmp_path) -> None:
    environment = Environment(
        loader=DictLoader({"card.html.jinja": "Hello"}),
        autoescape=True,
    )

    with pytest.raises(
        ValueError,
        match="template_dir and environment are mutually exclusive",
    ):
        TemplateRenderer(tmp_path, environment=environment)

    with pytest.raises(
        ValueError,
        match="template_dir and environment are mutually exclusive",
    ):
        render_template_to_html(
            "card.html.jinja",
            {},
            template_dir=tmp_path,
            environment=environment,
        )


def test_template_renderer_accepts_configured_renderer(tmp_path) -> None:
    template = tmp_path / "card.html.jinja"
    template.write_text(
        '<div class="card">{{ title }}</div>',
        encoding="utf-8",
    )
    renderer = Renderer(load_default_fonts=False)
    families = renderer.register_font(GEIST_FONT.read_bytes())

    png = TemplateRenderer(tmp_path, renderer=renderer).render(
        "card.html.jinja",
        {"title": "Configured font"},
        stylesheets=[
            ".card { width: 320px; height: 120px; color: black; font-size: 32px; }"
        ],
        width=320,
        height=120,
        font_families=families,
    )

    assert png.startswith(b"\x89PNG")
