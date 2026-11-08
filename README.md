# takumi-py

**English** | [简体中文](https://github.com/BalconyJH/takumi-py/blob/main/README.zh-CN.md)

Render social cards, reports, and other images from Python using the
[Takumi](https://github.com/kane50613/takumi) Rust renderer. Turn node trees, HTML,
or Jinja templates into raster images, SVG, and animations without a browser runtime.

Requires Python 3.11+. Published versions are listed on
[PyPI](https://pypi.org/project/takumi-py/) and in
[GitHub Releases](https://github.com/BalconyJH/takumi-py/releases).

## Features

- **Three input models:** typed node trees, HTML parsed in Rust, and Jinja templates
  with custom filters or a caller-owned environment.
- **Static output:** PNG, JPEG, WebP, ICO, raw RGBA, and SVG; layout measurement
  returns a typed tree.
- **Animation:** sample CSS or structured keyframes, render scene sequences, or
  encode raw frames as WebP, APNG, and GIF.
- **Fonts and images:** explicit image bytes, raw RGBA sources, font subsets,
  fallback stacks, and language-aware text shaping.
- **Optional math (next-major preview):** explicit TeX to self-contained SVG through
  `takumi_py.math`, with bundled fonts and resource-owning document fragments.
- **Reuse and caching:** compiled nodes and stylesheets, budgeted image and font
  caches, and a configurable process-wide glyph cache.
- **Python typing:** PEP 561 support and native-extension stubs.

## Current limitations

Takumi implements its own HTML/CSS layout model. Existing web pages can need changes
before rendering correctly; a successful render does not guarantee browser-equivalent
layout or complete content.

### Mathematical formulas

`takumi_py.math` is a next-major preview for explicitly converting TeX expressions to
self-contained SVG. The math extra is not available from the current PyPI release;
install it from a current source checkout as described under
[Installation](#installation). Every wheel built from this preview includes the pinned MathJax
4.1.3 runtime and local SVG font data (about 11.5 MB uncompressed), while the extra
adds `mini-racer==0.14.1` without downloading assets at render time.

The optional runtime has a narrower Linux floor than the core extension: its glibc
wheel requires 2.27, while the core baseline is 2.17. Only macOS arm64 execution is
currently proven; the remaining wheel targets in this preview still require CI
verification.

The typesetter launches a supervised Python worker on the first cache miss and uses an
embedded V8 runtime in that child process. It does not use Node.js, a browser, a remote
rendering service, or network access. Reaching the deadline terminates the worker, with
a bounded cleanup grace after that deadline; the next conversion starts with a fresh
worker. Formula output can travel with a `Document` through `MathSvg.to_fragment()` and
`ResourceSet`.

The initial path supports base TeX, AMS math and align environments, matrices, cases,
resizable delimiters, color, `\cancel`, `\bbox`, and opt-in mhchem. It does not scan
Markdown or HTML, and it does not promise complete LaTeX, persistent macros, MathML, or
CJK text such as `\text{中文}`. See
[Math rendering](https://balconyjh.github.io/takumi-py/dev/guides/math/) for the
runtime, lifecycle, limits, and supported subset.

### Other limitations

| Area | Current behavior | Application-side approach |
| --- | --- | --- |
| Markdown | No Markdown parser or extension processing. | Convert Markdown to HTML first and supply its CSS; select and typeset formulas explicitly with `takumi_py.math`. |
| JavaScript and browser applications | `<script>` elements are dropped. No browser DOM, client-side application execution, page navigation, or browser fallback. | Provide the final static HTML, nodes, or images. |
| HTML and CSS | `<style>` and `<link>` elements are ignored; inline `style` attributes work. Unsupported stylesheet declarations are skipped by HTML/template entry points and rejected by strict node entry points. | Pass document CSS through `stylesheets` and check the actual output. |
| External resources | Image URLs and external stylesheets are not downloaded; the renderer provides no HTTP client. | Fetch or read resources in application code, pass image bytes through `images`, and supply CSS explicitly. |
| Font coverage | The bundled Geist fallback covers Latin text. Host system fonts are not automatically loaded. | Register suitable fonts for CJK, emoji, and other scripts. |
| SVG containing HTML | SVG rasterization does not render HTML inside `<foreignObject>`. | Convert embedded HTML to SVG paths or a raster image before passing it in. |
| PDF and pagination | The Python API has no PDF output or automatic pagination. | Render images or SVG and use a separate document/PDF tool. |
| Async and cancellation | Rendering calls are synchronous, with no built-in cancellation or interruptible timeout API. | Schedule work in the application; use process isolation when an in-flight render must be forcibly stopped. |

See [HTML and CSS](https://balconyjh.github.io/takumi-py/dev/guides/html/)
for parsing behavior and the
[support matrix](https://balconyjh.github.io/takumi-py/dev/reference/support/)
for platform support and API boundaries.

## Installation

```bash
uv add takumi-py
```

Or install into an existing Python environment with pip:

```bash
python -m pip install takumi-py
```

These commands install the latest published release. To use the current source,
follow [Development](#development).

For the next-major formula preview, use a current source checkout and install the
optional math runtime:

```bash
uv sync --extra math
```

Locally built preview wheels also accept the `math` extra. Do not use
`takumi-py[math]` with PyPI until that extra appears in a published release.

Installing a compatible wheel does not require Rust. Source builds require Rust 1.91
or later and a native build toolchain. See the
[support matrix](https://balconyjh.github.io/takumi-py/dev/reference/support/)
for platform compatibility and the
[installation guide](https://balconyjh.github.io/takumi-py/dev/getting-started/installation/)
for source builds.

## Quickstart

Save this as `render.py` and run it with `uv run python render.py` (or
`python render.py` in the environment where you installed the package):

```python
from pathlib import Path

from takumi_py import Renderer

png = Renderer().render_html(
    '<main class="card">Hello from Python</main>',
    stylesheets=[
        """
        .card {
          width: 1200px;
          height: 630px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          background: #111827;
          font-size: 72px;
        }
        """
    ],
    width=1200,
    height=630,
)

Path("out.png").write_bytes(png)
```

The example writes a 1200 by 630 PNG to `out.png`.

- Pass document-level CSS through `stylesheets`. Inline `style` attributes work,
  but `<style>` elements in the HTML are ignored.
- The bundled Geist fallback covers Latin text. Register suitable fonts for Chinese,
  Japanese, Korean, emoji, or other scripts.
- The renderer never fetches resources over the network. Supply image bytes through
  `images` and register fonts on the renderer.

See [Fonts and images](https://balconyjh.github.io/takumi-py/dev/guides/resources/)
for resource setup, and [`examples/`](https://github.com/BalconyJH/takumi-py/tree/main/examples)
for runnable node, HTML, template, resource, measurement, animation, and math scripts.

## Documentation

The links below open the `dev` documentation built from `main`, in English and
[Simplified Chinese](https://balconyjh.github.io/takumi-py/zh/dev/). It can describe
changes that are not yet on PyPI. For a published package, select its version on the
[documentation site](https://balconyjh.github.io/takumi-py/).

The `Document` / `CompiledDocument` API and the new `Renderer.render`, `measure`, and
`render_svg` methods are a next-major preview. The quickstart above uses the existing
`render_html` API; preview documentation does not mean those newer APIs are available
in the published package.

| Task | Documentation |
| --- | --- |
| Render your first image | [Quickstart](https://balconyjh.github.io/takumi-py/dev/getting-started/quickstart/) |
| Choose inputs and outputs | [Rendering model](https://balconyjh.github.io/takumi-py/dev/guides/rendering/), [HTML and CSS](https://balconyjh.github.io/takumi-py/dev/guides/html/), [Output formats](https://balconyjh.github.io/takumi-py/dev/guides/output/) |
| Render dynamic content | [Jinja templates](https://balconyjh.github.io/takumi-py/dev/guides/templates/), [Animation](https://balconyjh.github.io/takumi-py/dev/guides/animation/) |
| Render mathematical formulas | [Math rendering](https://balconyjh.github.io/takumi-py/dev/guides/math/) |
| Look up signatures and behavior | [API reference](https://balconyjh.github.io/takumi-py/dev/reference/), [Exceptions](https://balconyjh.github.io/takumi-py/dev/reference/exceptions/) |
| Check compatibility and API policy | [Support matrix](https://balconyjh.github.io/takumi-py/dev/reference/support/) |

Documentation sources live in [`docs/`](https://github.com/BalconyJH/takumi-py/tree/main/docs).
English is the source of truth; Chinese mirrors its pages and code samples.

## Upgrading to 0.4.0

- Python 3.11+ is required; Python 3.10 support is removed.
- Replace the resource APIs deprecated in 0.2.0 with per-render `images` and
  `register_font` / `register_fonts`.
- Review font subsets, dithering, animation frame-rate limits, and rendering changes
  when moving from Takumi 2.5 to 2.17.

Follow the [Takumi v2 migration](https://balconyjh.github.io/takumi-py/dev/migration/takumi-v2/)
and [Takumi 2.17 migration](https://balconyjh.github.io/takumi-py/dev/migration/takumi-2.17/),
and read the [changelog](https://github.com/BalconyJH/takumi-py/blob/main/CHANGELOG.md).

## Development

Install `uv` and Rust, then clone with the Takumi submodule:

```bash
git clone --recurse-submodules https://github.com/BalconyJH/takumi-py.git
cd takumi-py
make sync
make check
make docs-build
```

`make check` runs linting, type checks, Python tests, and Rust checks, rebuilding the
native extension for runtime checks.
Use `make docs-serve` or `make docs-serve-zh` to preview documentation locally.
The [development guide](https://balconyjh.github.io/takumi-py/dev/maintainers/development/)
covers checks and Takumi upgrades; the
[release guide](https://balconyjh.github.io/takumi-py/dev/maintainers/releasing/)
describes the automated release pipeline.

## License

`takumi-py` is licensed under GPL-3.0-or-later. See
[LICENSE](https://github.com/BalconyJH/takumi-py/blob/main/LICENSE).

This repository includes `takumi` as a git submodule. `takumi` is licensed separately
under `MIT OR Apache-2.0`; see
[THIRD_PARTY_NOTICES.md](https://github.com/BalconyJH/takumi-py/blob/main/THIRD_PARTY_NOTICES.md).
