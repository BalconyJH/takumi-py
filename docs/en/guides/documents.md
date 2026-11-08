# Documents and reusable outputs

!!! info "Next-major preview"

    `Document`, `CompiledDocument`, `Fragment`, `ResourceSet`, and the new
    `Renderer.render`, `Renderer.measure`, and `Renderer.render_svg` entry points are a
    next-major preview in this checkout. They are additive: the package metadata and
    version remain unchanged, and the existing `render_*`, `measure_*`, and
    `render_svg_*` APIs remain compatible.

The document API groups a rendered input with the resources it owns, then separates
compilation from output. It is useful when the same content is rendered as a raster
image, measured, and rendered as SVG, especially when image bytes must travel with the
document.

The APIs are implemented by the native Python package. They do not start a JavaScript
runtime, require Node.js, load an external sidecar, or fetch remote resources.

## Pipeline { #pipeline }

```mermaid
flowchart LR
    S["Node or HTML source"] --> D["Document snapshot"]
    D --> C["compile_document"]
    C --> N["Compiled node + stylesheet + resources"]
    N --> L1["Raster layout"]
    N --> L2["Measurement layout"]
    N --> L3["SVG layout"]
```

`Document.from_node` and `Document.from_html` create immutable source snapshots.
`compile_document` parses the node or HTML, compiles and merges stylesheets, and
returns a `CompiledDocument` containing:

| Component | Purpose |
| --- | --- |
| `node` | Native `CompiledNode` |
| `stylesheets` | Zero or one merged native stylesheet |
| `resources` | Immutable `ResourceSet` snapshot |

`Renderer.render`, `Renderer.measure`, and `Renderer.render_svg` accept either a
`Document` or a `CompiledDocument`. Passing a raw `Document` compiles it for that
call. Call `compile_document` first when compilation should be reused.

!!! warning "Compilation is reused; layout is not"

    A `CompiledDocument` owns parsed source and resources, not a precomputed layout,
    paint tree, or pixel buffer. Every output call lays out the compiled node again.
    Layout options, animation time, media resolution, and raster scale can therefore
    produce different geometry or pixels from the same compiled document.

## Create a document { #create-a-document }

### Node documents { #node-documents }

`Document.from_node` accepts a node mapping and snapshots it. Node documents compile
CSS strictly, so invalid stylesheet syntax raises `StyleSheetError`.

```python
from pathlib import Path

from takumi_py import (
    Document,
    Fragment,
    ImageResource,
    LayoutOptions,
    RasterOptions,
    Renderer,
    ResourceSet,
    compile_document,
)

logo = Fragment(
    {
        "type": "image",
        "src": "memory://logo",
        "width": 32,
        "height": 32,
    },
    ResourceSet(
        [
            ImageResource("memory://logo", Path("logo.svg").read_bytes()),
        ]
    ),
)

document = Document.from_node(
    {
        "type": "container",
        "className": "card",
        "children": [
            logo,
            {"type": "text", "text": "Reusable document"},
        ],
    },
    stylesheets=[
        ".card { padding: 24px; color: black; }",
    ],
)

compiled = compile_document(document)
renderer = Renderer()

png = renderer.render(
    compiled,
    layout=LayoutOptions(width=320, height=160),
    output=RasterOptions(scale=2),
)
```

The stylesheet strings are applied in order. Structured `keyframes` passed to either
document constructor are compiled after those stylesheets. A document snapshot keeps
defensive copies of mutable node, stylesheet, keyframe, and resource inputs.

### HTML documents { #html-documents }

`Document.from_html` keeps the HTML string plus explicitly supplied resources and
stylesheets. The native parser handles HTML structure and the configured style
presets; document-level CSS remains explicit. HTML documents use Takumi's lossy CSS
parser because browser-authored stylesheets commonly contain declarations the renderer
does not support.

