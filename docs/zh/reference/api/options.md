# 选项与资源

这些类型把渲染、动画、HTML 解析、字体和图片输入组织在一起。

通用的校验约定：

- 设置 `RenderOptions.lang` 时，它必须是合法的 BCP-47 语言标签。
- 设置 `FontResource.weight` 时，它必须是 1 到 1000 的有限数。
- `FontResource.unicode_range` 的每一项都是满足 `0 <= start <= end <= 0x10FFFF` 的
  `(start, end)` 闭区间。
- `AnimationEncodeOptions.quality` 接受 0 到 100，`webp_speed` 接受 0 到 6。

违反这些数值或语言标签约定时抛出 `ValueError`。

::: takumi_py.options.RenderOptions

::: takumi_py.options.AnimationEncodeOptions

::: takumi_py.options.HtmlOptions

::: takumi_py.options.ImageResource

::: takumi_py.options.FontResource
