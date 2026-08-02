# takumi-py

`takumi-py` provides Python 3.10+ bindings for the Takumi Rust renderer.

The documentation source lives in
[`docs/`](https://github.com/BalconyJH/takumi-py/blob/main/docs/index.md) and is
built with [Zensical](https://zensical.org/). Use `make docs-serve` for local
preview.

> [!IMPORTANT]
> `takumi-py` is currently in a testing stage. APIs, wheel build targets, release automation, and exception types may still change while the Takumi core binding surface is completed; do not treat it as a stable production dependency yet.

The binding focuses on exposing practical Takumi core capabilities instead of copying the WASM/JS convenience layer. It currently supports:

- Node Tree, HTML string, and Jinja template rendering into image bytes.
- `RenderOptions`, including auto viewport, DPR, debug border, dithering, and `time_ms`.
- Custom fonts, per-render image resources, font fallback families, language hints, and SVG output.
- Raw row-major RGBA image sources and configurable resource and glyph cache budgets.
- Rust-backed HTML parsing with configurable presets, Tailwind attribute mapping, and depth limits.
- Layout measurement with a typed measured node tree result.
- CSS and structured keyframe animation time sampling, sequence animation, and WebP/APNG/GIF animated encoders.
- PEP 561 typing, with `_core.pyi` covering the public native binding surface.

It intentionally does not include Playwright fallback, remote fetch, abort signal support, data URL convenience APIs, a Node.js sidecar, or Takumi internal layout/cache/glyph types.

## Development

```bash
git submodule update --init --recursive
uv sync --all-groups --all-extras
uv run maturin develop
make check
```

`make check` checks Ruff formatting and linting, `ty`, native stub/runtime parity
with `mypy.stubtest`, pytest with coverage, and the Rust formatting/build checks.

## Install From Source

```bash
git clone --recurse-submodules https://github.com/BalconyJH/takumi-py.git
cd takumi-py
uv sync --all-groups --all-extras
uv run maturin develop
```

For an existing non-recursive checkout, run
`git submodule update --init --recursive` before syncing dependencies.

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
Takumi's locale-aware text shaping and line-breaking. Invalid render-level language
tags raise `ValueError` consistently across render, measure, SVG, and animation APIs.

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
native resource cache. Tuple resources like `("memory://logo", data)` remain
accepted and default to `"auto"`.

Image nodes can also consume raw row-major RGBA pixels without image decoding:

```python
from takumi_py import RawRgbaImage, Renderer

source: RawRgbaImage = {
    "width": 2,
    "height": 2,
    "data": bytes([255, 0, 0, 128] * 4),
}

png = Renderer().render_node(
    {"type": "image", "src": source, "width": 2, "height": 2},
    width=2,
    height=2,
)
```

The byte length must equal `width * height * 4`. Input uses straight alpha by
default; set `premultiplied=True` only when the RGB channels are already
multiplied by alpha.

`Renderer(cache_max_bytes=...)` controls the renderer-local resource cache for
decoded images, scaled rasters, SVG rasters, and related render resources. The
default is 16 MiB; `0` disables retention. Glyph masks and outlines use a separate
process-wide cache. Call `set_glyph_cache_max_bytes(...)` before the process's first
render when the default 8 MiB glyph budget is too small for the workload.

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
When provided, `weight` must be a finite number from 1 through 1000; invalid weight
overrides raise `ValueError`.

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

Animation scene and raw-frame `duration_ms` values must be positive. A zero duration
raises `ValueError` instead of producing an empty or silently skipped frame.

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
- Image nodes accept `RawRgbaImage` sources for already decoded row-major RGBA
  pixels.
- `Renderer(cache_max_bytes=...)` controls its resource cache, while
  `set_glyph_cache_max_bytes(...)` controls the process-wide glyph cache before
  first use.
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
from pathlib import Path

from takumi_py import FontResource, Renderer, TemplateRenderer


def uppercase(value: str) -> str:
    return value.upper()


configured_renderer = Renderer(load_default_fonts=False)
families = configured_renderer.register_font(
    FontResource(
        Path("Inter-Regular.woff2").read_bytes(),
        name="Inter",
        generic_family="sans-serif",
    )
)
renderer = TemplateRenderer(
    "examples/templates",
    filters={"uppercase": uppercase},
    renderer=configured_renderer,
)
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
    font_families=families,
    width=1200,
    height=630,
)
```

Registered filters are available to templates in the renderer's environment;
for example, `{{ title | uppercase }}` uses the filter above. Injecting the
configured `Renderer` preserves its registered font state for template renders.
The standalone `render_template_to_html` helper accepts the same `filters`
mapping when only the rendered HTML string is needed.

For complete Jinja control, pass `environment=...` instead of `template_dir`.
The injected `jinja2.Environment` keeps its loader, globals, tests, extensions,
undefined-value policy, bytecode cache, and other native configuration. The
optional `filters` mapping is then added to that same environment, and
`renderer.environment` exposes the exact instance in use.

## Release

The version contract, exact-commit CI gates, automatic tag and publish pipeline,
external repository settings, and failure recovery rules are maintained in the
[release guide](https://github.com/BalconyJH/takumi-py/blob/main/docs/maintainers/releasing.md).

## Test Coverage

The Python test suite covers static rendering, the HTML adapter, templates, core fixtures, options, measurement, resources, animation, typing artifacts, and generated HTML fixtures from the upstream Takumi core test suite.

## License

`takumi-py` is licensed under GPL-3.0-or-later. See
[LICENSE](https://github.com/BalconyJH/takumi-py/blob/main/LICENSE).

This repository includes `takumi` as a git submodule. `takumi` is licensed
separately under `MIT OR Apache-2.0`; see
[THIRD_PARTY_NOTICES.md](https://github.com/BalconyJH/takumi-py/blob/main/THIRD_PARTY_NOTICES.md).
