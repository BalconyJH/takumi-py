# takumi-py

`takumi-py` provides Python 3.10+ bindings for the Takumi Rust renderer.

> [!IMPORTANT]
> `takumi-py` is currently in a testing stage. APIs, wheel build targets, release automation, and exception types may still change while the Takumi core binding surface is completed; do not treat it as a stable production dependency yet.

The binding focuses on exposing practical Takumi core capabilities instead of copying the WASM/JS convenience layer. It currently supports:

- Node Tree, HTML string, and Jinja template rendering into image bytes.
- `RenderOptions`, including auto viewport, DPR, debug border, dithering, and `time_ms`.
- Custom fonts, per-render image resources, font fallback families, language hints, and SVG output.
- Rust-backed HTML parsing with configurable presets, Tailwind attribute mapping, and depth limits.
- Layout measurement with a typed measured node tree result.
- CSS and structured keyframe animation time sampling, sequence animation, and WebP/APNG/GIF animated encoders.
- PEP 561 typing, with `_core.pyi` covering the public native binding surface.

It intentionally does not include Playwright fallback, remote fetch, abort signal support, data URL convenience APIs, a Node.js sidecar, or Takumi internal layout/cache/glyph types.

## Development

```bash
uv sync --all-groups --all-extras
uv run maturin develop
make check
```

