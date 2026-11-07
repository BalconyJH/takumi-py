# HTML 解析

`parse_html` 是独立的、基于 Rust 的 HTML 解析器。它返回 `ParsedHtml` 组合，其中包含
已编译节点和一个已编译样式表元组。当前解析器会忽略 `<style>` 元素，因此该元组为空；
请显式编译文档级 CSS。使用时把这两个字段分别传给已编译渲染 API：

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

使用 `HtmlOptions` 选择解析器预设、从其他属性映射 Tailwind 类名，或限制嵌套深度。
文档级 CSS 仍是显式的渲染输入；传给已编译 API 之前，请先用
`Renderer.compile_stylesheet` 或 `Renderer.compile_stylesheet_lossy` 编译它。HTML
编译直接由原生解析器完成，HTML 入口没有单独的 Python 侧 `validate` 开关。解析行为的
完整说明见 [HTML 与 CSS](../../guides/html.md)。

## parse_html { #parse_html }

::: takumi_py.html.parse_html

## ParsedHtml { #parsedhtml }

::: takumi_py.html.ParsedHtml
    options:
      members:
        - node
        - stylesheets
