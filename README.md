# takumi-py

**English** | [简体中文](https://github.com/BalconyJH/takumi-py/blob/main/README.zh-CN.md)

Python 3.10+ bindings for the [Takumi](https://github.com/kane50613/takumi) Rust
renderer. Render node trees, HTML, and Jinja templates to PNG, JPEG, WebP, ICO, raw
RGBA, SVG, and WebP, APNG, or GIF animations, without a browser runtime.

> [!IMPORTANT]
> `takumi-py` is in a testing stage. APIs, wheel build targets, release automation, and
> exception types may still change while the Takumi core binding surface is completed;
> do not treat it as a stable production dependency yet.

## Documentation

The documentation site is [balconyjh.github.io/takumi-py](https://balconyjh.github.io/takumi-py/),
in English and [Simplified Chinese](https://balconyjh.github.io/takumi-py/zh/). Its
sources live in [`docs/`](https://github.com/BalconyJH/takumi-py/tree/main/docs):

- [Quickstart](https://github.com/BalconyJH/takumi-py/blob/main/docs/en/getting-started/quickstart.md)
- [Guides](https://github.com/BalconyJH/takumi-py/blob/main/docs/en/guides/index.md):
  rendering model, HTML and CSS, output formats, fonts and images, Jinja templates,
  and animation
- [Support matrix](https://github.com/BalconyJH/takumi-py/blob/main/docs/en/reference/support.md)
  and [exceptions](https://github.com/BalconyJH/takumi-py/blob/main/docs/en/reference/exceptions.md)
- Migration guides for [Takumi v2](https://github.com/BalconyJH/takumi-py/blob/main/docs/en/migration/takumi-v2.md)
  and [Takumi 2.17](https://github.com/BalconyJH/takumi-py/blob/main/docs/en/migration/takumi-2.17.md)

## Installation

```bash
uv add takumi-py
```

Published `cp310-abi3` wheels cover Linux x86_64 and aarch64, macOS on Apple Silicon,
and Windows x64. Other platforms build from the source distribution, which needs
Rust 1.91 or later. See
[Installation](https://github.com/BalconyJH/takumi-py/blob/main/docs/en/getting-started/installation.md)
for source checkouts.

## Quickstart

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

Runnable scripts for every input and output live in
[`examples/`](https://github.com/BalconyJH/takumi-py/tree/main/examples).

## Features

- Node trees, HTML parsed by Takumi's Rust parser, and Jinja templates with custom
  filters or a caller-owned environment.
- Raster output with encoder options, device pixel ratio, dithering, and raw RGBA;
  SVG output; and layout measurement as a typed tree.
- Caller-supplied fonts with `unicode-range` subsets, per-render images, raw RGBA
  image sources, font fallback stacks, and language-aware shaping.
- CSS and structured keyframe sampling, plus WebP, APNG, and GIF animation encoding.
- Renderer-local resource caches and a process-wide glyph cache budget.
- PEP 561 typing, with `_core.pyi` covering the native extension.

The binding keeps resource ownership explicit: it never fetches over the network and
ships no Playwright fallback, abort-signal protocol, data URL helpers, or Node.js
sidecar. The [support matrix](https://github.com/BalconyJH/takumi-py/blob/main/docs/en/reference/support.md)
lists every exclusion.

## Development

```bash
git clone --recurse-submodules https://github.com/BalconyJH/takumi-py.git
cd takumi-py
uv sync --all-groups --all-extras
uv run maturin develop
make check
```

The [development guide](https://github.com/BalconyJH/takumi-py/blob/main/docs/en/maintainers/development.md)
covers checks, tests, and Takumi upgrades, and the
[release guide](https://github.com/BalconyJH/takumi-py/blob/main/docs/en/maintainers/releasing.md)
covers the automated release pipeline.

## License

`takumi-py` is licensed under GPL-3.0-or-later. See
[LICENSE](https://github.com/BalconyJH/takumi-py/blob/main/LICENSE).

This repository includes `takumi` as a git submodule. `takumi` is licensed separately
under `MIT OR Apache-2.0`; see
[THIRD_PARTY_NOTICES.md](https://github.com/BalconyJH/takumi-py/blob/main/THIRD_PARTY_NOTICES.md).
