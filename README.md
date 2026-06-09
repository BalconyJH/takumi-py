# takumi-py

`takumi-py` provides Python 3.10+ bindings for the Takumi Rust renderer.
The current implementation covers static Node Tree, HTML string, and Jinja
template rendering into image bytes.

This package intentionally does not include Playwright fallback, remote resource
fetching, complex resource lifecycle management, or a Node.js sidecar.

## Development

```bash
uv sync --all-groups --all-extras
uv run maturin develop
make check
```

`make check` runs Ruff formatting and linting, `ty`, pytest with coverage, and
the Rust formatting/build checks.

## Node Tree

```python
from pathlib import Path

from takumi_py import Renderer

renderer = Renderer()

png = renderer.render_node(
    {"type": "text", "text": "Hello from Python"},
    stylesheets=["span { font-size: 72px; color: black; }"],
    width=1200,
    height=630,
)

Path("out.png").write_bytes(png)
```

## HTML

```python
from takumi_py import Renderer

html = """
<div class="card">
  <h1>Hello</h1>
</div>

<style>
.card {
  width: 1200px;
  height: 630px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  background: #111827;
}
</style>
"""

png = Renderer().render_html(html, width=1200, height=630)
```

## Jinja

```python
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
```

## Test Coverage

The Python test suite includes generated HTML fixtures from the upstream Takumi
core test suite. These tests exercise the Python HTML adapter against the same
static fixture corpus while keeping known CSS parser limitations explicit.