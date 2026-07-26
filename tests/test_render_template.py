from pathlib import Path

from jinja2 import DictLoader, Environment, StrictUndefined, select_autoescape
import pytest

from takumi_py import Renderer, TemplateRenderer
from takumi_py.template import render_template_to_html

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
