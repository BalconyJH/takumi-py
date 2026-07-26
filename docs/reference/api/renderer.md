# Renderer

`Renderer` is the primary entry point for compilation, measurement, static rendering,
SVG, and animation.

::: takumi_py.renderer.Renderer
    options:
      members:
        - __init__
        - compile_node
        - compile_stylesheet
        - compile_stylesheet_lossy
        - compile_keyframes
        - register_font
        - register_fonts
        - load_font
        - load_fonts
        - put_persistent_image
        - clear_image_store
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
