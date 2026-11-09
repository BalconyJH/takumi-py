# Upgrade to Takumi 2.20

This checkout moves the native renderer from Takumi 2.17.1 and
`takumi-core` 0.32.0 to Takumi 2.20.0 and `takumi-core` 0.36.0. The existing Python
rendering calls remain available. Most migration work is about discovering resources
that `@font-face` and the HTML cascade can now require, and reviewing output that has
moved closer to Chromium.

## Resource discovery { #resource-discovery }

`Renderer.needs(document, *, layout=None, scale=1.0)` reports what a compiled document
reaches after CSS matching, custom-property substitution, media evaluation, generated
content, and `display: none`. It returns a `RenderNeeds` value:

| Field | Meaning |
| --- | --- |
| `images` | Image identifiers the styled tree can use, including identifiers already supplied by the document |
| `faces` | Pending face identifiers used by upstream font fallback |
| `font_files` | The next `@font-face` file URL for each used face |

No network or filesystem access occurs. The query is synchronous and uses the same
layout options and raster scale as rendering. For raster output at scale `S`, pass
`scale=S`: `needs()` enlarges the viewport the same way and uses the same device pixel
ratio, so resolution media queries and viewport rounding agree. Measurement and SVG
layout use scale one, so query with the default `scale=1.0` for those outputs.

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

html = """
<style>
  @font-face {
    font-family: Article;
    src: url("https://assets.example/article.woff2");
  }
  .hero {
    width: 1200px;
    height: 630px;
    font-family: Article;
    background-image: url("https://assets.example/background.png");
  }
</style>
<div class="hero">Hello</div>
"""

layout = LayoutOptions(width=1200, height=630)
raster_scale = 2.0
renderer = Renderer()
compiled = compile_document(Document.from_html(html))
needs = renderer.needs(compiled, layout=layout, scale=raster_scale)

if needs.images:
    compiled = compiled.with_resources(
        [ImageResource(url, fetch_bytes(url)) for url in needs.images]
    )

for url in needs.font_files:
    try:
        renderer.load_font_file(url, fetch_bytes(url))
    except FontError:
        layout = replace(
            layout,
            failed_font_files=(*layout.failed_font_files, url),
        )

# Loading or failing one source can expose the next fallback source, or SVG text
# inside an image that was not otherwise needed.
needs = renderer.needs(compiled, layout=layout, scale=raster_scale)
```

`images` is not a missing-resource list. It includes URLs already supplied through
`Document`, so use it as the image set for the current cascade rather than looping
until it becomes empty. `faces` is preserved for bindings that register pending faces;
the normal all-at-once Python font API does not create them.

Keep `CompiledDocument.resource_urls()` and `missing_resources()` where a conservative
node-plus-stylesheet inventory is useful. Prefer `needs()` when the application needs
the images and font files that the styled tree can actually reach.

## CSS `@font-face` files { #font-face-files}

Takumi 2.20 evaluates `@font-face` rules from render stylesheets. The CSS owns the
family, weight, style, source order, and `unicode-range`; the application supplies only
the bytes:

```python
renderer.load_font_file(url, data)
```

Files loaded this way belong to the renderer until
`renderer.forget_font_file(url)` or `renderer.clear_fonts()`. They are separate from
the `cache_font()` budget and from families registered with `FontResource`.
`load_font_file()` rejects unusable font data with `FontError`; a failed load does not
silently mark the URL unavailable.

When an application fetch fails, set `LayoutOptions.failed_font_files` to the failed
URLs for that call. The setting is snapshotted, applies only to that renderer
operation, and lets Takumi choose the next `src`. Query `needs()` again after changing
loaded or failed files.

## HTML `<style>` elements { #html-style-elements}

The HTML parser now returns the CSS of eligible `<style>` elements alongside the node
tree. `Renderer.compile_html()` exposes both through `CompiledHtml`, while
`render_html()`, `measure_html()`, `render_svg_html()`, and template adapters apply the
embedded CSS automatically.

- Missing or empty `type`, plus case-insensitive `text/css`, is accepted.
- CSS is kept in document order.
- A non-empty `media` attribute becomes an `@media` rule around that block.
- Explicit author stylesheets are applied first; embedded document styles are applied
  afterward.
- `<link>` elements, scripts, linked stylesheets, and `<base>` URLs are not resolved.
  URL strings remain exactly as authored and still match explicit resources by that
  string.

Remove `<style>` fixtures that applications previously copied into `stylesheets=` by
hand. If an application intentionally supplied the same CSS as an author override, keep
only the override and rely on the document's embedded rule for the base style.

HTML and template entry points continue to compile browser-authored CSS with error
tolerance. `compile_stylesheet()` remains strict by default.

## Expected rendering changes { #expected-rendering-changes}

Takumi 2.18 through 2.20 add more Chromium-aligned behavior. Inline SVG in HTML inherits
properties from its host element and accepts the page stylesheet before its own styles.
Layout also adds or improves CSS math functions, typed `@property`, counters, form text
fields, `:has()`, `:disabled` and related form states, `line-clamp`, named pages,
tables, flex, grid, SVG text, and SVG filters.

Regenerate visual fixtures and compare suspicious differences with Chrome. Some
documents will move geometry or pixels even though their Python inputs did not change.

Upstream 2.20 also has internal paged-raster APIs and `@page` support. This upgrade
does not add paged or PDF output to the Python API.

## Upgrade checklist { #upgrade-checklist}

- [ ] Rebuild the extension against the new native dependencies before testing.
- [ ] Replace hand-copied HTML `<style>` CSS with the parsed document styles.
- [ ] Query `Renderer.needs()` with each layout and raster scale used by the
  application. Use the default scale of one for measurement and SVG.
- [ ] Fetch reported images and `@font-face` files explicitly.
- [ ] Represent failed font downloads with `LayoutOptions.failed_font_files`.
- [ ] Query `needs()` again after loaded or failed inputs change.
- [ ] Regenerate and review raster, SVG, and measurement fixtures.
- [ ] Review new upstream and vendored-license notices when packaging.
