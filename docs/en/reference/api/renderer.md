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

## Document APIs { #document-apis }

The document APIs are a next-major preview. They are additive, while the existing
renderer entry points retain their current compatibility and pixel-sizing behavior.

::: takumi_py.document.Document

::: takumi_py.document.Fragment

::: takumi_py.document.ResourceSet

::: takumi_py.document.CompiledDocument

::: takumi_py.document.compile_document

::: takumi_py.options.LayoutOptions

::: takumi_py.options.RasterOptions