```python
from pathlib import Path

from takumi_py import (
    Document,
    HtmlOptions,
    ImageResource,
    LayoutOptions,
    Renderer,
    compile_document,
)

document = Document.from_html(
    '<article class="story"><img src="memory://cover"><p>Read me</p></article>',
    resources=[
        ImageResource("memory://cover", Path("cover.webp").read_bytes()),
    ],
    stylesheets=[
        ".story { padding: 24px; }",
        "@media (min-width: 600px) { .story { padding: 48px; } }",
    ],
    html_options=HtmlOptions(presets="chromium"),
)

compiled = compile_document(document)
renderer = Renderer()

svg = renderer.render_svg(
    compiled,
    layout=LayoutOptions(width=640, height=360),
)
```

HTML parsing does not discover image bytes, Markdown, formulas, or external
stylesheets. Pass every image resource explicitly and include any document-level CSS
in `stylesheets`.

### Fragments and resources { #fragments-and-resources }

`Fragment` pairs a reusable node value with a `ResourceSet`. When a `Document` is
created, it walks the node tree, expands every fragment in place, snapshots the
expanded node, and appends the fragment resources to the document. The same fragment
can appear repeatedly without duplicating identical resources.

Fragments passed to `Document.from_node` must contain node mappings. A generic
`Fragment` can hold other values, but a `CompiledNode` fragment cannot be expanded
into a source document; use the compiled-node APIs for an already compiled tree.

`ResourceSet` preserves first-seen order and copies resource bytes. Exact duplicates
with the same `src`, bytes, and cache mode are collapsed. If one `src` maps to
different bytes or a different cache mode, construction raises `ResourceError`.

```python
from takumi_py import ImageResource, ResourceError, ResourceSet

try:
    resources = ResourceSet(
        [
            ImageResource("memory://logo", b"first image"),
            ImageResource("memory://logo", b"different image"),
        ]
    )
except ResourceError as error:
    print(error)
```

Resources attached to fragments and resources passed to `Document.from_node` share
the same namespace. A conflict anywhere in the assembled document is an error rather
than a last-one-wins choice.

## Compile once, lay out per output { #compile-once }

Compilation is deterministic with respect to the source and options captured by the
`Document`. The same `CompiledDocument` can be reused across renderers and outputs.

```python
from takumi_py import Document, LayoutOptions, RasterOptions, Renderer, compile_document

compiled = compile_document(
    Document.from_node(
        {
            "type": "container",
            "style": {"width": "160px", "height": "80px", "backgroundColor": "black"},
        }
    )
)

renderer = Renderer()
layout = LayoutOptions(width=240, height=120)

png = renderer.render(compiled, layout=layout, output=RasterOptions(format="png"))
raw = renderer.render(compiled, layout=layout, output=RasterOptions(format="raw"))
measured = renderer.measure(compiled, layout=layout)
svg = renderer.render_svg(compiled, layout=layout)
```

Each call above lays out the content independently. This is intentional: measurement
always uses a device pixel ratio of one, SVG uses CSS-pixel dimensions, and raster
output may use another scale. Image resources are available through the document, but
decoded images remain renderer-local and follow each renderer's resource-cache policy.

## Layout in CSS pixels { #layout-in-css-pixels }

`LayoutOptions` describes the document viewport in CSS pixels:

| Field | Default | Meaning |
| --- | --- | --- |
| `width` | `1200` | Canvas width in CSS pixels, or `None` to infer it |
| `height` | `None` | Canvas height in CSS pixels, or `None` to infer it |
| `font_size` | `16.0` | Root font size used for `rem` and fallback metrics |
| `time_ms` | `0` | Animation sampling time |
| `font_families` | `None` | Preferred fallback family order |
| `lang` | `None` | BCP-47 language used for shaping and line breaking |

Explicit dimensions must be positive 32-bit integers. `font_size` must be a finite,
positive native float. `time_ms` must be a non-negative signed 64-bit integer.

The same requested layout dimensions are used by `render`, `measure`, and `render_svg`.
Viewport media queries such as `width`, `height`, `orientation`, and `aspect-ratio`
use the effective CSS dimensions, including the raster rounding described below.
A raster call additionally uses `RasterOptions.scale` as its device
pixel ratio, so `resolution` media queries can differ between raster output and
measurement or SVG even when `LayoutOptions` is unchanged.

