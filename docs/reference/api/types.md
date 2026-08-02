# Nodes and result types

The Python type layer defines node inputs, measurement results, and animation scenes.

`AnimationScene.duration_ms` and `RawAnimationFrame.duration_ms` must be positive.
Raw animation frames also require positive dimensions and exactly
`width * height * 4` RGBA bytes.

`RawRgbaImage` describes decoded row-major RGBA pixels used as an `ImageNode.src`.
Its byte length follows the same `width * height * 4` contract.

::: takumi_py.types.TextNode

::: takumi_py.types.ImageNode

::: takumi_py.types.RawRgbaImage

::: takumi_py.types.ContainerNode

::: takumi_py.types.MeasuredNode

::: takumi_py.types.MeasuredTextRun

::: takumi_py.types.AnimationScene

::: takumi_py.types.RawAnimationFrame

::: takumi_py.types.validate_node
