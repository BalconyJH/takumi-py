# HTML and CSS

Takumi's Rust parser turns HTML into the same node tree that `render_node` accepts.
The binding has no browser and no Python-side HTML parser.

## Render HTML

```python
from takumi_py import Renderer

png = Renderer().render_html(
    '<div class="card"><h1>Hello</h1></div>',
    stylesheets=[
        """
        .card {
          width: 1200px;
          height: 630px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          background: #111827;
        }
        """
    ],
    width=1200,
    height=630,
)
```

`measure_html` and `render_svg_html` accept the same HTML and stylesheet inputs.

## Document structure

A source that starts with a doctype or an `<html>` element parses as a document, with
`<html>`, `<head>`, and `<body>` as a browser builds them. Anything else parses as a
fragment. A fragment with several top-level elements is wrapped in a container that
fills the viewport.

The parser maps `style`, `class`, `id`, `dir`, `lang`, and Tailwind attributes onto the
node tree. `<style>` elements are removed from that tree, and their CSS is returned
separately in document order. Other elements that do not render are dropped, and an
`<img>` without a `src` renders as an empty box sized by its `width` and `height`.

## Stylesheets

Inline `style` attributes are part of the HTML. CSS from eligible `<style>` elements is
extracted and applied automatically. The `stylesheets=[...]` argument remains available
for author CSS supplied by the application; it is applied before the document's
embedded styles so equal-specificity HTML rules come later in cascade order.

A `<style>` block participates when its `type` is absent, empty, or case-insensitively
`text/css`. Non-empty `media` becomes an enclosing `@media` rule. `<link>` elements,
scripts, linked stylesheets, and `<base>` URL resolution are not supported; URL strings
remain exactly as authored.

HTML and node entry points compile `stylesheets` differently:

| Entry points | Compilation | Unsupported declaration |
| --- | --- | --- |
| `render_html`, `measure_html`, `render_svg_html`, `render_template`, `render_svg_template` | Error-tolerant, like a browser | Skipped |
| `render_node`, `measure_node`, `render_svg_node`, `render_animation`, `render_sequence_at_time` | Strict | Raises `StyleSheetError` |

For the compiled APIs, choose explicitly: `compile_stylesheet` is strict and
`compile_stylesheet_lossy` is error-tolerant.

```python
from takumi_py import Renderer, StyleSheetError

renderer = Renderer()
tolerant = renderer.compile_stylesheet_lossy("a { display: weird; } b { color: red; }")

try:
    renderer.compile_stylesheet("a { display: weird; }")
except StyleSheetError as error:
    print(error)
```

## Parser options

`HtmlOptions` controls the parser:

```python
from takumi_py import HtmlOptions, Renderer

png = Renderer().render_html(
    '<div class="w-[1200px] h-[630px]"></div>',
    html_options=HtmlOptions(
        presets="none",
        tailwind_property="class",
        max_depth=64,
    ),
    width=None,
    height=None,
)
```

| Option | Default | Effect |
| --- | --- | --- |
| `presets` | `"chromium"` | `"chromium"` applies Chromium's default element styles; `"none"` applies none |
| `tailwind_property` | `None` | Attribute that carries Tailwind classes; `None` reads the `tw` attribute |
| `max_depth` | `None` | Maximum element nesting; `None` uses Takumi's limit of 512 |

The effective HTML nesting limit is therefore always 512 or lower. Passing a
`max_depth` greater than 512 raises `ValueError` before parsing. HTML nested deeper
than the effective limit raises `HtmlParseError`.

## Parse once, render many

`parse_html` parses without a renderer and returns a `ParsedHtml` bundle;
`Renderer.compile_html` returns the equivalent `CompiledHtml`. Pass the bundle's node
and stylesheets to the compiled APIs as described in
[Compile and reuse](rendering.md#compile-and-reuse):

```python
from takumi_py import Renderer, parse_html

parsed = parse_html("<style>article { color: red; }</style><article>Hello</article>")
png = Renderer().render_compiled(
    parsed.node,
    stylesheets=parsed.stylesheets,
    width=320,
    height=160,
)
```

`ParsedHtml.stylesheets` and `CompiledHtml.stylesheets` contain the extracted CSS in
document order. When combining them with explicit author CSS, pass the explicit sheets
first and the extracted sheets afterward.

## Discover external resources

The renderer never fetches anything. `CompiledNode.resource_urls()` lists image-source
identifiers from image nodes, `CompiledStyleSheet.resource_urls()` lists identifiers
from CSS, and `CompiledDocument.resource_urls()` returns their deduplicated union.
Discovery is not limited to HTTP(S): every identifier it finds is included, including
custom schemes such as `memory://`:

```python
from takumi_py import Document, compile_document

compiled = compile_document(
    Document.from_node({"type": "image", "src": "https://example.com/logo.png"})
)

print(compiled.resource_urls())
print(compiled.missing_resources())
```

`missing_resources()` excludes references already supplied by the document and
self-contained data URLs or inline SVG. Raw byte-backed image sources have no string
identifier to discover; identifier sources retain their scheme. Pass application-read
bytes back as `ImageResource` values, as described in
[Fonts and images](resources.md#discover-image-references). Treat the result as a
conservative image-reference diagnostic rather than a complete post-cascade resource
closure.

For the resources a styled document actually reaches, prefer
`Renderer.needs(document, *, layout=None, scale=1.0)`. It accounts for CSS matching,
custom properties, media queries, hidden nodes, generated content, and `@font-face`
files. For raster output, pass the raster operation's scale so resolution queries and
viewport rounding match; measurement and SVG use scale one:

```python
from takumi_py import Document, LayoutOptions, Renderer, compile_document

compiled = compile_document(
    Document.from_html(
        """
        <style>
          @font-face { font-family: Article; src: url(article.woff2); }
          .card { font-family: Article; background: url(card.png); }
        </style>
        <div class="card">Hello</div>
        """
    )
)
needs = Renderer().needs(
    compiled,
    layout=LayoutOptions(width=1200, height=630),
    scale=2.0,
)
print(needs.images)
print(needs.font_files)
```

The renderer still performs no I/O. Load reported font files with
`load_font_file()`, mark failed downloads through
`LayoutOptions.failed_font_files`, and query `needs()` again after either changes.
See [Upgrade to Takumi 2.20](../migration/takumi-2.20.md#resource-discovery).

See the runnable
[`examples/render_html.py`](https://github.com/BalconyJH/takumi-py/blob/main/examples/render_html.py)
example.
