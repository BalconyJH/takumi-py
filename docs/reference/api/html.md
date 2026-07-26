# HTML parsing

`parse_html` is the standalone Rust-backed HTML parser. It returns a `ParsedHtml`
bundle containing the compiled node and any compiled stylesheets associated with the
parse result. Pass those fields separately to a compiled renderer API:

```python
from takumi_py import Renderer, parse_html

parsed = parse_html("<article>Hello</article>")
png = Renderer().render_compiled(
    parsed.node,
    stylesheets=parsed.stylesheets,
    width=320,
    height=160,
)
```

Use `HtmlOptions` to select parser presets, map Tailwind classes from another
attribute, or cap nesting depth. Document-level CSS remains an explicit render input;
compile it with `Renderer.compile_stylesheet` before passing it to a compiled API.
HTML compilation is performed directly by the native parser; HTML entry points do not
have a separate Python-side `validate` switch.

## parse_html

::: takumi_py.html.parse_html

## ParsedHtml

::: takumi_py.html.ParsedHtml
    options:
      members:
        - node
        - stylesheets