`make check` checks Ruff formatting and linting, `ty`, pytest with coverage,
and the Rust formatting/build checks.

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
"""

stylesheets = ["""
.card {
  width: 1200px;
  height: 630px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  background: #111827;
}
"""]

png = Renderer().render_html(
    html,
    stylesheets=stylesheets,
    width=1200,
    height=630,
)
```

HTML parsing is performed by Takumi's Rust parser. Use `HtmlOptions` when you
need to disable Chromium presets, read Tailwind classes from a custom attribute,
or cap parse depth:

```python
from takumi_py import HtmlOptions, Renderer

png = Renderer().render_html(
    '<div class="w-[1200px] h-[630px]"></div>',
    html_options=HtmlOptions(
        presets="none",
        tailwind_property="class",
        max_depth=64,
    ),
    width=None,
    height=None,
)
```

Compiled nodes expose Takumi's image URL discovery API:

```python
compiled = Renderer().compile_node(
    {"type": "image", "src": "https://example.com/logo.png"}
)

print(compiled.resource_urls())
```

`resource_urls()` follows Takumi's native image URL discovery semantics and
reports HTTP(S) image references from image nodes and styles. It does not fetch
those resources and does not report already-provided `memory://` resources or
byte buffers.

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
families = renderer.register_font(
    FontResource(
        Path("Inter-Regular.woff2").read_bytes(),
        name="Inter",
        weight=400,
        style="normal",
        generic_family="sans-serif",
    )
)

png = renderer.render_node(
    {"type": "image", "src": "memory://logo", "width": 128, "height": 128},
    width=128,
    height=128,
    images=[
        ImageResource(
            "memory://logo",
            Path("logo.svg").read_bytes(),
            cache="none",
        )
    ],
    font_families=families,
    lang="en",
)
```

`fetched_resources`, `load_font`, `load_fonts`, `persistent_images`,
`put_persistent_image`, and `clear_image_store` remain available as deprecated
compatibility shims for the v0.2 line. New code should pass `images` per render
and use `register_font` / `register_fonts`.

`register_font` returns the family names registered by Takumi. Pass that list as
`font_families` when you want a render call to use those families as its
fallback stack. `lang` accepts a BCP-47 language tag and is forwarded to
Takumi's locale-aware text shaping and line-breaking.

The render-level `lang` option is not injected as a node attribute, so it does
not make CSS `:lang()` selectors match. Takumi's selector matcher follows the
HTML language-determination model and walks actual node metadata or HTML
attributes. If CSS needs `:lang(...)`, set `lang` on the HTML element or node
that should establish the language:

```python
renderer.render_html(
    '<section lang="zh-Hant"><div class="headline">你好</div></section>',
    stylesheets=[
        '.headline:lang(zh-Hant) { font-family: "Noto Sans TC"; }',
    ],
)

renderer.render_node(
    {
        "type": "container",
        "lang": "ja",
        "children": [{"type": "text", "text": "こんにちは"}],
    },
    stylesheets=[':lang(ja) { font-family: "Noto Sans JP"; }'],
)
```

`ImageResource.cache` accepts `"auto"` or `"none"` and is forwarded to Takumi's
native image cache. Tuple resources like `("memory://logo", data)` remain
accepted and default to `"auto"`.

`FontResource` accepts Takumi v2 descriptor fields:

```python
FontResource(
    font_bytes,
    name="Inter",
    weight=700,
    style="italic",
    subset_of="Brand Sans",
    generic_family="sans-serif",
)
```

`style` uses CSS font-style syntax such as `"normal"`, `"italic"`, or
`"oblique 12deg"`. Invalid style values raise `FontError` during registration.

## SVG

```python
from takumi_py import Renderer

svg = Renderer().render_svg_html(
    """
    <div class="card">Hello</div>
    """,
    stylesheets=[".card { width: 1200px; height: 630px; color: black; }"],
    width=1200,
    height=630,
)
```

## Animation

```python
from takumi_py import AnimationScene, RenderOptions, Renderer

renderer = Renderer()

frame = renderer.render_html(
    """
    <div class="box"></div>
    """,
    stylesheets=["""
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
    """],
    width=64,
    height=64,
    time_ms=500,
)

structured_frame = renderer.render_node(
    {
        "type": "container",
        "className": "box",
    },
    stylesheets=[
        ".box { width: 64px; height: 64px; animation: fade 1000ms both; }"
    ],
    keyframes={
        "fade": {
            "from": {"opacity": 0},
            "to": {"opacity": 1},
        }
    },
    width=64,
    height=64,
    time_ms=500,
)

options_frame = renderer.render_node(
    {"type": "container", "className": "box"},
    stylesheets=[
        ".box { width: 64px; height: 64px; animation: fade 1000ms both; }"
    ],
    options=RenderOptions(
        width=64,
        height=64,
        time_ms=500,
        keyframes={
            "fade": {
                "from": {"opacity": 0},
                "to": {"opacity": 1},
            }
        },
    ),
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

## Takumi v2 Migration

`takumi-py` now targets Takumi v2. The main resource model changed from a
renderer-level global context to explicit per-render resources:

- Use `images=[ImageResource(...)]` instead of `fetched_resources`.
- Use `register_font` / `register_fonts` instead of `load_font` / `load_fonts`.
- Pass `font_families` and `lang` on render calls when you need deterministic
  font fallback or locale-aware shaping.
- Use HTML or node `lang` attributes, not the render-level `lang` option, when
  CSS selectors depend on `:lang(...)`.
- `ImageResource.cache` is forwarded to the native image cache for per-render,
  constructor, and deprecated persistent-image resources.
- `FontResource` accepts Takumi v2 descriptor fields: `name`, `weight`, `style`,
  `subset_of`, and `generic_family`.
- The built-in fallback font follows Takumi v2: a Latin Geist subset marked as
  last resort, so caller-registered fonts win ordinary fallback selection.
- `HtmlOptions` exposes Takumi's Rust `from_html` parser options.
- `CompiledNode.resource_urls()` wraps Takumi's image URL discovery and reports
  HTTP(S) image/style references for callers that want to prepare resources
  before rendering.
- Pass `keyframes=...` or `RenderOptions(keyframes=...)` to use Takumi's
  structured keyframe input without embedding `@keyframes` CSS text.
- WebP defaults to lossless when neither `quality` nor `lossless` is specified.
  Passing both `quality` and `lossless=True` is rejected.
- SVG output is available through `render_svg_node`, `render_svg_html`,
  `render_svg_template`, and `render_svg_compiled`.
- HTML parsing is handled by Takumi's Rust parser. Inline `style` attributes are
  parsed with the HTML payload; pass document-level CSS explicitly through
  `stylesheets=[...]` on HTML render, measure, SVG, or template calls.

Takumi v2 also changes several CSS defaults to be closer to the Web platform.
If an old image shifts, check for implicit defaults such as `position`,
border/outline width, `transform-origin`, `object-position`, and SVG
`currentColor` inheritance before treating it as a binding regression.

## Jinja

```python
from takumi_py import TemplateRenderer

renderer = TemplateRenderer("examples/templates")
stylesheets = ["""
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
"""]

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
```

## Release

Releases are handled by GitHub Actions. After the release commit is on `main`,
tag that commit with `v` plus the `project.version` value from
`pyproject.toml`, then push the tag to build wheels/sdist, publish to PyPI, and
create a GitHub Release.

```bash
git tag v0.2.0rc1 <commit-on-main>
git push origin main v0.2.0rc1
```

The tag must match `project.version` in `pyproject.toml`; for example, version
`0.2.0rc1` must be released as `v0.2.0rc1`.

## Test Coverage

The Python test suite covers static rendering, the HTML adapter, templates, core fixtures, options, measurement, resources, animation, typing artifacts, and generated HTML fixtures from the upstream Takumi core test suite.

## License

`takumi-py` is licensed under GPL-3.0-or-later. See [LICENSE](LICENSE).

This repository includes `takumi` as a git submodule. `takumi` is licensed
separately under `MIT OR Apache-2.0`; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
