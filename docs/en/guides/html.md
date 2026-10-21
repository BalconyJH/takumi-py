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
node tree. `<style>` elements and other elements that do not render are dropped, and an
`<img>` without a `src` renders as an empty box sized by its `width` and `height`.

## Stylesheets

Inline `style` attributes are part of the HTML. Document-level CSS is always an explicit
input through `stylesheets=[...]`; `<style>` elements in the markup are ignored.

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

Nesting deeper than `max_depth` raises `HtmlParseError`.

## Parse once, render many

`parse_html` parses without a renderer and returns a `ParsedHtml` bundle;
`Renderer.compile_html` returns the equivalent `CompiledHtml`. Pass the bundle's node
and stylesheets to the compiled APIs as described in
[Compile and reuse](rendering.md#compile-and-reuse):

```python
from takumi_py import Renderer, parse_html

parsed = parse_html("<article>Hello</article>")
png = Renderer().render_compiled(
    parsed.node,
    stylesheets=parsed.stylesheets,
    width=320,
    height=160,
)
```

## Discover external resources

The renderer never fetches anything. `CompiledNode.resource_urls()` lists the HTTP(S)
image references in image nodes and styles, so the application can fetch them first:

```python
from takumi_py import Renderer

compiled = Renderer().compile_node(
    {"type": "image", "src": "https://example.com/logo.png"}
)

print(compiled.resource_urls())
```

It does not report sources the caller already supplied, such as `memory://` resources
or byte buffers. Pass fetched bytes back as `ImageResource` values, as described in
[Fonts and images](resources.md#images).

See the runnable
[`examples/render_html.py`](https://github.com/BalconyJH/takumi-py/blob/main/examples/render_html.py)
example.
