# HTML 解析

`parse_html` 是独立的、基于 Rust 的 HTML 解析器。它返回 `ParsedHtml` 组合，其中包含
已编译节点和从符合条件的 `<style>` 元素中提取的已编译样式表。使用时把这两个字段分别
传给已编译渲染 API：

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
调用方需要额外作者 CSS 时，它仍是显式输入；传给已编译 API 之前，请先用
`Renderer.compile_stylesheet` 或 `Renderer.compile_stylesheet_lossy` 编译它。按级联
顺序，作者 CSS 位于提取出的文档样式之前。HTML 编译直接由原生解析器完成，HTML 入口没有
单独的 Python 侧 `validate` 开关。解析行为的完整说明见
[HTML 与 CSS](../../guides/html.md)。

## parse_html { #parse_html }

::: takumi_py.html.parse_html

## ParsedHtml { #parsedhtml }

::: takumi_py.html.ParsedHtml
    options:
      members:
        - node
        - stylesheets
