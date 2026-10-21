# HTML 与 CSS

Takumi 的 Rust 解析器会把 HTML 转换成与 `render_node` 所接受的相同的节点树。绑定中
没有浏览器，也没有 Python 侧的 HTML 解析器。

## 渲染 HTML { #render-html }

```python
from takumi_py import Renderer

png = Renderer().render_html(
    '<div class="card"><h1>Hello</h1></div>',
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
        """
    ],
    width=1200,
    height=630,
)
```

`measure_html` 和 `render_svg_html` 接受相同的 HTML 和样式表输入。

## 文档结构 { #document-structure }

以 doctype 或 `<html>` 元素开头的源码会按文档解析，并像浏览器一样构建 `<html>`、
`<head>` 和 `<body>`。其他源码按片段解析。包含多个顶层元素的片段会被包进一个填满
视口的容器。

解析器把 `style`、`class`、`id`、`dir`、`lang` 和 Tailwind 属性映射到节点树上。
`<style>` 元素以及其他不参与渲染的元素会被丢弃；没有 `src` 的 `<img>` 会渲染为一个
空盒子，尺寸由其 `width` 和 `height` 决定。

## 样式表 { #stylesheets }

内联 `style` 属性属于 HTML 的一部分。文档级 CSS 始终通过 `stylesheets=[...]` 显式
传入，标记中的 `<style>` 元素会被忽略。

HTML 入口和节点入口编译 `stylesheets` 的方式不同：

| 入口 | 编译方式 | 不支持的声明 |
| --- | --- | --- |
| `render_html`、`measure_html`、`render_svg_html`、`render_template`、`render_svg_template` | 像浏览器一样容错 | 跳过 |
| `render_node`、`measure_node`、`render_svg_node`、`render_animation`、`render_sequence_at_time` | 严格 | 抛出 `StyleSheetError` |

使用已编译 API 时请显式选择：`compile_stylesheet` 是严格的，
`compile_stylesheet_lossy` 是容错的。

```python
from takumi_py import Renderer, StyleSheetError

renderer = Renderer()
tolerant = renderer.compile_stylesheet_lossy("a { display: weird; } b { color: red; }")

try:
    renderer.compile_stylesheet("a { display: weird; }")
except StyleSheetError as error:
    print(error)
```

## 解析器选项 { #parser-options }

`HtmlOptions` 控制解析器：

```python
from takumi_py import HtmlOptions, Renderer

png = Renderer().render_html(
    '<div class="w-[1200px] h-[630px]"></div>',
    html_options=HtmlOptions(
        presets="none",
        tailwind_property="class",
        max_depth=64,
    ),
    width=None,
    height=None,
)
```

| 选项 | 默认值 | 作用 |
| --- | --- | --- |
| `presets` | `"chromium"` | `"chromium"` 应用 Chromium 的默认元素样式；`"none"` 不应用任何默认样式 |
| `tailwind_property` | `None` | 承载 Tailwind 类名的属性；`None` 读取 `tw` 属性 |
| `max_depth` | `None` | 元素最大嵌套深度；`None` 使用 Takumi 的上限 512 |

嵌套深度超过 `max_depth` 时抛出 `HtmlParseError`。

## 一次解析，多次渲染 { #parse-once-render-many }

`parse_html` 无需渲染器即可解析，并返回 `ParsedHtml` 组合；`Renderer.compile_html`
返回等价的 `CompiledHtml`。按照 [编译与复用](rendering.md#compile-and-reuse) 的说明，
把组合中的节点和样式表传给已编译 API：

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

## 发现外部资源 { #discover-external-resources }

渲染器从不抓取任何内容。`CompiledNode.resource_urls()` 列出图片节点和样式中的
HTTP(S) 图片引用，应用可以先行抓取它们：

```python
from takumi_py import Renderer

compiled = Renderer().compile_node(
    {"type": "image", "src": "https://example.com/logo.png"}
)

print(compiled.resource_urls())
```

它不会报告调用方已经提供的来源，例如 `memory://` 资源或字节缓冲区。请按
[字体与图片](resources.md#images) 的说明，把抓取到的字节作为 `ImageResource` 传回。

可运行示例见
[`examples/render_html.py`](https://github.com/BalconyJH/takumi-py/blob/main/examples/render_html.py)。
