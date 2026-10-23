# Migrate to Takumi v2

Takumi v2 replaces implicit renderer-level resource context with explicit resource
inputs and maps the Python binding more directly to core.

## Resource APIs

| Removed interface | Replacement |
| --- | --- |
| `fetched_resources=` on render calls and `RenderOptions` | Pass `images=[ImageResource(...)]` to each render |
| `load_font` / `load_fonts` | `register_font` / `register_fonts`, which return the registered family names |
| `Renderer(persistent_images=...)`, `put_persistent_image`, `clear_image_store` | Pass the images to each render that uses them |

These interfaces were deprecated in 0.2.0 and removed in 0.4.0. Code that still uses
them fails with `TypeError` for the keyword arguments and `AttributeError` for the
methods, so fix any `DeprecationWarning` under 0.3 before you upgrade.

## HTML and stylesheets

HTML parsing now lives in Takumi's Rust parser. HTML render, measure, SVG, and template
calls all receive document-level CSS explicitly through `stylesheets=[...]`, and inline
`style` attributes are parsed with the HTML. Use `HtmlOptions` to customize parser
presets, the Tailwind attribute, or the depth limit. See [HTML and CSS](../guides/html.md).

## Fonts and language

- `FontResource` accepts `name`, `weight`, `style`, `generic_family`, and
  `unicode_range` descriptors. A weight override must be finite and within
  1 through 1000. Since Takumi 2.17, register each subset of a family under one
  `name` with its own `unicode_range`; see
  [Upgrade to Takumi 2.17](takumi-2.17.md#font-subsets).
- `register_font(s)` returns the actual family names, which can be passed to render
  calls as `font_families`.
- Render-level `lang` affects shaping and line breaking; CSS `:lang()` still depends
  on an HTML or node attribute. Invalid BCP-47 render-level tags raise `ValueError`.
- The built-in fallback is now Latin Geist as a last resort. Caller-provided fonts
  participate first in normal fallback.

## Images and URLs

`ImageResource.cache` maps directly to the Takumi image cache hint for each per-render
image. Image nodes also accept decoded `RawRgbaImage` pixels. `CompiledNode.resource_urls()` reports HTTP(S) image and style
references, but it does not download them or report already supplied `memory://` bytes.
See [Fonts and images](../guides/resources.md).

## Animation and output

- Pass structured keyframes through `keyframes=` or `RenderOptions(keyframes=...)`.
- WebP defaults to lossless when neither `quality` nor `lossless` is specified, and
  `quality` together with `lossless=True` is rejected.
- Render SVG with `render_svg_node`, `render_svg_html`, `render_svg_template`, or
  `render_svg_compiled`.

## Migration checklist

- [ ] Replace implicit fetched resources with explicit `ImageResource` inputs.
- [ ] Replace deprecated font loaders with registration APIs.
- [ ] Pass document-level CSS through `stylesheets`.
- [ ] Register fonts for every script used by the rendered text.
- [ ] Exercise raster, SVG, measurement, and animation output used by the application.

!!! warning "Layout changes after migration"

    Check Web-platform defaults first: `position`, border and outline widths,
    `transform-origin`, `object-position`, and SVG `currentColor` inheritance.
