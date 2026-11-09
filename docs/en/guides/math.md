# Mathematical formulas

!!! info "Next-major preview"

    `takumi_py.math` is a next-major preview in this checkout. Its additive APIs do
    not change the package version or the existing rendering entry points.

`MathTypesetter` converts an explicitly supplied TeX expression into a self-contained
SVG value. `MathSvg` carries the SVG bytes, CSS-pixel dimensions, and signed baseline
depth. It can produce an image resource, HTML, a node, or a `Fragment` that owns both
the node and its image resource.

Formula conversion is separate from HTML and Markdown parsing. The package does not
scan a document for delimiters such as `$...$`, `\(...\)`, or `\[...\]`; select the
expressions in application code and pass the TeX without the surrounding Markdown
delimiter.

## Install { #install }

From a current source checkout, math conversion needs the optional runtime extra:

```bash
uv sync --extra math
```

The current PyPI release does not publish this preview extra. Locally built preview
wheels also accept the `math` extra; do not use `takumi-py[math]` with PyPI until that
extra appears in a published release. The extra installs `mini-racer==0.14.1`.

The optional runtime has a narrower compatibility floor than the core extension.
For Linux glibc targets, the MiniRacer wheel used by the math extra requires glibc
2.27, while the core wheel baseline is glibc 2.17. The math extra also exposes
musllinux 1.2, macOS Intel 10.9 and arm64 11, and Windows x64 and arm64 targets.
These are runtime wheel targets, not completed execution claims; CI still needs to
verify each platform.

The pinned MathJax `4.1.3` runtime and local SVG font data are bundled with every core
wheel, including installations that do not use the math extra. Those assets are about
11.5 MB uncompressed; their contribution to the compressed wheel is smaller. The extra
installs the runtime; it does not download MathJax or fonts on first use.

## Runtime and process model { #runtime-model }

Importing `takumi_py` or `takumi_py.math` does not start the formula engine. Construct
`MathTypesetter` explicitly after selecting the extra. Construction validates the
bundled MathJax assets. The first uncached `typeset` call starts a supervised Python
worker, which imports and version-checks MiniRacer.

The worker executes the pinned local MathJax bundle with an embedded V8 runtime. It
does not use Node.js, a browser, a remote rendering service, or network access. If a
conversion reaches `MathLimits.timeout_ms`, the parent terminates the worker and raises
a math error. The call can finish after that deadline while the parent performs the
bounded process-termination grace, so the deadline is not an absolute millisecond
return guarantee. A later cache miss starts a fresh worker, so the reusable runtime
does not retain the runaway job.

The deadline also covers process creation. A stalled operating-system launch runs
in one background helper per typesetter, so it cannot block `typeset()` or `close()`
indefinitely. A process that appears after cancellation is terminated; retries do
not create additional launch helpers while that launch is still pending.

`typeset` is synchronous and blocks the calling thread while a cache miss is being
converted. Async applications can construct a typesetter safely, but should run
conversion calls in an executor when blocking their event loop is undesirable.
`close()` releases the typesetter and is idempotent. Use the context manager when the
typesetter has a bounded lifetime. A returned `MathSvg` owns only immutable bytes and
geometry, so it remains valid after the typesetter closes.

## Convert and compose { #convert-and-compose }

`MathOptions.display=False` produces inline TeX. Setting `display=True` applies display
style and makes `MathSvg.to_node()` and `to_fragment()` return a centered block
container. `font_size_px` uses CSS pixels, `ex_ratio` sets the input environment's
x-height ratio, and `color` is an optional named CSS color or hexadecimal color.

Dimensions and baseline depth come from MathJax's layout box and scale linearly
with `font_size_px`, including large sizes. TeX lengths explicitly written in `px`
retain their absolute units. Derived geometry outside the finite float32 range
raises `MathLimitError`; a font size too small to represent the minimum box raises
`MathValidationError` before conversion.

The preferred document path is `to_fragment()`. It returns a `Fragment` whose node and
`ResourceSet` are inserted by `Document.from_node`; identical formula resources are
deduplicated automatically.

