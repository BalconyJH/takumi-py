# Renderer

`Renderer` is the primary entry point for compilation, measurement, static rendering,
SVG, animation, and reusable documents.

`Renderer(cache_max_bytes=...)` controls each renderer's resource cache, and
`font_cache_max_bytes` bounds the fonts it holds through `cache_font`. The glyph cache
is process-wide and configured separately before first use.

::: takumi_py.renderer.set_glyph_cache_max_bytes

::: takumi_py.renderer.Renderer
    options:
      members:
        - __init__
        - render
        - rasterize
        - needs
        - measure
        - render_svg
        - compile_node
        - compile_stylesheet
        - compile_stylesheet_lossy
        - compile_keyframes
        - register_font
        - register_fonts
        - cache_font
        - cached_fonts
        - load_font_file
        - forget_font_file
        - unregister_font
        - clear_fonts
        - render_compiled
        - measure_compiled
        - render_node
        - measure_node
        - compile_html
        - render_html
        - measure_html
        - render_template
        - render_svg_compiled
        - render_svg_node
        - render_svg_html
        - render_svg_template
        - render_sequence_at_time
        - render_animation
        - encode_frames

## CompiledHtml

::: takumi_py.renderer.CompiledHtml
    options:
      members:
        - node
        - stylesheets

## Raster images { #raster-images }

::: takumi_py.raster.RasterImage
    options:
      members:
        - from_raw
        - width
        - height
        - size
        - stride
        - nbytes
        - data
        - tobytes
        - encode
        - to_raw_source
        - to_fragment

## Document APIs { #document-apis }

The document APIs are a next-major preview. They are additive, while the existing
renderer entry points retain their current compatibility and pixel-sizing behavior.

`CompiledDocument` copies encoded image bytes once into an opaque native snapshot.
Its renderer methods borrow that snapshot, while decoded images remain in the chosen
renderer's resource cache. `resource_urls()` is the deduplicated union of image
references from the node and stylesheet. `missing_resources()` is a conservative
diagnostic and does not block rendering. `with_resources()` adds image resources
without recompiling the node or stylesheet.

::: takumi_py.document.Document

::: takumi_py.document.Fragment

::: takumi_py.document.ResourceSet

::: takumi_py.document.CompiledDocument

::: takumi_py.document.compile_document

::: takumi_py.options.LayoutOptions

::: takumi_py.options.RasterOptions
