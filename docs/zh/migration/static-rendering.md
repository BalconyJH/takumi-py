# 迁移到自有位图

下一主版本的文档 API 把原本隐藏在一次性字节渲染调用中的三个操作分开：

1. 编译节点、HTML 文档或已经渲染的 Jinja 模板。
2. 布局并绘制一个保留的 `RasterImage`。
3. 把这些像素编码为 PNG、JPEG、WebP、ICO 或原始 RGBA 字节。

`Renderer.render(document, ...)` 仍是只需要一个编码结果的便捷入口。同一组像素需要输出
多种格式，或需要在源渲染器释放后继续使用时，新路径更合适。

## 改动前后 { #before-and-after }

| 需求 | 以前的一次性调用形状 | 下一主版本的静态形状 |
| --- | --- | --- |
| 一个编码文件 | `renderer.render(document, output=...)` | 保持不变 |
| 一次布局输出 PNG 和 WebP | 两次独立渲染 | `image = renderer.rasterize(...)` 后分别编码 |
| 已知尺寸的原始 RGBA | `render(..., output=RasterOptions(format="raw"))` 并在外部记录尺寸 | `image.tobytes()`、`image.size` 和 `image.stride` |
| 在另一文档中复用图片 | 解码已经编码的图片字节 | `image.to_raw_source()` 或 `image.to_fragment()` |
| 从 Jinja 模板构建 | 直接输出 HTML 或编码字节 | `TemplateRenderer.document(...)`，再编译并选择输出 |

下一主版本预览期间，以前的 API 仍然可用。

## 渲染一次，重复编码 { #render-once }

`Renderer.rasterize` 只执行一次布局、解码和绘制。返回的 `RasterImage` 拥有原生位图；每次
调用 `encode` 都读取同一份位图。

```python
from takumi_py import Document, LayoutOptions, Renderer, compile_document

document = Document.from_node(
    {
        "type": "container",
        "style": {
            "width": "1200px",
            "height": "630px",
            "backgroundColor": "#0f172a",
        },
    }
)
compiled = compile_document(document)

image = Renderer().rasterize(
    compiled,
    layout=LayoutOptions(width=1200, height=630),
    scale=2,
)

png = image.encode("png")
webp = image.encode("webp", quality=90)
raw_rgba = image.tobytes()

assert image.size == (2400, 1260)
assert len(raw_rgba) == image.nbytes == image.stride * image.height
```

需要在多种格式间保持一致像素时，不要为每种格式分别调用 `Renderer.render`。这些调用会
有意执行独立布局和位图化。已经绘制出的像素而不只是编译源是复用边界时，请保留
`RasterImage`。

## 把模板转换为文档 { #template-document }

`TemplateRenderer.document(...)` 先渲染一次 Jinja，再把得到的 HTML、资源、样式表和解析
器选项快照为 `Document`。它既不保留 Jinja 环境，也不选择输出格式。

```python
from takumi_py import (
    Document,
    ImageResource,
    LayoutOptions,
    Renderer,
    TemplateRenderer,
    compile_document,
)

cover = b"""
<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160">
  <rect width="160" height="160" fill="#38bdf8"/>
</svg>
"""

template = TemplateRenderer("templates")
document: Document = template.document(
    "static_card.html.jinja",
    {"title": "Static card", "subtitle": "Reusable output"},
    resources=[ImageResource("https://assets.example/cover.svg", cover, cache="none")],
    stylesheets=[
        ".card { width: 640px; height: 320px; }",
    ],
)

compiled = compile_document(document)
assert compiled.missing_resources() == ()

image = Renderer().rasterize(
    compiled,
    layout=LayoutOptions(width=640, height=320),
)
```

独立函数 `render_template_to_document` 提供相同的适配能力，无需构造
`TemplateRenderer`。

## 资源发现 { #resource-discovery }

