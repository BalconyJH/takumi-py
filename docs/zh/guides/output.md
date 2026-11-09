# 输出格式

所有输入都渲染到同一组输出：

| 输出 | API 系列 | 结果 |
| --- | --- | --- |
| PNG、JPEG、WebP、ICO | `render_*` | 编码后的 `bytes` |
| 原始 RGBA | 使用 `format="raw"` 的 `render_*` | 像素 `bytes` |
| 保留 RGBA | `Renderer.rasterize` | 可重复编码的 `RasterImage` |
| SVG | `render_svg_*` | `str` |
| 仅布局 | `measure_*` | `MeasuredNode` |
| WebP、APNG、GIF 动画 | `render_animation`、`encode_frames` | 编码后的 `bytes`，见 [动画](animation.md) |

## 位图 { #raster-images }

`format` 选择编码器，默认为 `"png"`。

```python
from takumi_py import Renderer

jpeg = Renderer().render_html(
    "<h1>Hello</h1>",
    width=320,
    height=160,
    format="jpeg",
    quality=90,
)
```

| 格式 | 编码器选项 |
| --- | --- |
| `"png"` | 无 |
| `"jpeg"` 或 `"jpg"` | `quality` 取 0 到 100，默认 75 |
| `"webp"` | 未设置 `quality` 时为无损；`lossless=True` 不能与 `quality` 同时使用 |
| `"ico"` | 无 |

`device_pixel_ratio` 把 CSS 长度缩放为输出像素。取 `2.0` 时，一个 `10px` 的盒子覆盖
20 个输出像素。显式的 `width` 和 `height` 以输出像素为单位设定画布尺寸，而由布局推断
的维度会随内容缩放。

`dithering="ordered-bayer"` 会在渐变填充量化到 8 位之前对其抖动，以减少平滑渐变中的
色带。

## 保留位图 { #retained-raster-images }

已经完成的像素需要多次编码时，使用 `Renderer.rasterize`。布局和绘制只执行一次，每次
`RasterImage.encode` 都读取保留的原生位图：

```python
from takumi_py import Document, LayoutOptions, Renderer, compile_document

compiled = compile_document(
    Document.from_node(
        {
            "type": "container",
            "style": {
                "width": "320px",
                "height": "160px",
                "backgroundColor": "#111827",
            },
        }
    )
)

image = Renderer().rasterize(
    compiled,
    layout=LayoutOptions(width=320, height=160),
    scale=2,
)

png = image.encode("png")
webp = image.encode("webp", quality=85)
rgba = image.tobytes()

assert image.size == (640, 320)
assert len(rgba) == image.nbytes == image.stride * image.height
```

位图不可变，并且可以在渲染器释放后继续使用。只需要一个编码结果时，一次性 `render`
入口更简单。

## 原始 RGBA { #raw-rgba }

`format="raw"` 跳过编码，返回按行优先排列、使用非预乘 alpha 的 RGBA 字节，每像素
4 字节：

```python
from takumi_py import Renderer

raw = Renderer().render_node(
    {
        "type": "container",
        "style": {"width": "24px", "height": "12px", "backgroundColor": "white"},
    },
    width=None,
    height=None,
    format="raw",
)

assert len(raw) == 24 * 12 * 4
```

原始输出可以与 `encode_frames` 配合，在 Python 中拼装动画，也可以交给接受 RGBA
缓冲区的图像库。

## SVG { #svg }

`render_svg_node`、`render_svg_html`、`render_svg_template` 和 `render_svg_compiled`
返回 SVG 文档字符串：

```python
from takumi_py import Renderer

svg = Renderer().render_svg_html(
    '<div class="card">Hello</div>',
    stylesheets=[".card { width: 1200px; height: 630px; color: black; }"],
    width=1200,
    height=630,
)
```

SVG 输出接受视口、`font_size`、`time_ms`、图片、关键帧、字体族和 `lang`。编码器设置、
`device_pixel_ratio`、抖动和调试边框只作用于位图输出。

## 测量 { #measurement }

`measure_node`、`measure_html` 和 `measure_compiled` 只执行布局而不绘制，并返回
`MeasuredNode` 树：

```python
from takumi_py import Renderer

measured = Renderer().measure_node(
    {
        "type": "container",
        "style": {"width": "240px", "height": "120px"},
        "children": [{"type": "text", "text": "Hello"}],
    },
    width=None,
    height=None,
)

print(measured.width, measured.height)
for run in measured.runs:
    print(run.text, run.x, run.y, run.width, run.height)
```

每个 `MeasuredNode` 带有自身的 `width`、`height`、一个二维仿射 `transform`、
`children`，以及它所排版文本的 `MeasuredTextRun`。测量报告精确的布局尺寸；位图输出在
绘制时会把盒子对齐到整像素。

可运行示例见
[`examples/render_options_measure.py`](https://github.com/BalconyJH/takumi-py/blob/main/examples/render_options_measure.py)。
