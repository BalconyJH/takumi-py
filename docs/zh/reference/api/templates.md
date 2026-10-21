# 模板

`TemplateRenderer` 接受一个可选的已配置 `Renderer`。模板渲染必须使用该渲染器上已注册的
字体时，请注入它；省略时，模板包装器会在内部创建一个默认渲染器。它也接受一个完整的
Jinja `Environment` 来代替 `template_dir`，并保留原生的加载器、全局变量、测试、扩展、
未定义值策略、缓存以及其他 Jinja 配置。

::: takumi_py.template.TemplateRenderer
    options:
      members:
        - __init__
        - environment
        - render

## render_template_to_html { #render_template_to_html }

调用方只需要渲染后的 HTML 而不需要图片输出时，使用这个独立的辅助函数。它接受
`template_dir` 或调用方持有的 Jinja `environment` 二者之一，以及同样的自定义过滤器
映射。需要带有自定义渲染器状态的图片输出时，优先使用
`TemplateRenderer(..., renderer=renderer)`。

::: takumi_py.template.render_template_to_html
