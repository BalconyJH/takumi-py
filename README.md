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
- **Reuse and caching:** compiled nodes and stylesheets, budgeted image and font
  caches, and a configurable process-wide glyph cache.
- **Python typing:** PEP 561 support and native-extension stubs.

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
for runnable node, HTML, template, resource, measurement, and animation scripts.

## Documentation

The links below open the `dev` documentation built from `main`, in English and
[Simplified Chinese](https://balconyjh.github.io/takumi-py/zh/dev/). It can describe
changes that are not yet on PyPI. For a published package, select its version on the
[documentation site](https://balconyjh.github.io/takumi-py/).

| Task | Documentation |
| --- | --- |
| Render your first image | [Quickstart](https://balconyjh.github.io/takumi-py/dev/getting-started/quickstart/) |
| Choose inputs and outputs | [Rendering model](https://balconyjh.github.io/takumi-py/dev/guides/rendering/), [HTML and CSS](https://balconyjh.github.io/takumi-py/dev/guides/html/), [Output formats](https://balconyjh.github.io/takumi-py/dev/guides/output/) |
| Render dynamic content | [Jinja templates](https://balconyjh.github.io/takumi-py/dev/guides/templates/), [Animation](https://balconyjh.github.io/takumi-py/dev/guides/animation/) |
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
