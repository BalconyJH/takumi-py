from pathlib import Path

from takumi_py import NodeInput, Renderer, RenderOptions

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

node: NodeInput = {
    "type": "container",
    "style": {
        "width": "480px",
        "height": "240px",
        "display": "flex",
        "alignItems": "center",
        "justifyContent": "center",
        "backgroundColor": "white",
    },
    "children": [
        {
            "type": "text",
            "text": "Measured layout",
            "style": {"fontSize": "48px", "color": "black"},
        }
    ],
}

renderer = Renderer()
options = RenderOptions(
    width=None,
    height=None,
    device_pixel_ratio=2.0,
    dithering="ordered-bayer",
)

measured = renderer.measure_node(node, options=options)
if measured.width <= 0 or measured.height <= 0:
    raise RuntimeError("measured node size must be positive")

(OUTPUT_DIR / "options-measure.png").write_bytes(
    renderer.render_node(node, options=options)
)
