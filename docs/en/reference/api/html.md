# HTML parsing

`parse_html` is the standalone Rust-backed HTML parser. It returns a `ParsedHtml`
bundle containing the compiled node and the compiled stylesheets extracted from
eligible `<style>` elements. Pass both fields separately to a compiled renderer API:

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
attribute, or cap nesting depth. Explicit author CSS remains an input when the caller
needs it; compile that CSS with `Renderer.compile_stylesheet` or
`Renderer.compile_stylesheet_lossy` before passing it to a compiled API. Author CSS
comes before the extracted document styles in cascade order.
HTML compilation is performed directly by the native parser; HTML entry points do not
have a separate Python-side `validate` switch. See [HTML and CSS](../../guides/html.md)
for the full parsing behavior.

## parse_html

::: takumi_py.html.parse_html

## ParsedHtml

::: takumi_py.html.ParsedHtml
    options:
      members:
        - node
        - stylesheets
