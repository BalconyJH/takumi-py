# 快速上手

下面的程序用显式样式表渲染 HTML，并写出一个 PNG：

```python
from pathlib import Path

from takumi_py import Renderer

renderer = Renderer()
png = renderer.render_html(
    '<section class="card"><h1>Hello</h1></section>',
    stylesheets=[
        """
        .card {
          width: 1200px;
          height: 630px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          background: #111827;
        }
        h1 { font-size: 72px; }
        """
    ],  # (1)!
    width=1200,
    height=630,  # (2)!
)

Path("out.png").write_bytes(png)
```

1. 样式表作为文档级渲染输入传入，而不是隐藏在渲染器的全局状态中。
2. 需要多次调用得到相同结果时，请固定两个视口维度。

## 选择输入模型 { #choose-an-input-model }

<div class="grid cards" markdown>

- **已有 HTML**：使用 `render_html`，见 [HTML 与 CSS](../guides/html.md)。
- **内容是结构化数据**：使用 `render_node`，见
  [节点树](../guides/rendering.md#node-trees)。
- **同一结构会被反复渲染**：调用 `compile_node` 或 `compile_html`，再遵循
  [已编译渲染约定](../guides/rendering.md#compile-and-reuse)。
- **模板存放在磁盘上**：使用 `TemplateRenderer`，见
  [Jinja 模板](../guides/templates.md)。

</div>

## 下一步 { #next-steps }

??? question "结果看起来不对"

    先检查以下边界：

    1. 视口尺寸是显式指定的，还是有意交给布局推断？
    2. 文档级 CSS 是否通过 `stylesheets` 传入？
    3. 文本所需的字体是否已经注册？

    底层约定见 [渲染模型](../guides/rendering.md) 和 [资源指南](../guides/resources.md)。
