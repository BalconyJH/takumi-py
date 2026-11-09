# 选项与资源

这些类型把渲染、动画、HTML 解析、字体和图片输入组织在一起。

通用的校验约定：

- 设置 `RenderOptions.lang` 时，它必须是合法的 BCP-47 语言标签。
- 设置 `FontResource.weight` 时，它必须是 1 到 1000 的有限数。
- `FontResource.unicode_range` 的每一项都是满足 `0 <= start <= end <= 0x10FFFF` 的
  `(start, end)` 闭区间。
- `LayoutOptions.failed_font_files` 是本次操作中应用侧下载失败的 `@font-face` URL
  序列。
- `AnimationEncodeOptions.quality` 接受 0 到 100，`webp_speed` 接受 0 到 6。

违反这些数值或语言标签约定时抛出 `ValueError`。

::: takumi_py.options.RenderOptions

::: takumi_py.options.AnimationEncodeOptions

::: takumi_py.options.HtmlOptions

::: takumi_py.options.LayoutOptions

::: takumi_py.options.ImageResource

::: takumi_py.options.FontResource

## 结构化关键帧 { #structured-keyframes }

可以把结构化关键帧传给渲染方法，或存入 `RenderOptions.keyframes`。映射形式使用动画名称
作为键。

在提供 `keyframes` 覆盖参数的渲染入口中，省略该参数会继承适用的 renderer、template
或 `RenderOptions.keyframes` 值；传入关键帧会替换该值，传入 `None` 则会清除它。

::: takumi_py.options.Keyframe

::: takumi_py.options.KeyframesRule
