---
icon: lucide/image
---

# takumi-py

[Takumi](https://github.com/kane50613/takumi) Rust 渲染器的 Python 3.10+ 绑定。无需
浏览器运行时，即可把类型化的节点树、HTML 或 Jinja 模板渲染为位图、SVG 和动画。

[开始使用 :material-arrow-right:](getting-started/index.md){ .md-button .md-button--primary }
[API 参考](reference/index.md){ .md-button }

!!! warning "测试阶段项目"

    随着 Takumi 核心演进，公共 API、异常类型和发布平台仍可能变化。升级前请阅读
    [变更日志](https://github.com/BalconyJH/takumi-py/blob/main/CHANGELOG.md)。

## 选择路径 { #choose-your-path }

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **渲染第一张图片**

    ---

    安装 wheel，用几行代码从 HTML 生成 PNG。

    [:octicons-arrow-right-24: 快速上手](getting-started/quickstart.md)

-   :material-vector-square:{ .lg .middle } **理解渲染流程**

    ---

    在节点树、HTML 和已编译内容之间选择输入，再选择位图、SVG 或测量输出。

    [:octicons-arrow-right-24: 渲染模型](guides/rendering.md) ·
    [:octicons-arrow-right-24: HTML 与 CSS](guides/html.md) ·
    [:octicons-arrow-right-24: 输出格式](guides/output.md)

-   :material-folder-image:{ .lg .middle } **管理资源**

    ---

    注册字体、提供内存中的图片，并控制按语言进行的文本整形。

    [:octicons-arrow-right-24: 字体与图片](guides/resources.md)

-   :material-movie-open-play:{ .lg .middle } **生成动态输出**

    ---

    渲染 Jinja 模板，或编码 WebP、APNG 与 GIF 动画。

    [:octicons-arrow-right-24: 模板](guides/templates.md) ·
    [:octicons-arrow-right-24: 动画](guides/animation.md)

</div>

## 最小示例 { #minimal-example }

```python
from pathlib import Path

from takumi_py import Renderer

png = Renderer().render_html(
    '<main class="card">Hello from Python</main>',
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
          font-size: 72px;
        }
        """
    ],  # (1)!
    width=1200,
    height=630,  # (2)!
)

Path("out.png").write_bytes(png)
```

1. 文档级 CSS 是显式输入，内联 `style` 属性仍属于 HTML 输入的一部分。
2. 显式视口让输出尺寸保持确定。任一维度也可以交由布局推断。

## 设计边界 { #design-boundary }

绑定在保持资源归属清晰的前提下，暴露 Takumi 核心的实用能力：外部字体和图片字节由
调用方提供，渲染器不访问网络。本包有意不提供 Playwright 回退、远程抓取、
`AbortSignal` 抽象、data URL 辅助函数或 Node.js 旁路进程。完整说明见
[支持矩阵](reference/support.md)。
