from pathlib import Path

from takumi_py import Renderer


png = Renderer().render_node(
    {"type": "text", "text": "Hello from Python"},
    stylesheets=["span { font-size: 72px; color: black; }"],
    width=1200,
    height=630,
)

Path("out.png").write_bytes(png)
