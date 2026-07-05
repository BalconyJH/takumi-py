from pathlib import Path

from takumi_py import ImageResource, Renderer

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

LOGO_SVG = b"""
<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160">
  <rect width="160" height="160" rx="24" fill="#111827"/>
  <circle cx="80" cy="80" r="48" fill="#38bdf8"/>
  <text x="80" y="94" text-anchor="middle" font-size="42" fill="white">T</text>
</svg>
"""

renderer = Renderer()

png = renderer.render_node(
    {
        "type": "container",
        "style": {
            "width": "420px",
            "height": "220px",
            "display": "flex",
            "alignItems": "center",
            "gap": "32px",
            "padding": "32px",
            "backgroundColor": "white",
        },
        "children": [
            {
                "type": "image",
                "src": "memory://takumi-logo",
                "width": 160,
                "height": 160,
            },
            {
                "type": "text",
                "text": "Per-render image",
                "style": {"fontSize": "36px", "color": "black"},
            },
        ],
    },
    width=None,
    height=None,
    images=[ImageResource("memory://takumi-logo", LOGO_SVG, cache="none")],
)

(OUTPUT_DIR / "resources.png").write_bytes(png)
