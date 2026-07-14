from takumi_py import TemplateRenderer
from takumi_py.template import render_template_to_html


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

    def reverse_filter(value: str) -> str:
        return value[::-1]

    html = render_template_to_html(
        "card.html.jinja",
        {"title": "Hello"},
        template_dir=tmp_path,
        filters={"reverse": reverse_filter},
    )

    assert '<div class="card">olleH</div>' in html
