# Fonts and images

!!! important "The renderer never fetches resources"

    Read external resources into `bytes` in application code and pass them explicitly
    at the rendering boundary. This keeps networking, authentication, retries, and
    persistent caching outside the renderer.

## Images

Image nodes refer to images by `src`. Supply the bytes for each `src` through the
per-render `images` option:

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

`ImageResource.cache` accepts `"auto"` or `"none"` and is forwarded to the renderer's
resource cache. The tuple shorthand `("memory://logo", data)` remains supported and
uses `"auto"`. Images embedded as `data:` URIs need no resource at all.

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

### Owned raster images { #owned-raster-images }

`Renderer.rasterize` returns a `RasterImage` that owns the completed native bitmap.
Unlike a second `render` call, encoding another format does not repeat layout,
resource decoding, or drawing:

```python
from takumi_py import Document, LayoutOptions, Renderer, compile_document

document = Document.from_node(
    {
        "type": "container",
        "style": {
            "width": "320px",
            "height": "180px",
            "backgroundColor": "#111827",
        },
    }
)
compiled = compile_document(document)

image = Renderer().rasterize(
    compiled,
    layout=LayoutOptions(width=320, height=180),
    scale=2,
)

png = image.encode("png")
webp = image.encode("webp", quality=85)
raw_rgba = image.tobytes()

assert image.size == (640, 360)
assert image.stride == image.width * 4
assert len(raw_rgba) == image.nbytes == image.stride * image.height
```

The bitmap is tightly packed, row-major RGBA8 with straight alpha. Its native storage
does not depend on the renderer or document that produced it. `data` and `tobytes()`
copy the pixels to Python bytes. `to_raw_source()` returns a `RawRgbaImage`, while
`to_fragment()` returns an image `Fragment` carrying copied pixels that can be passed
to `Document.from_node`.

`RasterImage.from_raw(data, width=..., height=...)` imports an existing tightly packed
RGBA8 buffer. The byte count must equal `width * height * 4`.

The same encoder rules apply to `RasterImage.encode` and the one-call render APIs:
PNG, JPEG, lossy or lossless WebP, ICO, and `"raw"` are supported. WebP defaults to
lossless when `quality` is omitted. `lossless` is accepted only for WebP, and
`lossless=True` cannot be combined with `quality`.

### Discover image references { #discover-image-references }

After compilation, `CompiledDocument.resource_urls()` combines image references from
the compiled node and stylesheet into a deduplicated, sorted tuple.
`CompiledDocument.missing_resources()` compares those references with the
`ImageResource.src` values already owned by the document:

```python
from takumi_py import Document, ImageResource, compile_document

compiled = compile_document(
    Document.from_html(
        '<img src="https://cdn.example/hero.png"><div class="backdrop"></div>',
        resources=[
            ImageResource("https://cdn.example/hero.png", downloaded_hero),
        ],
        stylesheets=[
            '.backdrop { background-image: url("https://cdn.example/pattern.png"); }',
        ],
    )
)

print(compiled.resource_urls())
print(compiled.missing_resources())
```

Discovery never performs network access. Lowercase `data:` URLs, inline `<svg` markup,
and references already supplied under the same `src` are excluded from
`missing_resources()`. Treat the result as a conservative image-reference diagnostic
rather than proof that every future render input is present: it does not fetch URLs or
provide a complete post-cascade resource closure. Pass the fetched bytes in a
`ResourceSet` or the document's `resources` input.

`missing_resources()` reports information; it does not reject rendering.
`CompiledDocument.with_resources()` attaches resources after discovery while reusing
the existing native node and stylesheet handles. A conflicting definition for the
same `src` raises `ResourceError`.

### Prefer `Renderer.needs()` { #renderer-needs }

Use `Renderer.needs(document, *, layout=None, scale=1.0)` for the image identifiers
and font files the styled document actually reaches. The scale follows raster output:
it enlarges the viewport and sets the device pixel ratio exactly as `render()` or
`rasterize()` does. Pass the same scale used by the planned raster operation.
`measure()` and `render_svg()` use scale one, so use the default `scale=1.0` when
discovery is for those outputs. The other layout options and failed-font list apply
to that operation too:

