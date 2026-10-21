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

### Raw RGBA pixels

Use `RawRgbaImage` when pixels are already decoded as row-major RGBA. This avoids an
image codec round trip:

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

The byte length must be exactly `width * height * 4`. Data uses straight alpha by
default. Set `premultiplied=True` only for pixels whose RGB channels already include
the alpha multiplication.

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

### Font subsets

Register each subset of a family under the same `name`, with the `unicode_range` its
`@font-face` declares. A subset serves only the codepoints in its inclusive
`(start, end)` ranges, as in Chrome, so text picks the right file per character:

```python
renderer.register_fonts(
    [
        FontResource(latin, name="Inter", unicode_range=[(0x0000, 0x00FF)]),
        FontResource(cyrillic, name="Inter", unicode_range=[(0x0400, 0x045F)]),
    ]
)
```

Each range must satisfy `0 <= start <= end <= 0x10FFFF`; anything else raises
`ValueError`. `FontResource.subset_of` is deprecated: Takumi now only uses it as the
family name, in place of `name`.

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

## Cache budgets

`Renderer(cache_max_bytes=...)` sets the byte budget shared by that renderer's
decoded images, scaled image variants, SVG rasters, and related render resources.
Images embedded as `data:` URIs decode through the same cache, so a template that
inlines its logo decodes it once per renderer rather than on every render. The Takumi
default is 64 MiB; pass `0` to disable retention.

Glyph masks and outlines use a separate process-wide cache with an 8 MiB default.
For CJK-heavy workloads, configure it before the first render in the process:

```python
from takumi_py import Renderer, set_glyph_cache_max_bytes

set_glyph_cache_max_bytes(32 * 1024 * 1024)
renderer = Renderer(cache_max_bytes=64 * 1024 * 1024)
```

Changing the glyph budget after glyph rendering begins does not resize the existing
process-wide caches.

## Lifecycle

| Resource | Preferred lifetime | API |
| --- | --- | --- |
| Font | Renderer lifetime | `register_font` or `register_fonts` |
| Image | One render | `images=[ImageResource(...)]` |

??? info "Compatibility APIs"

    `load_font(s)`, `fetched_resources`, and the persistent image APIs remain only as
    compatibility shims. New code should not expand its dependency on those deprecated
    interfaces.