```python
from pathlib import Path

from takumi_py import (
    Document,
    LayoutOptions,
    RasterOptions,
    Renderer,
    compile_document,
)
from takumi_py.math import MathOptions, MathTypesetter

with MathTypesetter() as typesetter:
    inline = typesetter.typeset(
        r"E = mc^2",
        options=MathOptions(font_size_px=30, color="#000000"),
    )
    display = typesetter.typeset(
        r"\frac{x^2 + y^2}{a + b}",
        options=MathOptions(display=True, font_size_px=40, color="#000000"),
    )

    document = Document.from_node(
        {
            "type": "container",
            "style": {
                "width": "920px",
                "padding": "64px",
                "backgroundColor": "#ffffff",
                "color": "#000000",
                "fontSize": "30px",
                "lineHeight": "1.5",
            },
            "children": [
                {"type": "text", "text": "Energy and mass: "},
                inline.to_fragment(),
                {"type": "text", "text": " are related."},
                display.to_fragment(),
            ],
        }
    )

compiled = compile_document(document)
layout = LayoutOptions(width=920, height=None)
renderer = Renderer()

png = renderer.render(compiled, layout=layout, output=RasterOptions(scale=2))
measured = renderer.measure(compiled, layout=layout)
svg = renderer.render_svg(compiled, layout=layout)

Path("math.png").write_bytes(png)
Path("math.svg").write_text(svg, encoding="utf-8")
```

For layout, the inline formula occupies a single inline box with a CSS `verticalAlign`
derived from `MathSvg.depth_px`. The display formula changes TeX style and wraps that
box in a centered block. The same `CompiledDocument` can then be measured, rasterized
at one or more scales, or rendered to SVG without rerunning the math engine.

With `color=None`, generated fills and strokes use `currentColor`. Takumi resolves that
value through the host element's color when it renders the document. Vector SVG
resources are flattened into host path geometry when possible; raster image sources
may still need an `<image>` fallback. Output serialization is therefore an
implementation detail and should not be assumed to contain one embedded `<image>` or
an SVG data URI. Explicit `MathOptions.color` is the deterministic choice when a
formula must remain black, match a brand palette, or preserve an exact cache key across
hosts.

## Explicit HTML resources { #explicit-html-resources }

`MathSvg.to_html()` returns an escaped `<img>` with explicit width, height, and inline
baseline alignment. `Document.from_html` does not discover that image resource, so pass
`MathSvg.to_image_resource()` explicitly:

```python
from takumi_py import (
    Document,
    LayoutOptions,
    Renderer,
    ResourceSet,
    compile_document,
)
from takumi_py.math import MathOptions, MathTypesetter

with MathTypesetter() as typesetter:
    formula = typesetter.typeset(
        r"\int_0^1 x^2\,dx",
        options=MathOptions(font_size_px=32, color="#000000"),
    )

html = '<p class="formula">Integral: ' + formula.to_html(alt="integral") + "</p>"
document = Document.from_html(
    html,
    resources=ResourceSet([formula.to_image_resource()]),
    stylesheets=[
        ".formula { width: 900px; padding: 48px; color: black; background: white; }"
    ],
)
compiled = compile_document(document)

svg = Renderer().render_svg(
    compiled,
    layout=LayoutOptions(width=900, height=None),
)
```

The same two pieces work with the existing HTML API by passing the resource in its
`images` argument to `Renderer.render_html`. The document path is preferable when the
resource must travel with the source through compilation and later outputs.

Supplying `MathSvg.to_image_resource()` is still required because the HTML adapter
must associate the `<img>` with the stored SVG bytes. `Renderer.render_svg()` may then
flatten that vector resource into host `<path>` and transform elements. Do not inspect
the result for a guaranteed `data:image/svg+xml` URL or exactly one embedded `<image>`;
flattening is the preferred vector path, while raster resources may use `<image>`.

The formula's resource ID is a SHA-256 digest of its SVG bytes. Reusing a `MathSvg`
fragment in several document positions therefore contributes one identical
`ImageResource` to the compiled document. Resources with conflicting bytes for the
same source raise `ResourceError` when the document snapshots its resources.

## Batch, limits, and lifecycle { #batch-limits-and-lifecycle }

`typeset_many` preserves input order, deduplicates identical semantic requests, and
applies one `MathOptions` value to the batch. It is all-or-nothing: a failed expression
raises `MathBatchError` and does not return a partially successful tuple. Exceeding
`MathLimits.max_batch_size` raises `MathLimitError` before conversion starts.

