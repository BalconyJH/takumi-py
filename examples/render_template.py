from pathlib import Path

from takumi_py import TemplateRenderer


renderer = TemplateRenderer("examples/templates")
png = renderer.render(
    "card.html.jinja",
    {
        "title": "takumi-py",
        "subtitle": "HTML / Jinja to image",
    },
    width=1200,
    height=630,
)

Path("out.png").write_bytes(png)
