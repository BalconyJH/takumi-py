from pathlib import Path

from takumi_py import TemplateRenderer

EXAMPLES_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = EXAMPLES_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

renderer = TemplateRenderer(EXAMPLES_DIR / "templates")
png = renderer.render(
    "card.html.jinja",
    {
        "title": "takumi-py",
        "subtitle": "HTML / Jinja to image",
    },
    width=1200,
    height=630,
)

(OUTPUT_DIR / "template.png").write_bytes(png)
