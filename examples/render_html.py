from pathlib import Path

from takumi_py import Renderer


html = """
<div class="card">
  <h1>Hello</h1>
  <p>Generated from HTML</p>
</div>

<style>
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
</style>
"""

Path("out.png").write_bytes(Renderer().render_html(html, width=1200, height=630))
