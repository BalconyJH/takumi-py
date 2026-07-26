# Fonts and images

!!! important "The renderer never fetches resources"

    Read external resources into `bytes` in application code and pass them explicitly
    at the rendering boundary. This keeps networking, authentication, retries, and
    persistent caching outside the renderer.

## Images

```python
from pathlib import Path

from takumi_py import ImageResource, Renderer

renderer = Renderer()
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
)
```

`ImageResource.cache` accepts `"auto"` or `"none"`. The tuple shorthand
`("memory://logo", data)` remains supported and uses `"auto"` by default.

## Fonts

```python
from pathlib import Path

from takumi_py import FontResource, Renderer

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
    {"type": "text", "text": "Hello"},
    width=320,
    height=160,
    font_families=families,
    lang="en",
)
```

`register_font` returns the family names actually registered by Takumi. Pass that
result to `font_families` to select a deterministic fallback stack for a render.
When supplied, `FontResource.weight` must be a finite number from 1 through 1000;
invalid overrides raise `ValueError` before font registration.

!!! warning "The bundled font is intentionally narrow"

    Built-in Geist is a Latin last-resort font. Register suitable fonts for non-Latin
    scripts, emoji, or brand glyphs; do not depend on fonts installed on the host OS.

## Language and CSS

The render-level `lang` option affects text shaping and line breaking, but it does not
write a node attribute and therefore does not activate CSS `:lang()`. Set `lang` on
the HTML or node when a selector must match:

```python
renderer.render_html(
    '<section lang="zh-Hant"><div class="headline">Typography</div></section>',
    stylesheets=[
        '.headline:lang(zh-Hant) { font-family: "Noto Sans TC"; }',
    ],
)
```

Render-level `lang` must be a valid BCP-47 language tag. Every render, measure, SVG,
and animation entry point rejects an invalid tag with `ValueError`.

## Lifecycle

| Resource | Preferred lifetime | API |
| --- | --- | --- |
| Font | Renderer lifetime | `register_font` or `register_fonts` |
| Image | One render | `images=[ImageResource(...)]` |

??? info "Compatibility APIs"

    `load_font(s)`, `fetched_resources`, and the persistent image APIs remain only as
    compatibility shims. New code should not expand its dependency on those deprecated
    interfaces.
