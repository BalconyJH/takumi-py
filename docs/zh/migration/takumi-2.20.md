# 升级到 Takumi 2.20

此检出把原生渲染器从 Takumi 2.17.1 与 `takumi-core` 0.32.0 升级到 Takumi 2.20.0 与
`takumi-core` 0.36.0。现有 Python 渲染调用仍然可用。大部分迁移工作来自 `@font-face`
和 HTML 级联现在可能需要的资源发现，以及检查更接近 Chromium 的输出变化。

## 资源发现 { #resource-discovery }

`Renderer.needs(document, *, layout=None, scale=1.0)` 报告编译后的文档经过 CSS 匹配、
自定义属性替换、媒体查询求值、生成内容和 `display: none` 之后实际会访问的内容。它返回
一个 `RenderNeeds` 值：

| 字段 | 含义 |
| --- | --- |
| `images` | 样式树可能使用的图片标识，也包括文档已经提供的标识 |
| `faces` | 上游字体回退使用的待加载字形标识 |
| `font_files` | 每个已使用字形接下来要加载的 `@font-face` 文件 URL |

该查询不会访问网络或文件系统。它使用同步调用，并采用与渲染相同的布局选项和栅格缩放。
对于缩放为 `S` 的栅格输出，请传入 `scale=S`：`needs()` 会用相同方式扩大视口并使用相同
的设备像素比，因此分辨率媒体查询与视口取整结果一致。测量和 SVG 布局使用缩放 1，查询
这两类输出时应使用默认值 `scale=1.0`。

```python
from dataclasses import replace

from takumi_py import (
    Document,
    FontError,
    ImageResource,
    LayoutOptions,
    Renderer,
    compile_document,
)

html = """
<style>
  @font-face {
    font-family: Article;
    src: url("https://assets.example/article.woff2");
  }
  .hero {
    width: 1200px;
    height: 630px;
    font-family: Article;
    background-image: url("https://assets.example/background.png");
  }
</style>
<div class="hero">Hello</div>
"""

layout = LayoutOptions(width=1200, height=630)
raster_scale = 2.0
renderer = Renderer()
compiled = compile_document(Document.from_html(html))
needs = renderer.needs(compiled, layout=layout, scale=raster_scale)

if needs.images:
    compiled = compiled.with_resources(
        [ImageResource(url, fetch_bytes(url)) for url in needs.images]
    )

for url in needs.font_files:
    try:
        renderer.load_font_file(url, fetch_bytes(url))
    except FontError:
        layout = replace(
            layout,
            failed_font_files=(*layout.failed_font_files, url),
        )

# Loading or failing one source can expose the next fallback source, or SVG text
# inside an image that was not otherwise needed.
needs = renderer.needs(compiled, layout=layout, scale=raster_scale)
```

`images` 不是缺失资源列表。它包含已经通过 `Document` 提供的 URL，因此应把它当作当前级联
使用的图片集合，而不是循环到它为空。`faces` 为注册待加载字形的绑定保留；Python 通常
一次性注册字体的 API 不会创建这些标识。

如果需要节点与样式表的保守资源清单，可以继续使用
`CompiledDocument.resource_urls()` 和 `missing_resources()`。当应用需要知道样式树实际
会访问哪些图片和字体文件时，应优先使用 `needs()`。

## CSS `@font-face` 文件 { #font-face-files }

Takumi 2.20 会从渲染样式表计算 `@font-face` 规则。字体族、字重、样式、来源顺序和
`unicode-range` 都由 CSS 决定，应用只提供字节：

```python
renderer.load_font_file(url, data)
```

用这种方式加载的文件属于渲染器，直到调用 `renderer.forget_font_file(url)` 或
`renderer.clear_fonts()`。它们不计入 `cache_font()` 的预算，也不同于通过
`FontResource` 注册的字体族。`load_font_file()` 对不可用字体数据抛出 `FontError`；
加载失败不会悄悄把该 URL 标记为不可用。

如果应用下载失败，请为本次调用设置 `LayoutOptions.failed_font_files`。该设置会创建
快照，只对一个渲染器操作生效，并允许 Takumi 选择下一个 `src`。更改已加载或失败的
文件后，应再次查询 `needs()`。

## HTML `<style>` 元素 { #html-style-elements }

HTML 解析器现在会在返回节点树的同时，返回符合条件 `<style>` 元素中的 CSS。
`Renderer.compile_html()` 通过 `CompiledHtml` 暴露二者；`render_html()`、
`measure_html()`、`render_svg_html()` 和模板适配器会自动应用内嵌 CSS。

- 接受没有 `type`、`type` 为空或大小写不敏感的 `text/css`。
- CSS 按文档顺序保留。
- 非空 `media` 属性会被包成作用于该代码块的 `@media` 规则。
- 显式作者样式表先应用，文档内嵌样式后应用。
- 不解析或抓取 `<link>`、脚本、外部样式表和 `<base>` URL。URL 字符串保持原始写法，
  仍按该字符串匹配显式提供的资源。

删除应用以前手工复制到 `stylesheets=` 中的 `<style>` 内容。如果应用还显式传入了用作
作者覆盖的相同 CSS，只保留覆盖规则，并让文档中的内嵌规则提供基础样式。

HTML 与模板入口仍会以容错方式编译浏览器作者 CSS。`compile_stylesheet()` 默认仍使用
严格解析。

## 预期渲染变化 { #expected-rendering-changes }

Takumi 2.18 到 2.20 增加了更多与 Chromium 对齐的行为。HTML 中的内联 SVG 会从宿主元素
继承属性，并在自身样式之前接受页面样式表。布局还新增或改进了 CSS 数学函数、带类型的
`@property`、计数器、表单文本字段、`:has()`、`:disabled` 及相关表单状态、
`line-clamp`、命名页面、表格、flex、grid、SVG 文本和 SVG 滤镜。

请重新生成视觉基准图，并用 Chrome 对比可疑差异。即使 Python 输入没有变化，部分文档也
会移动几何位置或改变像素。

上游 2.20 还在内部提供分页栅格 API 和 `@page` 支持。此次升级不会给 Python API 增加
分页或 PDF 输出。

## 升级清单 { #upgrade-checklist }

- [ ] 测试前先针对新的原生依赖重新构建扩展。
- [ ] 用解析后的文档样式替代手工复制的 HTML `<style>` CSS。
- [ ] 使用应用实际采用的每个布局和栅格缩放调用 `Renderer.needs()`。测量和 SVG 使用
  默认缩放 1。
- [ ] 显式获取报告的图片和 `@font-face` 文件。
- [ ] 用 `LayoutOptions.failed_font_files` 表示字体下载失败。
- [ ] 已加载或失败输入变化后再次查询 `needs()`。
- [ ] 重新生成并审查栅格、SVG 和测量基准。
- [ ] 打包时审查新的上游与第三方许可证通知。
