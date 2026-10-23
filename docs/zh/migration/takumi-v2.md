# 迁移到 Takumi v2

Takumi v2 用显式的资源输入取代了隐式的渲染器级资源上下文，并让 Python 绑定更直接地
映射到核心。

## 资源 API { #resource-apis }

| 已移除的接口 | 替代方式 |
| --- | --- |
| 渲染调用和 `RenderOptions` 上的 `fetched_resources=` | 为每次渲染传入 `images=[ImageResource(...)]` |
| `load_font` / `load_fonts` | `register_font` / `register_fonts`，它们会返回已注册的字体族名 |
| `Renderer(persistent_images=...)`、`put_persistent_image`、`clear_image_store` | 把图片传给每次用到它们的渲染 |

这些接口自 0.2.0 起弃用，并已在 0.4.0 中移除。仍在使用它们的代码会因关键字参数抛出
`TypeError`，因方法抛出 `AttributeError`；升级前请先在 0.3 下消除所有
`DeprecationWarning`。

## HTML 与样式表 { #html-and-stylesheets }

HTML 解析现在由 Takumi 的 Rust 解析器完成。HTML 的渲染、测量、SVG 和模板调用都通过
`stylesheets=[...]` 显式接收文档级 CSS，内联 `style` 属性则随 HTML 一起解析。使用
`HtmlOptions` 自定义解析器预设、Tailwind 属性或深度上限。详见
[HTML 与 CSS](../guides/html.md)。

## 字体与语言 { #fonts-and-language }

- `FontResource` 接受 `name`、`weight`、`style`、`generic_family` 和 `unicode_range`
  描述符。字重覆盖值必须是 1 到 1000 的有限数。自 Takumi 2.17 起，请把同一字体族的每个
  子集都注册在同一个 `name` 下并附上各自的 `unicode_range`，见
  [升级到 Takumi 2.17](takumi-2.17.md#font-subsets)。
- `register_font(s)` 返回实际注册的字体族名称，可以作为 `font_families` 传给渲染调用。
- 渲染级 `lang` 影响文本整形和断行；CSS `:lang()` 仍取决于 HTML 或节点上的属性。非法的
  渲染级 BCP-47 标签会抛出 `ValueError`。
- 内置回退字体现在是作为最后回退的拉丁文字 Geist。调用方提供的字体会优先参与常规回退。

## 图片与 URL { #images-and-urls }

`ImageResource.cache` 直接对应 Takumi 的图片缓存提示，适用于每张单次渲染图片。图片节点
还接受已解码的 `RawRgbaImage` 像素。`CompiledNode.resource_urls()`
报告 HTTP(S) 图片和样式引用，但不会下载它们，也不会报告已经提供的 `memory://` 字节。
详见 [字体与图片](../guides/resources.md)。

## 动画与输出 { #animation-and-output }

- 通过 `keyframes=` 或 `RenderOptions(keyframes=...)` 传入结构化关键帧。
- 既未指定 `quality` 也未指定 `lossless` 时，WebP 默认无损；`quality` 与
  `lossless=True` 同时出现会被拒绝。
- 使用 `render_svg_node`、`render_svg_html`、`render_svg_template` 或
  `render_svg_compiled` 渲染 SVG。

## 迁移清单 { #migration-checklist }

- [ ] 用显式的 `ImageResource` 输入取代隐式的抓取资源。
- [ ] 用注册 API 取代弃用的字体加载函数。
- [ ] 通过 `stylesheets` 传入文档级 CSS。
- [ ] 为渲染文本用到的每种文字注册字体。
- [ ] 验证应用用到的位图、SVG、测量和动画输出。

!!! warning "迁移后的布局变化"

    先检查 Web 平台默认值：`position`、边框和轮廓宽度、`transform-origin`、
    `object-position` 以及 SVG 的 `currentColor` 继承。