`CompiledDocument.resource_urls()` 报告已编译节点和样式表中的图片引用。
`missing_resources()` 会移除文档已经提供的引用，并忽略自包含的 data URL 和内联 SVG
标记。两个方法都不会访问网络。

这是一个保守的图片引用诊断，不是完整的已编译资源闭包，也不会阻止渲染。请在应用代码中
获取它报告的内容，再用 `CompiledDocument.with_resources()` 附加字节，或者在构造源文档
时传入 `ImageResource`。`with_resources()` 复用已编译节点和样式表，不会再次解析。

`Renderer.needs(document, *, layout=None, scale=1.0)` 报告级联后的资源集合。准备栅格
输出时，请传入与 `render()` 的 `RasterOptions` 或 `rasterize()` 相同的缩放值。该查询会
用与栅格化相同的方式扩大视口并设置设备像素比，因此分辨率媒体查询和取整后的视口尺寸也
一致。测量与 SVG 布局使用缩放 1，为 `measure()` 或 `render_svg()` 查询资源时应使用
默认值 `scale=1.0`。

编码后的图片字节会复制一次到已编译文档的不透明原生快照。文档渲染借用该快照，因此不会
在每次调用时从 Python 重新上传相同字节。这不是零拷贝：文档构造和校验仍会复制。解码后的
图片也保留在各渲染器的缓存中，不属于文档。字体等其他输入仍需显式交给渲染器。

## 组合与像素归属 { #composition-and-ownership }

`RasterImage` 使用紧密排列、按行优先的 RGBA8 和 non-premultiplied alpha。`data` 和
`tobytes()` 会把原生缓冲区复制为 Python bytes。`to_raw_source()` 把它复制到
`RawRgbaImage` 映射，`to_fragment()` 则把该映射包装成图片 `Fragment`。后者可以像其他
fragment 一样参与文档组合，并携带自己的资源快照。

`RasterImage.from_raw(data, width=..., height=...)` 接受由 Takumi 之外生成的同一种像素
布局。缓冲区长度必须恰好等于 `width * height * 4`。

## SVG 输出中的矢量资源 { #vector-resource-output }

`Renderer.render_svg()` 可以把矢量 `ImageResource`（包括
`MathSvg.to_image_resource()`）扁平化为宿主 SVG 中的几何。对于矢量公式，这通常会生成
经过变换的 `<path>` 元素，而不会保留嵌入的 `<image>` 或 `data:image/svg+xml` URL。
栅格图片来源仍可能需要 `<image>` 回退。文档保留原始资源字节和标识，渲染后的 SVG 则
可能采用不同的内部表示。请验证路径、几何和可见输出，不要假定某一种固定图片序列化形式。

## 布局与线程边界 { #layout-and-threading }

保留对象是已经完成的位图。Takumi 的布局 scene 不属于 Python API。它包含只适合单一
线程的缓存，不能当作通用 `Send`/`Sync` scene 在 Python 工作线程之间移动。因此，公共
静态 API 暴露的是位图输出复用，而不是不透明的 scene 对象。

`Renderer.measure` 和 `Renderer.render_svg` 仍会独立布局已编译文档。编码现有
`RasterImage` 不会执行其中任何一种操作。

## 迁移清单 { #migration-checklist }

- [ ] 一次性编码字节继续使用 `Renderer.render`。
- [ ] 多格式或需要保留的静态输出改用 `Renderer.rasterize` 和
  `RasterImage.encode`。
- [ ] 使用 `TemplateRenderer.document` 或 `render_template_to_document` 把 Jinja
  模板渲染为 `Document`。
- [ ] 在假定图片输入已经完整之前，检查 `CompiledDocument.resource_urls()` 和
  `missing_resources()`。
- [ ] 使用与计划输出相同的布局和栅格缩放调用 `Renderer.needs()`；测量和 SVG 使用
  缩放 1。
- [ ] 像素需要跨原生边界时，使用 `tobytes()` 或 `to_raw_source()`。
- [ ] 动画时间和编码继续使用现有动画 API。
