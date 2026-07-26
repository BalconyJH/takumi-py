# Quickstart

This program renders HTML with an explicit stylesheet and writes a PNG:

```python
from pathlib import Path

from takumi_py import Renderer

renderer = Renderer()
png = renderer.render_html(
    '<section class="card"><h1>Hello</h1></section>',
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
        }
        h1 { font-size: 72px; }
        """
    ],  # (1)!
    width=1200,
    height=630,  # (2)!
)

Path("out.png").write_bytes(png)
```

1. Stylesheets are passed as document-level render inputs, rather than hidden global
   renderer state.
2. Fix both viewport dimensions when the output must be repeatable across calls.

## Choose an input model

<div class="grid cards" markdown>

- **HTML already exists** — use `render_html`.
- **Content is structured data** — use `render_node`.
- **The same structure is rendered repeatedly** — call `compile_node` or
  `compile_html`, then follow the [compiled rendering contract](../guides/rendering.md#compile-and-reuse).
- **Templates live on disk** — use `TemplateRenderer`.

</div>

## Next steps

??? question "The result does not look right"

    Check these boundaries first:

    1. Are the viewport dimensions explicit or intentionally inferred?
    2. Was document-level CSS passed through `stylesheets`?
    3. Were the fonts required by the text registered?

    Continue with the [rendering model](../guides/rendering.md) and
    [resource guide](../guides/resources.md) for the underlying contracts.
