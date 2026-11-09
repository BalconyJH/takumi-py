from pathlib import Path

from takumi_py import (
    ImageResource,
    LayoutOptions,
    Renderer,
    TemplateRenderer,
    compile_document,
)

EXAMPLES_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = EXAMPLES_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

COVER_SVG = b"""
<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240">
  <rect width="240" height="240" rx="36" fill="#0f172a"/>
  <circle cx="120" cy="120" r="76" fill="#38bdf8"/>
  <path d="M70 120h100M120 70v100" stroke="white" stroke-width="18"/>
</svg>
"""

stylesheets = [
    """
.card {
  width: 640px;
  height: 360px;
  display: flex;
  align-items: center;
  gap: 40px;
  padding: 52px;
  box-sizing: border-box;
  background: linear-gradient(135deg, #f8fafc, #dbeafe);
  color: #0f172a;
}

.cover {
  width: 180px;
  height: 180px;
  flex: none;
}

.eyebrow {
  margin: 0 0 12px;
  color: #0369a1;
  font-size: 18px;
  font-weight: 700;
  text-transform: uppercase;
}

h1 {
  margin: 0;
  font-size: 52px;
  line-height: 1.05;
}

.subtitle {
  margin: 20px 0 0;
  color: #334155;
  font-size: 24px;
}
"""
]

template = TemplateRenderer(EXAMPLES_DIR / "templates")
document = template.document(
    "static_card.html.jinja",
    {
        "title": "One layout, many files",
        "subtitle": "Compile once, rasterize once, encode repeatedly.",
    },
    resources=[
        ImageResource("https://assets.example/cover.svg", COVER_SVG, cache="none"),
    ],
    stylesheets=stylesheets,
)

compiled = compile_document(document)
assert compiled.resource_urls() == ("https://assets.example/cover.svg",)
assert compiled.missing_resources() == ()

image = Renderer().rasterize(
    compiled,
    layout=LayoutOptions(width=640, height=360),
    scale=2,
)

png = image.encode("png")
webp = image.encode("webp", quality=90)
rgba = image.tobytes()

assert image.size == (1280, 720)
assert len(rgba) == image.nbytes == image.stride * image.height

(OUTPUT_DIR / "static.png").write_bytes(png)
(OUTPUT_DIR / "static.webp").write_bytes(webp)
