# 字体与图片

!!! important "渲染器从不抓取资源"

    在应用代码中把外部资源读取为 `bytes`，并在渲染边界显式传入。这样网络访问、认证、
    重试和持久缓存都留在渲染器之外。

## 图片 { #images }

图片节点通过 `src` 引用图片。每个 `src` 对应的字节通过单次渲染的 `images` 选项提供：

```python
from pathlib import Path

from takumi_py import ImageResource, Renderer

renderer = Renderer()
png = renderer.render_node(
    {"type": "image", "src": "memory://logo", "width": 128, "height": 128},
    width=128,
    height=128,
    images=[
        ImageResource(
            "memory://logo",
            Path("logo.svg").read_bytes(),
            cache="none",
        )
    ],
)
```

`ImageResource.cache` 接受 `"auto"` 或 `"none"`，并会传给渲染器的资源缓存。元组简写
`("memory://logo", data)` 仍受支持，使用 `"auto"`。以 `data:` URI 内嵌的图片完全不需要
提供资源。

### 原始 RGBA 像素 { #raw-rgba-pixels }

像素已经按行优先解码为 RGBA 时，使用 `RawRgbaImage`，可以省去一次图像编解码往返：

```python
from takumi_py import RawRgbaImage, Renderer

source: RawRgbaImage = {
    "width": 2,
    "height": 2,
    "data": bytes([255, 0, 0, 128] * 4),
}

png = Renderer().render_node(
    {"type": "image", "src": source, "width": 2, "height": 2},
    width=2,
    height=2,
)
```

字节长度必须恰好等于 `width * height * 4`。数据默认使用非预乘 alpha。只有当 RGB
通道已经乘过 alpha 时，才设置 `premultiplied=True`。

### 自有位图对象 { #owned-raster-images }

`Renderer.rasterize` 返回拥有已完成原生位图的 `RasterImage`。与再次调用 `render` 不同，
编码另一种格式不会重复布局、资源解码或绘制：

```python
from takumi_py import Document, LayoutOptions, Renderer, compile_document

document = Document.from_node(
    {
        "type": "container",
        "style": {
            "width": "320px",
            "height": "180px",
            "backgroundColor": "#111827",
        },
    }
)
compiled = compile_document(document)

image = Renderer().rasterize(
    compiled,
    layout=LayoutOptions(width=320, height=180),
    scale=2,
)

png = image.encode("png")
webp = image.encode("webp", quality=85)
raw_rgba = image.tobytes()

assert image.size == (640, 360)
assert image.stride == image.width * 4
assert len(raw_rgba) == image.nbytes == image.stride * image.height
```

位图使用紧密排列、按行优先的 RGBA8 和 non-premultiplied alpha。它的原生存储不依赖
生成它的渲染器或文档。`data` 和 `tobytes()` 会把像素复制成 Python bytes。
`to_raw_source()` 返回 `RawRgbaImage`，`to_fragment()` 则返回携带复制像素的图片
`Fragment`，可传给 `Document.from_node`。

`RasterImage.from_raw(data, width=..., height=...)` 导入现有的紧密排列 RGBA8 缓冲区，
其字节数必须等于 `width * height * 4`。

`RasterImage.encode` 与一次性渲染 API 遵循相同的编码规则：支持 PNG、JPEG、有损或无
损 WebP、ICO 和 `"raw"`。省略 `quality` 时 WebP 默认使用无损编码。`lossless` 只适用于
WebP，并且 `lossless=True` 不能与 `quality` 同时使用。

### 发现图片引用 { #discover-image-references }

编译完成后，`CompiledDocument.resource_urls()` 会合并节点和样式表中的图片引用，返回
去重并排序后的元组。`CompiledDocument.missing_resources()` 会把这些引用与文档已经拥有
的 `ImageResource.src` 比较：

