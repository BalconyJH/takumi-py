# Renderer

`Renderer` 是编译、测量、静态渲染、SVG 和动画的主要入口。

`Renderer(cache_max_bytes=...)` 控制每个渲染器的资源缓存。字形缓存是进程级的，需要在
首次使用之前单独配置。

::: takumi_py.renderer.set_glyph_cache_max_bytes

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
        - unregister_font
        - clear_fonts
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

## CompiledHtml { #compiledhtml }

::: takumi_py.renderer.CompiledHtml
    options:
      members:
        - node
        - stylesheets