`MathLimits` controls execution and cache budgets. Its defaults are a 5,000 ms deadline,
a 256 MiB V8 heap limit inside the worker, a 65,536-byte input limit, a 1,000,000-byte
SVG limit, a 128-level source nesting limit, a 1,024-expression batch limit,
128 cache entries, and 16 MiB of cached
UTF-8 TeX keys plus SVG bytes combined. The heap limit does not cap the worker process's
total resident memory. Tighten these values when application inputs are less trusted
or smaller than the defaults. Timeout and heap budgets must also fit the platform's
timeout and native integer ranges; out-of-range values raise `ValueError` at construction.

`max_nesting_depth` can be lowered but cannot exceed 128. It checks nested TeX
groups, environments, and paired delimiters before starting the worker, ignoring
comments and escaped characters. Exceeding it raises `MathLimitError`. This is a
source budget, not a bound on macro expansion; expansion remains inside the
supervised worker's time and memory limits.

The typesetter uses an in-memory LRU cache by default. Pass `cache=False` to disable
it; it does not read or write a disk cache.

```python
from takumi_py.math import MathLimits, MathOptions, MathTypesetter

limits = MathLimits(
    timeout_ms=2_000,
    max_input_bytes=16_384,
    max_batch_size=64,
    cache_entries=32,
)

with MathTypesetter(limits=limits, extensions=("mhchem",)) as typesetter:
    formulas = typesetter.typeset_many(
        (r"E = mc^2", r"\ce{H2O}", r"E = mc^2"),
        options=MathOptions(font_size_px=24, color="#000000"),
    )

# Formula values remain immutable and usable after the worker is closed.
```

Extensions are selected on the typesetter, not in `MathOptions`. The initial supported
extension is `"mhchem"`; without `extensions=("mhchem",)`, chemistry commands are
unavailable. Each conversion starts from fresh TeX declarations, so a macro defined in
one expression does not persist into a later call.

## Syntax and support scope { #syntax-and-support }

The initial math path intentionally covers formulas, not general LaTeX documents.
The demonstrated subset includes base TeX, AMS math and align environments, matrices
and cases, resizable delimiters, named operators such as `\sin` and `\operatorname`,
text spaces, color, `\cancel`, `\bbox` borders, array rules, and opt-in mhchem chemistry.

It does not promise complete LaTeX packages, arbitrary macros with persistent state,
`\input`, file access, network retrieval, formula numbering or cross-references,
automatic line breaking, MathML, or Markdown formula detection. Put line-breaking and
pagination in the surrounding layout.

CJK text such as `\text{中文}` is currently unsupported. The pinned path-only output
policy rejects text nodes instead of silently depending on fonts that may not exist on
the host. General CJK body text still requires a font registered with the normal
Takumi font APIs.

The local integration has been proven on macOS arm64. The other targets listed above
are reserved for CI validation and are not described here as verified until those runs
pass.

## Errors and public API { #errors-and-api }

All math-specific failures derive from `MathError`, which also inherits `TakumiError`.
Runtime packaging failures use `MathRuntimeUnavailableError`; TeX syntax failures use
`MathSyntaxError`; untrusted or oversized input uses `MathValidationError`; budget
failures use `MathLimitError`; and worker or engine failures use `MathRuntimeError`.
`MathBatchError` identifies the failing batch index and retains the underlying cause.

The public module exports:

```python
from takumi_py.math import (
    MathBatchError,
    MathConverter,
    MathError,
    MathLimitError,
    MathLimits,
    MathOptions,
    MathRuntimeError,
    MathRuntimeUnavailableError,
    MathSvg,
    MathSyntaxError,
    MathTypesetter,
    MathValidationError,
)
```

`MathConverter` is a narrow protocol for application-provided converters. It defines
`typeset(tex, *, options=None) -> MathSvg` and does not own or launch the built-in
worker.

## Runnable example { #runnable-example }

[`examples/render_math.py`](https://github.com/BalconyJH/takumi-py/blob/main/examples/render_math.py)
composes an inline formula with body text and a display fraction, writes a PNG and SVG
under `examples/output`, and uses `MathSvg.to_fragment()` with the document pipeline.
