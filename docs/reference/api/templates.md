# Templates

`TemplateRenderer` accepts an optional configured `Renderer`. Inject one when template
renders must use fonts registered on that renderer; when omitted, the template wrapper
creates a default renderer internally. It also accepts a complete Jinja `Environment`
instead of `template_dir`, preserving native loaders, globals, tests, extensions,
undefined-value policies, caches, and other Jinja configuration.

::: takumi_py.template.TemplateRenderer
    options:
      members:
        - __init__
        - environment
        - render

## render_template_to_html

Use this standalone helper when the caller needs rendered HTML without image output.
It accepts either `template_dir` or a caller-owned Jinja `environment`, plus the same
custom-filter mapping. For image output with custom renderer state, prefer
`TemplateRenderer(..., renderer=renderer)`.

::: takumi_py.template.render_template_to_html
