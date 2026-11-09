# Migrate to owned static images

The next-major document API separates three operations that used to be hidden
inside one byte-returning render call:

1. Compile a node, HTML document, or rendered Jinja template.
2. Lay out and draw a retained `RasterImage`.
3. Encode those pixels as PNG, JPEG, WebP, ICO, or raw RGBA bytes.

`Renderer.render(document, ...)` remains the compact convenience for callers that
need one encoded result. The new path matters when the same pixels must be written in
several formats or kept after the source renderer is released.

## Before and after { #before-and-after }

| Need | Previous single-call shape | Next-major static shape |
| --- | --- | --- |
| One encoded file | `renderer.render(document, output=...)` | unchanged |
| PNG and WebP from one layout | Two independent render calls | `image = renderer.rasterize(...)`; encode each format |
| Raw RGBA with known dimensions | `render(..., output=RasterOptions(format="raw"))` plus external size bookkeeping | `image.tobytes()`, `image.size`, and `image.stride` |
| Reuse an image in another document | Decode encoded image bytes | `image.to_raw_source()` or `image.to_fragment()` |
| Build from a Jinja template | Render directly to HTML or encoded bytes | `TemplateRenderer.document(...)`, then compile and choose outputs |

The previous APIs remain available during the next-major preview.

## Render once, encode repeatedly { #render-once }

`Renderer.rasterize` performs layout, decoding, and drawing once. The returned
`RasterImage` owns the native bitmap; every `encode` call reads that same bitmap.

```python
from takumi_py import Document, LayoutOptions, Renderer, compile_document

document = Document.from_node(
    {
        "type": "container",
        "style": {
            "width": "1200px",
            "height": "630px",
            "backgroundColor": "#0f172a",
        },
    }
)
compiled = compile_document(document)

image = Renderer().rasterize(
    compiled,
    layout=LayoutOptions(width=1200, height=630),
    scale=2,
)

png = image.encode("png")
webp = image.encode("webp", quality=90)
raw_rgba = image.tobytes()

assert image.size == (2400, 1260)
assert len(raw_rgba) == image.nbytes == image.stride * image.height
```

Do not call `Renderer.render` once per format when the pixels should be identical.
Those calls intentionally perform independent layout and rasterization. Keep a
`RasterImage` when the drawn pixels, not just the compiled source, are the reuse
boundary.

## Convert a template into a document { #template-document }

`TemplateRenderer.document(...)` renders Jinja once, then snapshots the resulting
HTML, resources, stylesheets, and parser options as a `Document`. It does not retain
the Jinja environment or choose an output format.

```python
from takumi_py import (
    Document,
    ImageResource,
    LayoutOptions,
    Renderer,
    TemplateRenderer,
    compile_document,
)

cover = b"""
<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160">
  <rect width="160" height="160" fill="#38bdf8"/>
</svg>
"""

template = TemplateRenderer("templates")
document: Document = template.document(
    "static_card.html.jinja",
    {"title": "Static card", "subtitle": "Reusable output"},
    resources=[ImageResource("https://assets.example/cover.svg", cover, cache="none")],
    stylesheets=[
        ".card { width: 640px; height: 320px; }",
    ],
)

compiled = compile_document(document)
assert compiled.missing_resources() == ()

image = Renderer().rasterize(
    compiled,
    layout=LayoutOptions(width=640, height=320),
)
```

The standalone `render_template_to_document` helper provides the same adapter without
constructing a `TemplateRenderer`.

## Resource discovery { #resource-discovery }

`CompiledDocument.resource_urls()` reports image references found in the compiled node
and stylesheet. `missing_resources()` removes references already supplied by the
document and ignores self-contained data URLs and inline SVG markup. Neither method
performs network access.

This is a conservative image-reference diagnostic, not a complete compiled-resource
closure, and it does not block rendering. Fetch what it reports in application code,
then attach the bytes with `CompiledDocument.with_resources()` or pass them as
`ImageResource` values when constructing the source document. `with_resources()`
reuses the compiled node and stylesheet instead of parsing again.

`Renderer.needs(document, *, layout=None, scale=1.0)` reports the post-cascade set.
When preparing raster output, pass the same scale used by `render()`'s
`RasterOptions` or `rasterize()`. The query enlarges the viewport and sets the device
pixel ratio in the same way as rasterization, including resolution media queries and
rounded viewport dimensions. Measurement and SVG layout use scale one, so use the
default `scale=1.0` when discovering for `measure()` or `render_svg()`.

Encoded image bytes are copied once into the compiled document's opaque native
snapshot. Document renders borrow that snapshot, so they do not upload the same bytes
from Python on every call. This is not zero-copy: document construction and validation
still copy. Decoded images also remain in each renderer's cache and are not part of the
document. Keep other inputs such as fonts explicit in the renderer.

## Composition and pixel ownership { #composition-and-ownership }

`RasterImage` stores tightly packed, row-major RGBA8 with straight alpha. `data` and
`tobytes()` copy the native buffer into Python bytes. `to_raw_source()` copies it into
a `RawRgbaImage` mapping, and `to_fragment()` wraps that mapping in an image
`Fragment`. The latter can participate in document composition like any other
fragment and carries its own resource snapshot.

`RasterImage.from_raw(data, width=..., height=...)` accepts the same pixel layout for
an image produced outside Takumi. The buffer length must be exactly
`width * height * 4`.

## Vector resources in SVG output { #vector-resource-output }

`Renderer.render_svg()` may flatten vector `ImageResource` values, including
`MathSvg.to_image_resource()`, into geometry under the host SVG. For a vector formula,
this commonly produces transformed `<path>` elements without an embedded `<image>` or
`data:image/svg+xml` URL. Raster image sources may still require an `<image>` fallback.
The document keeps the original resource bytes and identifier; the rendered SVG may
use a different internal representation. Validate paths, geometry, and visible output
rather than assuming one particular image serialization.

## Layout and threading boundaries { #layout-and-threading }

The retained object is a finished bitmap. Takumi's layout scene is not part of the
Python API. It contains single-thread-affine caches and cannot be treated as a
general-purpose `Send`/`Sync` scene that Python calls may move between worker threads.
This is why the public static surface exposes raster output reuse rather than an
opaque scene object.

`Renderer.measure` and `Renderer.render_svg` continue to lay out the compiled document
independently. Encoding an existing `RasterImage` does not perform either operation.

## Migration checklist { #migration-checklist }

- [ ] Keep `Renderer.render` for one-shot encoded bytes.
- [ ] Switch multi-format or retained static output to `Renderer.rasterize` and
  `RasterImage.encode`.
- [ ] Render Jinja templates into `Document` objects with
  `TemplateRenderer.document` or `render_template_to_document`.
- [ ] Inspect `CompiledDocument.resource_urls()` and `missing_resources()` before
  assuming image inputs are complete.
- [ ] Query `Renderer.needs()` with the same layout and raster scale as the planned
  output; use scale one for measurement and SVG.
- [ ] Use `tobytes()` or `to_raw_source()` when pixels must cross the native boundary.
- [ ] Keep animation timing and encoding in the existing animation APIs.