```python
from dataclasses import replace

from takumi_py import (
    Document,
    FontError,
    ImageResource,
    LayoutOptions,
    Renderer,
    compile_document,
)

renderer = Renderer()
compiled = compile_document(Document.from_html(html))
layout = LayoutOptions(width=1200, height=630)
raster_scale = 2.0
needs = renderer.needs(compiled, layout=layout, scale=raster_scale)

supplied = {resource.src for resource in compiled.resources.images}
pending_images = set(needs.images) - supplied
if pending_images:
    compiled = compiled.with_resources(
        [ImageResource(url, fetch_bytes(url)) for url in sorted(pending_images)]
    )

for url in needs.font_files:
    try:
        data = fetch_bytes(url)
    except OSError:
        layout = replace(
            layout,
            failed_font_files=(*layout.failed_font_files, url),
        )
        continue
    try:
        renderer.load_font_file(url, data)
    except FontError:
        layout = replace(
            layout,
            failed_font_files=(*layout.failed_font_files, url),
        )

# Supplying pixels or changing a font source can reveal fallback sources and
# SVG text read from decoded images.
needs = renderer.needs(compiled, layout=layout, scale=raster_scale)
```

`needs.images` excludes `data:` URIs and inline SVG, but includes identifiers already
supplied by the document. Diff it against `compiled.resources` instead of looping until
the set is empty. `needs.font_files` reports the next source for each used
`@font-face`; load that source explicitly, record an application-side fetch failure in
`LayoutOptions.failed_font_files`, and query again. A malformed font raises
`FontError`. Replace the exception used by your HTTP client where the example uses
`OSError`.

`needs()` performs no network or filesystem access. `faces` preserves upstream
pending-face identifiers for bindings that manage faces individually; Python's normal
font APIs usually leave it empty. SVG text and fallback sources can add needs after
another resource becomes available, so repeat the query after each meaningful input
change. Reuse `raster_scale` as `RasterOptions(scale=...)` or
`Renderer.rasterize(..., scale=...)`; omit the extra scale for SVG and measurement.

When a document is compiled, its encoded image bytes are copied once into an opaque
native snapshot. The document render methods borrow that snapshot, avoiding a
Python-to-Rust upload on every render. This is not zero-copy: validation and document
snapshots still own copied bytes, and decoded images remain renderer-local cache
entries.

## Fonts

Fonts register on a renderer and stay registered for its lifetime:

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

`register_font` returns the family names Takumi registered. Pass that result to
`font_families` to select a deterministic fallback stack for a render. Takumi reads
TrueType, OpenType, WOFF, and WOFF2 data.

`FontResource` fields override what the font file declares:

