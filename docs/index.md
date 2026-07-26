---
icon: lucide/image
---

# takumi-py

Python 3.10+ bindings for the [Takumi](https://github.com/kane50613/takumi) Rust
renderer. Turn typed node trees, HTML, or Jinja templates into raster images, SVG,
and animation without a browser runtime.

[Get started :material-arrow-right:](getting-started/index.md){ .md-button .md-button--primary }
[API reference](reference/index.md){ .md-button }

!!! warning "Testing-stage project"

    Public APIs, exception types, and release platforms may still change as Takumi
    core evolves. Read the
    [changelog](https://github.com/BalconyJH/takumi-py/blob/main/CHANGELOG.md)
    before upgrading.

## Choose your path

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **Render your first image**

    ---

    Install the wheel and create a PNG from HTML in a few lines.

    [:octicons-arrow-right-24: Quickstart](getting-started/quickstart.md)

-   :material-vector-square:{ .lg .middle } **Understand rendering**

    ---

    Choose between node trees, HTML, compiled content, raster output, and SVG.

    [:octicons-arrow-right-24: Rendering model](guides/rendering.md)

-   :material-folder-image:{ .lg .middle } **Manage resources**

    ---

    Register fonts, provide in-memory images, and control language-aware shaping.

    [:octicons-arrow-right-24: Fonts and images](guides/resources.md)

-   :material-movie-open-play:{ .lg .middle } **Build dynamic output**

    ---

    Render Jinja templates or encode WebP, APNG, and GIF animations.

    [:octicons-arrow-right-24: Templates](guides/templates.md) ·
    [:octicons-arrow-right-24: Animation](guides/animation.md)

</div>

## Minimal example

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
    ],  # (1)!
    width=1200,
    height=630,  # (2)!
)

Path("out.png").write_bytes(png)
```

1. Document-level CSS is an explicit input. Inline `style` attributes remain part
   of the HTML input.
2. An explicit viewport makes output dimensions deterministic. Either dimension
   can also be inferred from layout.

## Design boundary

The binding exposes practical Takumi core capabilities while keeping resource
ownership explicit: callers provide external fonts and image bytes, and the renderer
does not access the network. The package intentionally has no Playwright fallback,
remote fetcher, `AbortSignal` abstraction, data URL helper, or Node.js sidecar. See
the complete [support matrix](reference/support.md).
