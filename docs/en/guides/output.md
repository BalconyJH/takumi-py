# Output formats

Every input renders to the same set of outputs:

| Output | API family | Result |
| --- | --- | --- |
| PNG, JPEG, WebP, ICO | `render_*` | Encoded `bytes` |
| Raw RGBA | `render_*` with `format="raw"` | Pixel `bytes` |
| Retained RGBA | `Renderer.rasterize` | `RasterImage` for repeated encoding |
| SVG | `render_svg_*` | `str` |
| Layout only | `measure_*` | `MeasuredNode` |
| WebP, APNG, GIF animation | `render_animation`, `encode_frames` | Encoded `bytes`; see [Animation](animation.md) |

## Raster images

`format` selects the encoder; `"png"` is the default.

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

| Format | Encoder options |
| --- | --- |
| `"png"` | None |
| `"jpeg"` or `"jpg"` | `quality` from 0 through 100, default 75 |
| `"webp"` | Lossless unless `quality` is set; `lossless=True` cannot be combined with `quality` |
| `"ico"` | None |

`device_pixel_ratio` scales CSS lengths into output pixels. At `2.0`, a `10px` box
covers 20 output pixels. An explicit `width` and `height` set the canvas size in output
pixels, while an inferred dimension scales with the content.

`dithering="ordered-bayer"` dithers gradient fills before they are quantized to 8 bits,
which reduces banding in smooth gradients.

## Retained raster images { #retained-raster-images }

Use `Renderer.rasterize` when the finished pixels must be encoded more than once.
Layout and drawing happen once, and every `RasterImage.encode` call reads the retained
native bitmap:

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

The bitmap is immutable and outlives the renderer. Its one-call `render` counterpart
is simpler when only one encoded result is needed.

## Raw RGBA

`format="raw"` skips encoding and returns row-major RGBA bytes with straight alpha,
4 bytes per pixel:

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

Raw output pairs with `encode_frames` for animations assembled in Python, and with image
libraries that accept RGBA buffers.

## SVG

`render_svg_node`, `render_svg_html`, `render_svg_template`, and `render_svg_compiled`
return an SVG document string:

```python
from takumi_py import Renderer

svg = Renderer().render_svg_html(
    '<div class="card">Hello</div>',
    stylesheets=[".card { width: 1200px; height: 630px; color: black; }"],
    width=1200,
    height=630,
)
```

SVG output takes the viewport, `font_size`, `time_ms`, images, keyframes, font families,
and `lang`. Encoder settings, `device_pixel_ratio`, dithering, and debug borders apply
only to raster output.

## Measurement

`measure_node`, `measure_html`, and `measure_compiled` run layout without drawing and
return a `MeasuredNode` tree:

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

Each `MeasuredNode` carries its `width`, `height`, a 2D affine `transform`, its
`children`, and the `MeasuredTextRun` values for the text it lays out. Measurement
reports exact layout sizes; raster output snaps boxes to whole pixels as it paints.

See the runnable
[`examples/render_options_measure.py`](https://github.com/BalconyJH/takumi-py/blob/main/examples/render_options_measure.py)
example.