## Raster output and scale { #raster-output-and-scale }

`RasterOptions` controls raster encoding. It has no effect on `measure` or
`render_svg`.

| Field | Default | Meaning |
| --- | --- | --- |
| `format` | `"png"` | `"png"`, `"jpeg"`, `"jpg"`, `"webp"`, `"ico"`, or `"raw"` |
| `scale` | `1.0` | Output pixels per CSS pixel |
| `quality` | `None` | Lossy encoder quality from 0 through 100 |
| `lossless` | `None` | Lossless WebP encoding |
| `dithering` | `"none"` | Dithering mode |
| `draw_debug_border` | `False` | Draw layout debug borders |

`scale` multiplies the explicit CSS dimensions to choose the output canvas. For
example, a 1200×630 CSS layout at scale 2 produces a 2400×1260 raster. An inferred
dimension remains inferred and is scaled from the resulting content size.

Fractional scales are allowed. Each explicit output dimension is rounded up with
`ceil(width * scale)` and `ceil(height * scale)`; avoid asserting exact fractional
pixel geometry from the output canvas alone. A scaled dimension that exceeds the
native 32-bit limit raises `ValueError`.

The native raster viewport is reconstructed from the rounded canvas and scale. For
example, width 41 at scale 1.5 becomes 62 output pixels and an effective CSS width
of approximately 41.333. This can change viewport units and media-query matches near
a breakpoint, including width, height, aspect ratio, and orientation. Use a scale
that maps explicit dimensions to whole output pixels when matching measurement or
SVG layout at a breakpoint matters.

```python
import struct

from takumi_py import Document, LayoutOptions, Renderer, RasterOptions, compile_document

compiled = compile_document(
    Document.from_node(
        {
            "type": "container",
            "style": {"width": "1200px", "height": "630px"},
        }
    )
)

png = Renderer().render(
    compiled,
    layout=LayoutOptions(width=1200, height=630),
    output=RasterOptions(format="png", scale=1.5),
)

assert struct.unpack(">II", png[16:24]) == (1800, 945)
```

## Legacy pixel sizing { #legacy-pixel-sizing }

The existing APIs remain supported with their current semantics. Their `width` and
`height` arguments are output pixel dimensions; `device_pixel_ratio` changes the CSS
viewport and media resolution inside that fixed raster. The document API reverses the
axis: `LayoutOptions` sets CSS pixels first, then `RasterOptions.scale` chooses output
pixels.

```python
from takumi_py import (
    Document,
    LayoutOptions,
    RasterOptions,
    Renderer,
    compile_document,
)

legacy = Renderer().render_html(
    "<div>Hello</div>",
    width=1200,
    height=630,
    device_pixel_ratio=2,
)

document = Document.from_node({"type": "text", "text": "Hello"})
new_api = Renderer().render(
    compile_document(document),
    layout=LayoutOptions(width=1200, height=630),
    output=RasterOptions(scale=2),
)
```

The legacy render above keeps a 1200×630 output canvas. The document render produces
a 2400×1260 canvas because 1200×630 are CSS dimensions. Keep using the legacy methods
when callers already express dimensions in output pixels; do not convert them
silently.

## Validation and failures { #validation-and-failures }

Document construction and compilation surface errors at the layer that can explain
them:

| Failure | Exception |
| --- | --- |
| Conflicting image data or cache mode for one `src` | `ResourceError` |
| Invalid node mapping during compilation | `NodeDecodeError` |
| Invalid HTML or parser depth | `HtmlParseError` |
| Invalid strict node CSS or structured keyframes | `StyleSheetError` |
| Invalid layout/output numeric option | `ValueError` |
| Rendering, image decoding, or encoding failure | Native render exception |

Passing a `CompiledDocument` avoids recompilation but does not bypass layout-time
validation or output encoding checks. A renderer still resolves images, selects
fonts, evaluates media queries at the requested viewport and scale, performs layout,
and encodes the requested output.

## API reference { #api-reference }

The complete generated signatures for the new document APIs are on the
[Renderer API page](../reference/api/renderer.md#document-apis). Existing signatures
remain available there as well.