```python
from takumi_py import Document, ImageResource, compile_document

compiled = compile_document(
    Document.from_html(
        '<img src="https://cdn.example/hero.png"><div class="backdrop"></div>',
        resources=[
            ImageResource("https://cdn.example/hero.png", downloaded_hero),
        ],
        stylesheets=[
            '.backdrop { background-image: url("https://cdn.example/pattern.png"); }',
        ],
    )
)

print(compiled.resource_urls())
print(compiled.missing_resources())
```

资源发现不会访问网络。小写 `data:` URL、内联 `<svg` 标记，以及已经用相同 `src`
提供的引用不会出现在 `missing_resources()` 中。应把结果当作保守的图片引用诊断，而不是
所有未来渲染输入都已就绪的证明：它既不会获取 URL，也不提供完整的级联后资源闭包。请把
获取到的字节传入 `ResourceSet` 或文档的 `resources` 输入。

`missing_resources()` 只报告信息，不会拒绝渲染。`CompiledDocument.with_resources()` 可在
发现资源后附加图片，同时复用现有的原生节点和样式表句柄。同一 `src` 的定义发生冲突时
抛出 `ResourceError`。

### 优先使用 `Renderer.needs()` { #renderer-needs }

样式化文档实际会访问哪些图片标识和字体文件，应使用
`Renderer.needs(document, *, layout=None, scale=1.0)` 查询。缩放规则与栅格输出一致：
它会像 `render()` 或 `rasterize()` 那样扩大视口并设置设备像素比。调用时应传入计划用于
栅格操作的同一个缩放值。`measure()` 和 `render_svg()` 使用缩放 1；为这些输出查询时，
请使用默认值 `scale=1.0`。其他布局选项和字体失败列表也会应用于本次查询：

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

renderer = Renderer()
compiled = compile_document(Document.from_html(html))
layout = LayoutOptions(width=1200, height=630)
raster_scale = 2.0
needs = renderer.needs(compiled, layout=layout, scale=raster_scale)

supplied = {resource.src for resource in compiled.resources.images}
pending_images = set(needs.images) - supplied
if pending_images:
    compiled = compiled.with_resources(
        [ImageResource(url, fetch_bytes(url)) for url in sorted(pending_images)]
    )

for url in needs.font_files:
    try:
        data = fetch_bytes(url)
    except OSError:
        layout = replace(
            layout,
            failed_font_files=(*layout.failed_font_files, url),
        )
        continue
    try:
        renderer.load_font_file(url, data)
    except FontError:
        layout = replace(
            layout,
            failed_font_files=(*layout.failed_font_files, url),
        )

# Supplying pixels or changing a font source can reveal fallback sources and
# SVG text read from decoded images.
needs = renderer.needs(compiled, layout=layout, scale=raster_scale)
```

`needs.images` 不包含 `data:` URI 和内联 SVG，但会包含文档已经提供的标识，因此应与
`compiled.resources` 求差，而不是循环到集合为空。`needs.font_files` 报告每个已使用
`@font-face` 的下一个来源；请显式加载该来源，把应用侧下载失败记录到
`LayoutOptions.failed_font_files`，然后再次查询。字体数据不可用时抛出 `FontError`。
如果你的 HTTP 客户端使用其他异常类型，请替换示例中的 `OSError`。

`needs()` 不会访问网络或文件系统。`faces` 为分别管理字形的绑定保留上游待加载标识；
Python 的常规字体 API 通常让它保持为空。另一资源可用后，SVG 文本和回退来源可能增加新
需求，因此每次有实质输入变化后都应再次查询。请把 `raster_scale` 同样传给
`RasterOptions(scale=...)` 或 `Renderer.rasterize(..., scale=...)`；SVG 和测量则不要
额外设置缩放。

编译文档时，编码后的图片字节会复制一次到不透明的原生快照。文档渲染方法借用该快照，
避免每次渲染都从 Python 向 Rust 重新上传。这不是零拷贝：校验和文档快照仍拥有复制出的
字节，解码后的图片也仍是渲染器本地缓存中的条目。

## 字体 { #fonts }

字体注册在渲染器上，并在渲染器的整个生命周期内保持注册：

```python
from pathlib import Path

