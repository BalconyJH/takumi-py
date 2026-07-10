from pathlib import Path

from takumi_py import TemplateRenderer

EXAMPLES_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = EXAMPLES_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

renderer = TemplateRenderer(EXAMPLES_DIR / "templates")
stylesheets = [
    """
.card {
  width: 1200px;
  height: 630px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 64px;
  background: #111827;
  color: white;
}

.title {
  font-size: 72px;
  font-weight: 800;
}

.subtitle {
  margin-top: 24px;
  font-size: 36px;
  opacity: 0.8;
}
"""
]

png = renderer.render(
    "card.html.jinja",
    {
        "title": "takumi-py",
        "subtitle": "HTML / Jinja to image",
    },
    stylesheets=stylesheets,
    width=1200,
    height=630,
)

(OUTPUT_DIR / "template.png").write_bytes(png)
