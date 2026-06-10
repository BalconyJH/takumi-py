# takumi-py

`takumi-py` provides Python 3.10+ bindings for the Takumi Rust renderer.

> [!IMPORTANT]
> `takumi-py` is currently in a testing stage. APIs, wheel build targets, release automation, and exception types may still change while the Takumi core binding surface is completed; do not treat it as a stable production dependency yet.

The binding focuses on exposing practical Takumi core capabilities instead of copying the WASM/JS convenience layer. It currently supports:

- Node Tree, HTML string, and Jinja template rendering into image bytes.
- `RenderOptions`, including auto viewport, DPR, debug border, dithering, and `time_ms`.
- Custom fonts, a persistent image store, and per-render fetched resources.
- Layout measurement with a typed measured node tree result.
- CSS animation time sampling, sequence animation, and WebP/APNG/GIF animated encoders.
- PEP 561 typing, with `_core.pyi` covering the public native binding surface.

It intentionally does not include Playwright fallback, remote fetch, abort signal support, data URL convenience APIs, a Node.js sidecar, or Takumi internal layout/cache/glyph types.

## Development

```bash
uv sync --all-groups --all-extras
uv run maturin develop
make check
```

`make check` runs Ruff formatting and linting, `ty`, pytest with coverage, and
the Rust formatting/build checks.

## Install From Source

```bash
uv sync --all-groups --all-extras
uv run maturin develop
```

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

## Render Options

```python
from takumi_py import RenderOptions, Renderer

raw = Renderer().render_node(
    {
        "type": "container",
        "style": {
            "width": "240px",
            "height": "120px",
            "backgroundColor": "white",
        },
    },
    options=RenderOptions(
        width=None,
        height=None,
        format="raw",
        device_pixel_ratio=2.0,
        dithering="ordered-bayer",
    ),
)
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

## Measure

```python
from takumi_py import Renderer

measured = Renderer().measure_node(
    {
        "type": "container",
        "style": {"width": "240px", "height": "120px"},
        "children": [{"type": "text", "text": "Hello"}],
    },
    width=240,
    height=120,
)

print(measured.width, measured.height)
```

## Resources

```python
from pathlib import Path

from takumi_py import FontResource, ImageResource, Renderer

renderer = Renderer(load_default_fonts=False)
renderer.load_font(FontResource(Path("Inter-Regular.woff2").read_bytes()))
renderer.put_persistent_image(
    ImageResource("memory://logo", Path("logo.svg").read_bytes())
)

png = renderer.render_node(
    {"type": "image", "src": "memory://logo", "width": 128, "height": 128},
    width=128,
    height=128,
)
```

## Animation

```python
from takumi_py import AnimationScene, Renderer

renderer = Renderer()

frame = renderer.render_html(
    """
    <div class="box"></div>
    <style>
    @keyframes fade {
      from { opacity: 0; }
      to { opacity: 1; }
    }
    .box {
      width: 64px;
      height: 64px;
      background: black;
      animation: fade 1000ms both;
    }
    </style>
    """,
    width=64,
    height=64,
    time_ms=500,
)

webp = renderer.render_animation(
    [
        AnimationScene(
            {
                "type": "container",
                "style": {
                    "width": "100%",
                    "height": "100%",
                    "backgroundColor": "black",
                },
            },
            duration_ms=100,
        ),
        AnimationScene(
            {
                "type": "container",
                "style": {
                    "width": "100%",
                    "height": "100%",
                    "backgroundColor": "white",
                },
            },
            duration_ms=100,
        ),
    ],
    width=64,
    height=64,
    fps=20,
)
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

## Release

Releases are handled by GitHub Actions. After the release commit is on `main`, tag that commit with `vX.Y.Z` and push the tag to build wheels/sdist, publish to PyPI, and create a GitHub Release.

```bash
git tag v0.1.0 <commit-on-main>
git push origin main v0.1.0
```

The tag must match `project.version` in `pyproject.toml`; for example, version `0.1.0` must be released as `v0.1.0`.

## Test Coverage

The Python test suite covers static rendering, the HTML adapter, templates, core fixtures, options, measurement, resources, animation, typing artifacts, and generated HTML fixtures from the upstream Takumi core test suite.

## License

`takumi-py` is licensed under GPL-3.0-or-later. See [LICENSE](LICENSE).

This repository includes `takumi` as a git submodule. `takumi` is licensed
separately under `MIT OR Apache-2.0`; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
