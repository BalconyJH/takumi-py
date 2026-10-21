# 节点与结果类型

Python 类型层定义了节点输入、测量结果和动画场景。

`AnimationScene.duration_ms` 和 `RawAnimationFrame.duration_ms` 必须为正。原始动画帧
还要求尺寸为正，并且恰好包含 `width * height * 4` 个 RGBA 字节。

`RawRgbaImage` 描述用作 `ImageNode.src` 的、已解码的按行优先 RGBA 像素。它的字节长度
遵循同样的 `width * height * 4` 约定。

::: takumi_py.types.TextNode

::: takumi_py.types.ImageNode

::: takumi_py.types.RawRgbaImage

::: takumi_py.types.ContainerNode

::: takumi_py.types.MeasuredNode

::: takumi_py.types.MeasuredTextRun

::: takumi_py.types.AnimationScene

::: takumi_py.types.RawAnimationFrame

::: takumi_py.types.validate_node
