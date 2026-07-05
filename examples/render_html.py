from pathlib import Path

from takumi_py import Renderer

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

html = """
<div class="card">
  <h1>Hello</h1>
  <p>Generated from HTML</p>
</div>
"""

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

h1 {
  font-size: 80px;
  margin: 0;
}
"""
]

(OUTPUT_DIR / "html.png").write_bytes(
    Renderer().render_html(
        html,
        stylesheets=stylesheets,
        width=1200,
        height=630,
    )
)