| Field | Contract |
| --- | --- |
| `name` | Family name to register under; defaults to the name in the file |
| `weight` | Finite number from 1 through 1000; otherwise `ValueError` |
| `style` | CSS `font-style` syntax such as `"normal"`, `"italic"`, or `"oblique 12deg"`; otherwise `FontError` |
| `generic_family` | Generic keyword the font resolves, such as `"sans-serif"` or `"monospace"` |
| `unicode_range` | Inclusive codepoint ranges the font serves; see [Font subsets](#font-subsets) |

!!! warning "The bundled font is intentionally narrow"

    Built-in Geist is a Latin last-resort font. Register suitable fonts for non-Latin
    scripts, emoji, or brand glyphs; do not depend on fonts installed on the host OS.

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
`ValueError`. Without `unicode_range`, a later font registered under the same name and
descriptors shadows the earlier one, as a later `@font-face` rule does in a browser.

`FontResource.subset_of` is deprecated: Takumi now only uses it as the family name, in
place of `name`. See [Upgrade to Takumi 2.17](../migration/takumi-2.17.md#font-subsets)
to migrate per-subset family names.

### Releasing fonts

`unregister_font(name)` removes every face registered under a family, all its
`unicode_range` subsets included, and returns whether it had any. `clear_fonts()`
removes every registered font, including those passed to the constructor; only the
bundled Geist fallback remains, and only when the renderer was created with
`load_default_fonts=True`.

```python
renderer.unregister_font("Inter")
renderer.clear_fonts()
```

### Caching fonts on demand

A service that loads fonts per request, such as the families its users pick, can let
the renderer hold them within a budget instead of registering each one for good.
`cache_font(font, key)` registers a font under a key, such as the URL it came from, and
`cached_fonts(key)` returns its families while the renderer still holds them, or
`None`. Here `download` stands for your own HTTP client:

```python
from takumi_py import Renderer

renderer = Renderer(font_cache_max_bytes=64 * 1024 * 1024)


def font_families(url: str) -> tuple[str, ...]:
    return renderer.cached_fonts(url) or renderer.cache_font(download(url), url)


png = renderer.render_html(html, font_families=list(font_families(url)))
```

Past `font_cache_max_bytes` of decoded font data, the renderer releases the least
recently used cached families. A render marks the families in its `font_families`
used, and so does a `cached_fonts()` hit; `cached_fonts(key, pin=True)` keeps a font
for good. Fonts from `register_font`, `register_fonts`, or the constructor are never
released, and the font cached last stays even when it alone exceeds the budget.
`unregister_font` and `clear_fonts` forget cached fonts as well.

## Language

The render-level `lang` option affects text shaping and line breaking. It must be a
valid BCP-47 language tag; every render, measure, SVG, and animation entry point
rejects an invalid tag with `ValueError`.

Render-level `lang` does not write a node attribute, so it does not make CSS `:lang()`
selectors match. Set `lang` on the HTML element or node that establishes the language:

=== "HTML"

    ```python
    renderer.render_html(
        '<section lang="zh-Hant"><div class="headline">你好</div></section>',
        stylesheets=[
            '.headline:lang(zh-Hant) { font-family: "Noto Sans TC"; }',
        ],
    )
    ```

=== "Node tree"

    ```python
    renderer.render_node(
        {
            "type": "container",
            "lang": "ja",
            "children": [{"type": "text", "text": "こんにちは"}],
        },
        stylesheets=[':lang(ja) { font-family: "Noto Sans JP"; }'],
    )
    ```

## Cache budgets

`Renderer(cache_max_bytes=...)` sets the byte budget shared by that renderer's decoded
images, scaled image variants, SVG rasters, and related render resources. Images
embedded as `data:` URIs decode through the same cache, so a template that inlines its
logo decodes it once per renderer rather than on every render. The default is 64 MiB;
pass `0` to disable retention. Fonts held with `cache_font` have their own budget,
`font_cache_max_bytes`, as [caching fonts on demand](#caching-fonts-on-demand) explains.

Glyph masks and outlines use a separate process-wide cache with an 8 MiB default.
For CJK-heavy workloads, configure it before the first render in the process:

```python
from takumi_py import Renderer, set_glyph_cache_max_bytes

set_glyph_cache_max_bytes(32 * 1024 * 1024)
renderer = Renderer(cache_max_bytes=128 * 1024 * 1024)
```

Changing the glyph budget after glyph rendering begins does not resize the existing
process-wide caches.

## Lifecycle

| Resource | Preferred lifetime | API |
| --- | --- | --- |
| Font | Renderer lifetime | `register_font` or `register_fonts`; release with `unregister_font` or `clear_fonts` |
| Cached font | Until released for space | `cache_font`, checked with `cached_fonts`, bounded by `font_cache_max_bytes` |
| Image | One render | `images=[ImageResource(...)]` |

??? info "Removed compatibility APIs"

    0.4.0 removed the shims deprecated in 0.2.0: `load_font`, `load_fonts`,
    `fetched_resources`, `persistent_images`, `put_persistent_image`, and
    `clear_image_store`. The [Takumi v2 migration](../migration/takumi-v2.md#resource-apis)
    lists their replacements.

See the runnable
[`examples/render_resources.py`](https://github.com/BalconyJH/takumi-py/blob/main/examples/render_resources.py)
and
[`examples/render_static.py`](https://github.com/BalconyJH/takumi-py/blob/main/examples/render_static.py)
examples.
