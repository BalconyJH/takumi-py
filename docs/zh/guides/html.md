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
`<style>` 元素会从节点树中移除，其中的 CSS 按文档顺序单独返回。其他不参与渲染的元素
会被丢弃；没有 `src` 的 `<img>` 会渲染为一个空盒子，尺寸由其 `width` 和 `height`
决定。

## 样式表 { #stylesheets }

内联 `style` 属性属于 HTML 的一部分。符合条件的 `<style>` 元素中的 CSS 会被提取并
自动应用。`stylesheets=[...]` 参数仍用于应用提供的作者 CSS；它在文档内嵌样式之前应用，
因此同等优先级的 HTML 规则会在级联中处于更后的位置。

缺少 `type`、`type` 为空或大小写不敏感的 `text/css` 时，`<style>` 代码块会参与解析。
非空 `media` 会被包成外层 `@media` 规则。不支持 `<link>` 元素、脚本、外部样式表和
`<base>` URL 解析；URL 字符串保持原始写法。

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

因此 HTML 的有效嵌套上限始终不高于 512。传入大于 512 的 `max_depth` 会在开始解析前
抛出 `ValueError`；HTML 嵌套深度超过有效上限时抛出 `HtmlParseError`。

## 一次解析，多次渲染 { #parse-once-render-many }

`parse_html` 无需渲染器即可解析，并返回 `ParsedHtml` 组合；`Renderer.compile_html`
返回等价的 `CompiledHtml`。按照 [编译与复用](rendering.md#compile-and-reuse) 的说明，
把组合中的节点和样式表传给已编译 API：

```python
from takumi_py import Renderer, parse_html

parsed = parse_html("<style>article { color: red; }</style><article>Hello</article>")
png = Renderer().render_compiled(
    parsed.node,
    stylesheets=parsed.stylesheets,
    width=320,
    height=160,
)
```

`ParsedHtml.stylesheets` 与 `CompiledHtml.stylesheets` 按文档顺序包含提取出的 CSS。
把它们与显式作者 CSS 组合时，先传显式样式表，再传提取出的样式表。

## 发现外部资源 { #discover-external-resources }

渲染器从不抓取任何内容。`CompiledNode.resource_urls()` 列出图片节点中的图片来源标识，
`CompiledStyleSheet.resource_urls()` 列出 CSS 中的标识，
`CompiledDocument.resource_urls()` 返回二者去重后的并集。资源发现不限于 HTTP(S)：
找到的每个标识都会包含在内，包括 `memory://` 这样的自定义协议：

```python
from takumi_py import Document, compile_document

compiled = compile_document(
    Document.from_node({"type": "image", "src": "https://example.com/logo.png"})
)

print(compiled.resource_urls())
print(compiled.missing_resources())
```

`missing_resources()` 会排除文档已经提供的引用，以及自包含的 data URL 或内联 SVG。
由原始字节支持的图片来源没有可供发现的字符串标识；带标识的来源会保留其协议。请按
[字体与图片](resources.md#discover-image-references) 的说明，把应用读取到的字节作为
`ImageResource` 传回。应把结果视为保守的图片引用诊断，而不是完整的级联后资源闭包。

如果需要知道样式化文档实际会访问的资源，应优先使用
`Renderer.needs(document, *, layout=None, scale=1.0)`。它会计算 CSS 匹配、自定义
属性、媒体查询、隐藏节点、生成内容和 `@font-face` 文件。为栅格输出查询时，请传入
栅格操作的缩放值，使分辨率查询和视口取整一致；测量和 SVG 使用缩放 1：

```python
from takumi_py import Document, LayoutOptions, Renderer, compile_document

compiled = compile_document(
    Document.from_html(
        """
        <style>
          @font-face { font-family: Article; src: url(article.woff2); }
          .card { font-family: Article; background: url(card.png); }
        </style>
        <div class="card">Hello</div>
        """
    )
)
needs = Renderer().needs(
    compiled,
    layout=LayoutOptions(width=1200, height=630),
    scale=2.0,
)
print(needs.images)
print(needs.font_files)
```

渲染器仍不执行任何 I/O。请用 `load_font_file()` 加载报告的字体文件，通过
`LayoutOptions.failed_font_files` 标记下载失败，并在任一状态变化后再次查询
`needs()`。见[升级到 Takumi 2.20](../migration/takumi-2.20.md#resource-discovery)。

可运行示例见
[`examples/render_html.py`](https://github.com/BalconyJH/takumi-py/blob/main/examples/render_html.py)。
