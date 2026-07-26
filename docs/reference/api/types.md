# Nodes and result types

The Python type layer defines node inputs, measurement results, and animation scenes.

`AnimationScene.duration_ms` and `RawAnimationFrame.duration_ms` must be positive.
Raw animation frames also require positive dimensions and exactly
`width * height * 4` RGBA bytes.

::: takumi_py.types.TextNode

::: takumi_py.types.ImageNode

::: takumi_py.types.ContainerNode

::: takumi_py.types.MeasuredNode

::: takumi_py.types.MeasuredTextRun

::: takumi_py.types.AnimationScene

::: takumi_py.types.RawAnimationFrame

::: takumi_py.types.validate_node
