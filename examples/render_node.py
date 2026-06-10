from pathlib import Path

from takumi_py import Renderer

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

png = Renderer().render_node(
    {"type": "text", "text": "Hello from Python"},
    stylesheets=["span { font-size: 72px; color: black; }"],
    width=1200,
    height=630,
)

(OUTPUT_DIR / "node.png").write_bytes(png)
