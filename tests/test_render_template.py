from takumi_py import TemplateRenderer


def test_template_renderer_loads_template_dir(tmp_path) -> None:
    template = tmp_path / "card.html.jinja"
    template.write_text(
        """
        <div class="card">{{ title }}</div>
        <style>
        .card {
          width: 240px;
          height: 120px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 32px;
          color: black;
        }
        </style>
        """,
        encoding="utf-8",
    )

    png = TemplateRenderer(tmp_path).render(
        "card.html.jinja",
        {"title": "Hello"},
        width=240,
        height=120,
    )

    assert png.startswith(b"\x89PNG")