from takumi_py import FontResource, Renderer

renderer = Renderer(load_default_fonts=False)
families = renderer.register_font(
    FontResource(
        Path("Inter-Regular.woff2").read_bytes(),
        name="Inter",
        weight=400,
        style="normal",
        generic_family="sans-serif",
    )
)

png = renderer.render_node(
    {"type": "text", "text": "Hello"},
    width=320,
    height=160,
    font_families=families,
    lang="en",
)
```

`register_font` 返回 Takumi 实际注册的字体族名称。把该结果传给 `font_families`，即可
为一次渲染选择确定的回退栈。Takumi 可以读取 TrueType、OpenType、WOFF 和 WOFF2 数据。

`FontResource` 的字段会覆盖字体文件自身的声明：

| 字段 | 约定 |
| --- | --- |
| `name` | 注册使用的字体族名称；默认取文件中的名称 |
| `weight` | 1 到 1000 的有限数；否则抛出 `ValueError` |
| `style` | CSS `font-style` 语法，例如 `"normal"`、`"italic"` 或 `"oblique 12deg"`；否则抛出 `FontError` |
| `generic_family` | 该字体对应的通用字体族关键字，例如 `"sans-serif"` 或 `"monospace"` |
| `unicode_range` | 字体负责的闭区间码位范围，见 [字体子集](#font-subsets) |

!!! warning "内置字体的覆盖范围有意保持很窄"

    内置的 Geist 只是拉丁文字的最后回退。请为非拉丁文字、emoji 或品牌字形注册合适的
    字体，不要依赖宿主操作系统上安装的字体。

### 字体子集 { #font-subsets }

把同一字体族的每个子集都注册在相同的 `name` 下，并附上其 `@font-face` 声明的
`unicode_range`。与 Chrome 一样，每个子集只负责其 `(start, end)` 闭区间内的码位，
因此文本会按字符选择正确的文件：

```python
renderer.register_fonts(
    [
        FontResource(latin, name="Inter", unicode_range=[(0x0000, 0x00FF)]),
        FontResource(cyrillic, name="Inter", unicode_range=[(0x0400, 0x045F)]),
    ]
)
```

每个范围都必须满足 `0 <= start <= end <= 0x10FFFF`，否则抛出 `ValueError`。没有
`unicode_range` 时，后注册的同名、同描述符字体会遮蔽先注册的字体，正如浏览器中后出现的
`@font-face` 规则一样。

`FontResource.subset_of` 已弃用：Takumi 现在只把它当作字体族名称，取代 `name`。迁移
按子集命名的字体族，请参阅 [升级到 Takumi 2.17](../migration/takumi-2.17.md#font-subsets)。

### 释放字体 { #releasing-fonts }

`unregister_font(name)` 移除某个字体族下注册的所有字形，包括它的全部 `unicode_range`
子集，并返回该字体族此前是否存在。`clear_fonts()` 移除所有已注册的字体，包括传给构造
函数的字体；只有在渲染器以 `load_default_fonts=True` 创建时，才会保留内置的 Geist
回退字体。

```python
renderer.unregister_font("Inter")
renderer.clear_fonts()
```

### 按需缓存字体 { #caching-fonts-on-demand }

按请求加载字体的服务（例如加载用户选择的字体族）可以让渲染器在预算内持有这些字体，而不必
把每个字体都永久注册。`cache_font(font, key)` 以某个键（例如字体的来源 URL）注册字体；
在渲染器仍持有该字体时，`cached_fonts(key)` 返回它的字体族，否则返回 `None`。下例中的
`download` 代表你自己的 HTTP 客户端：

```python
from takumi_py import Renderer

renderer = Renderer(font_cache_max_bytes=64 * 1024 * 1024)


