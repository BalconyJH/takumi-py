# Renderer

`Renderer` 是编译、测量、静态渲染、SVG、动画和可复用文档的主要入口。

`Renderer(cache_max_bytes=...)` 控制每个渲染器的资源缓存，`font_cache_max_bytes` 则限制它
通过 `cache_font` 持有的字体。字形缓存是进程级的，需要在首次使用之前单独配置。

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

## CompiledHtml { #compiledhtml }

::: takumi_py.renderer.CompiledHtml
    options:
      members:
        - node
        - stylesheets

## 文档 API { #document-apis }

文档 API 是下一主版本预览。这些能力是增量的，现有渲染入口继续保持兼容和当前的像素
尺寸语义。

::: takumi_py.document.Document

::: takumi_py.document.Fragment

::: takumi_py.document.ResourceSet

::: takumi_py.document.CompiledDocument

::: takumi_py.document.compile_document

::: takumi_py.options.LayoutOptions

::: takumi_py.options.RasterOptions
