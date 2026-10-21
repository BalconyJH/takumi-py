# 升级到 Takumi 2.17

下一个 takumi-py 版本会把原生渲染器从 Takumi 2.5.4 升级到 2.17.1。Python API 保持兼容，
但少数输入的含义发生了变化，Takumi 的输出也更接近 Chrome。

## 预期像素变化 { #expect-pixel-changes }

Takumi 2.6 到 2.17 移植了更多 Chromium 的布局与绘制行为：文本与行内布局、行高、文本装饰、
滤镜与 `backdrop-filter`、背景、边框、轮廓、`box-shadow`、表格以及 CSS 绘制顺序。在 2.5 下
正确的图片可能会偏移几个像素，或者在过去与浏览器不一致的地方发生变化。

升级后请重新生成基准图；把可疑的差异视为绑定回归之前，先与 Chrome 的渲染结果对比。上游的
[Takumi 变更日志](https://github.com/kane50613/takumi/blob/master/takumi/CHANGELOG.md)
列出了每一项渲染变化。

## 必需的改动 { #required-changes }

| 之前 | 之后 | 原因 |
| --- | --- | --- |
| 每个子集一个 `FontResource(name="Inter-latin", subset_of="Inter")` | 每个子集都使用 `FontResource(name="Inter", unicode_range=[...])` | `subset_of` 现在只设置字体族名称 |
| `font_families=["Inter-latin", "Inter-cyrillic"]` | `font_families=["Inter"]` | 子集不再以各自的名称注册 |
| `dithering="floyd-steinberg"` | `dithering="ordered-bayer"` | Takumi 移除了误差扩散，旧名称只是别名 |
| `render_animation(..., fps=60, format="gif")` | GIF 的 `fps` 不超过 50，WebP 与 APNG 不超过 90 | 更高的帧率现在会抛出 `ValueError` |

### 字体子集 { #font-subsets }

把同一字体族的每个子集都注册在该字体族自己的名称下，并附上其 `@font-face` 声明的码位
范围。Takumi 会用范围覆盖该码位的子集来渲染每个码位：

=== "Takumi 2.17"

    ```python
    from pathlib import Path

    from takumi_py import FontResource, Renderer

    renderer = Renderer()
    renderer.register_fonts(
        [
            FontResource(
                Path("Inter-Latin.woff2").read_bytes(),
                name="Inter",
                unicode_range=[(0x0000, 0x00FF)],
            ),
            FontResource(
                Path("Inter-Cyrillic.woff2").read_bytes(),
                name="Inter",
                unicode_range=[(0x0400, 0x045F)],
            ),
        ]
    )
    ```

=== "Takumi 2.5"

    ```python
    renderer.register_fonts(
        [
            FontResource(latin, name="Inter-latin", subset_of="Inter"),
            FontResource(cyrillic, name="Inter-cyrillic", subset_of="Inter"),
        ]
    )
    ```

`subset_of` 仍然可用，但会发出 `DeprecationWarning`，并且优先于 `name`，因此
`register_font` 返回的是 `subset_of` 的值。没有 `unicode_range` 时，后注册的同名、同描述符
字体会遮蔽先注册的字体，正如浏览器中后出现的 `@font-face` 规则一样。

## 行为变化 { #behavior-changes }

- 没有 `src` 属性的 `<img>` 会解析为一个空盒子，尺寸由其 `width` 和 `height` 决定，与
  Chrome 的绘制方式一致。过去它会抛出 `HtmlParseError`。
- `compile_stylesheet` 接受 Takumi 2.5 拒绝的 CSS，例如 `text-decoration: none`。Takumi
  仍无法解析的值依旧抛出 `StyleSheetError`。
- 渲染器资源缓存的默认值从 16 MiB 改为 64 MiB。以 `data:` URI 内嵌的图片现在经过该缓存
  解码，每个渲染器只解码一次。
- `render_animation` 把帧流式写入编码器，因此任何时刻只持有一帧原始图像。编码结果与之前
  完全相同。

## 新 API { #new-apis }

- `FontResource.unicode_range` 限定字体负责的码位。
- `Renderer.unregister_font(name)` 释放一个字体族及其全部子集。
- `Renderer.clear_fonts()` 释放所有已注册的字体；渲染器加载了内置回退字体时，只保留该
  字体。

用法见 [字体与图片](../guides/resources.md#font-subsets)。

## 升级清单 { #upgrade-checklist }

- [ ] 用一个字体族 `name` 加上每个子集各自的 `unicode_range` 取代 `subset_of`。
- [ ] 从 `font_families` 和 CSS `font-family` 中删除按子集命名的字体族名称。
- [ ] 把 `dithering="floyd-steinberg"` 换成 `"ordered-bayer"`。
- [ ] 让 GIF 的 `fps` 不超过 50，WebP 和 APNG 不超过 90。
- [ ] 使用 `-W error::DeprecationWarning` 运行测试套件，找出弃用的调用。
- [ ] 重新生成并审查基准图。