def font_families(url: str) -> tuple[str, ...]:
    return renderer.cached_fonts(url) or renderer.cache_font(download(url), url)


png = renderer.render_html(html, font_families=list(font_families(url)))
```

解码后的字体数据超过 `font_cache_max_bytes` 时，渲染器会释放最久未使用的缓存字体族。渲染
会把其 `font_families` 中的字体族标记为已使用，命中 `cached_fonts()` 也会；
`cached_fonts(key, pin=True)` 会永久保留该字体。通过 `register_font`、`register_fonts` 或
构造函数注册的字体永远不会被释放，最后缓存的字体即使单独超出预算也会保留。
`unregister_font` 和 `clear_fonts` 同样会清除缓存记录。

## 语言 { #language }

渲染级 `lang` 选项影响文本整形和断行。它必须是合法的 BCP-47 语言标签；所有渲染、测量、
SVG 和动画入口都会以 `ValueError` 拒绝非法标签。

渲染级 `lang` 不会写入节点属性，因此不会让 CSS `:lang()` 选择器生效。请在确立语言的
HTML 元素或节点上设置 `lang`：

=== "HTML"

    ```python
    renderer.render_html(
        '<section lang="zh-Hant"><div class="headline">你好</div></section>',
        stylesheets=[
            '.headline:lang(zh-Hant) { font-family: "Noto Sans TC"; }',
        ],
    )
    ```

=== "节点树"

    ```python
    renderer.render_node(
        {
            "type": "container",
            "lang": "ja",
            "children": [{"type": "text", "text": "こんにちは"}],
        },
        stylesheets=[':lang(ja) { font-family: "Noto Sans JP"; }'],
    )
    ```

## 缓存预算 { #cache-budgets }

`Renderer(cache_max_bytes=...)` 设置该渲染器的解码图片、缩放后的图片变体、SVG 栅格以及
相关渲染资源共享的字节预算。以 `data:` URI 内嵌的图片也经过同一缓存解码，因此内嵌了
logo 的模板在每个渲染器中只解码一次，而不是每次渲染都解码。默认值为 64 MiB；传入 `0`
则不保留任何缓存。通过 `cache_font` 持有的字体另有预算 `font_cache_max_bytes`，详见
[按需缓存字体](#caching-fonts-on-demand)。

字形遮罩和轮廓使用单独的进程级缓存，默认 8 MiB。对于以 CJK 文字为主的工作负载，请在
进程首次渲染之前配置它：

```python
from takumi_py import Renderer, set_glyph_cache_max_bytes

set_glyph_cache_max_bytes(32 * 1024 * 1024)
renderer = Renderer(cache_max_bytes=128 * 1024 * 1024)
```

字形渲染开始之后再修改字形预算，不会改变已有进程级缓存的大小。

## 生命周期 { #lifecycle }

| 资源 | 推荐生命周期 | API |
| --- | --- | --- |
| 字体 | 渲染器生命周期 | `register_font` 或 `register_fonts`；用 `unregister_font` 或 `clear_fonts` 释放 |
| 缓存字体 | 直到因空间不足被释放 | `cache_font`，用 `cached_fonts` 检查，受 `font_cache_max_bytes` 约束 |
| 图片 | 单次渲染 | `images=[ImageResource(...)]` |

??? info "已移除的兼容 API"

    0.4.0 移除了 0.2.0 起弃用的兼容层：`load_font`、`load_fonts`、`fetched_resources`、
    `persistent_images`、`put_persistent_image` 和 `clear_image_store`。
    [Takumi v2 迁移](../migration/takumi-v2.md#resource-apis)列出了它们的替代方式。

可运行示例见
[`examples/render_resources.py`](https://github.com/BalconyJH/takumi-py/blob/main/examples/render_resources.py)
和
[`examples/render_static.py`](https://github.com/BalconyJH/takumi-py/blob/main/examples/render_static.py)。
