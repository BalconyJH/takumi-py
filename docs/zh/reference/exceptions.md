# 异常

所有公共异常类都可以从 `takumi_py` 导入。

| 异常 | 典型边界 |
| --- | --- |
| `TakumiError` | 绑定暴露的基类 |
| `NodeValidationError` | Python 输入与类型化节点结构不符 |
| `NodeDecodeError` | 无法解码原生节点或测量结果 |
| `HtmlParseError` | HTML 解析器拒绝了输入 |
| `StyleSheetError` | CSS 或关键帧编译失败 |
| `FontError` | 字体描述、解析或注册失败 |
| `ResourceError` | 图片或其他资源无效或无法解码 |
| `RenderError` | 图片、SVG 或动画帧的布局或渲染失败 |
| `AnimationError` | 动画编码失败，或动画格式、原始帧无效 |
| `UnsupportedFormatError` | 请求的输出格式不受支持 |

请捕获最窄的有用异常。只在有意把绑定的所有失败都转换为应用级错误的 API 边界上捕获
`TakumiError`：

```python
from takumi_py import FontError, FontResource, Renderer

try:
    Renderer().register_font(FontResource(b"not a font"))
except FontError as error:
    raise ValueError("invalid configured font") from error
```

!!! danger "保留原始错误"

    不要捕获 `Exception` 后丢弃原因。原生错误信息携带了定位非法渲染输入所需的上下文。
