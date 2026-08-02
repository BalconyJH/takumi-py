# Migrate to Takumi v2

Takumi v2 replaces implicit renderer-level resource context with explicit resource
inputs and maps the Python binding more directly to core.

## Resource APIs

| Previous interface | Preferred interface |
| --- | --- |
| `fetched_resources` | Pass `images=[ImageResource(...)]` to each render |
| `load_font` / `load_fonts` | `register_font` / `register_fonts` |
| Persistent image APIs | Prefer per-render `images` |

The old interfaces remain temporarily as deprecated compatibility shims. New code
should use the explicit model directly.

## HTML and stylesheets

HTML parsing now lives in Takumi's Rust parser. HTML render, measure, SVG, and template
calls all receive document-level CSS explicitly through `stylesheets=[...]`. Use
`HtmlOptions` to customize parser presets, the Tailwind attribute, or the depth limit.

## Fonts and language

- `FontResource` accepts `name`, `weight`, `style`, `subset_of`, and
  `generic_family` descriptors. A weight override must be finite and within
  1 through 1000.
- `register_font(s)` returns the actual family names, which can be passed to render
  calls as `font_families`.
- Render-level `lang` affects shaping and line breaking; CSS `:lang()` still depends
  on an HTML or node attribute. Invalid BCP-47 render-level tags raise `ValueError`.
- The built-in fallback is now Latin Geist as a last resort. Caller-provided fonts
  participate first in normal fallback.

## Images and URLs

`ImageResource.cache` maps directly to the Takumi image cache hint.
`CompiledNode.resource_urls()` reports HTTP(S) image and style references, but it does
not download them or report already supplied `memory://` bytes.

## Animation and output

- Pass structured keyframes through `keyframes=` or `RenderOptions(keyframes=...)`.
- WebP defaults to lossless when neither `quality` nor `lossless` is specified.
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
