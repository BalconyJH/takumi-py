# Jinja templates

`TemplateRenderer` owns a filesystem-backed Jinja environment and sends rendered HTML
to the Takumi parser.

```python
from takumi_py import Renderer, TemplateRenderer


def uppercase(value: str) -> str:
    return value.upper()


configured_renderer = Renderer()
renderer = TemplateRenderer(
    "templates",
    filters={"uppercase": uppercase},
    renderer=configured_renderer,
)

png = renderer.render(
    "card.html.jinja",
    {"title": "takumi-py"},
    stylesheets=[
        ".card { width: 1200px; height: 630px; color: white; background: #111827; }",
    ],
    width=1200,
    height=630,
)
```

The template can use `{{ title | uppercase }}` directly. The
`render_template_to_html` helper accepts the same `filters` mapping when the caller
needs an HTML string rather than image output.

## Build a static document { #build-a-static-document }

Use `TemplateRenderer.document` when the rendered template needs the document APIs.
Template loading and rendering finish before the returned `Document` is created; the
document keeps the HTML and explicit inputs but does not retain the Jinja environment.

```python
from takumi_py import (
    ImageResource,
    LayoutOptions,
    Renderer,
    TemplateRenderer,
    compile_document,
)

logo = b"""
<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128">
  <circle cx="64" cy="64" r="56" fill="#38bdf8"/>
</svg>
"""

template = TemplateRenderer("templates")
document = template.document(
    "static_card.html.jinja",
    {"title": "Static card", "subtitle": "Reusable output"},
    resources=[ImageResource("https://assets.example/cover.svg", logo, cache="none")],
    stylesheets=[".card { width: 640px; height: 320px; }"],
)

compiled = compile_document(document)
assert compiled.missing_resources() == ()

image = Renderer().rasterize(
    compiled,
    layout=LayoutOptions(width=640, height=320),
)
png = image.encode("png")
```

`compiled.resource_urls()` reports image references collected from the node and
stylesheet. `compiled.missing_resources()` removes resources already owned by the
document; neither method downloads anything. See the
[resource guide](resources.md#discover-image-references) for the discovery scope.

## Inject a complete Jinja environment

The filesystem-backed environment is a convenience default, not a restricted Jinja
surface. Inject an existing `jinja2.Environment` when the application needs another
loader, globals, tests, extensions, an undefined-value policy, a bytecode cache, or
other native Jinja configuration:

```python
from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from takumi_py import TemplateRenderer


environment = Environment(
    loader=PackageLoader("my_app", "templates"),
    autoescape=select_autoescape(("html", "xml", "jinja")),
    undefined=StrictUndefined,
)
environment.globals["product_name"] = "My App"
environment.tests["featured"] = lambda item: item.featured

renderer = TemplateRenderer(
    environment=environment,
    filters={"currency": lambda value: f"${value:,.2f}"},
)
```

`renderer.environment` is the exact injected instance. `filters` are updated on that
instance before the first template is loaded. `render_template_to_html` also accepts
`environment=...`. In both APIs, `template_dir` and `environment` are mutually
exclusive so that one template-loading source cannot silently shadow another.

## Inject a configured renderer

Pass an existing `Renderer` to `TemplateRenderer` when templates must share registered
fonts or other renderer-owned state. Configure the renderer first, then inject that
same instance:

```python
from pathlib import Path

from takumi_py import FontResource, Renderer, TemplateRenderer


def uppercase(value: str) -> str:
    return value.upper()


configured_renderer = Renderer(load_default_fonts=False)
families = configured_renderer.register_font(
    FontResource(
        Path("Inter-Regular.woff2").read_bytes(),
        name="Inter",
        generic_family="sans-serif",
    )
)
renderer = TemplateRenderer(
    "templates",
    filters={"uppercase": uppercase},
    renderer=configured_renderer,
)
png = renderer.render(
    "card.html.jinja",
    {"title": "takumi-py"},
    stylesheets=[".card { width: 1200px; height: 630px; }"],
    font_families=families,
    width=1200,
    height=630,
)
```

## Responsibility boundaries

```mermaid
flowchart LR
    T["Template + context"] --> J["Jinja environment"]
    J --> H["HTML"]
    H --> P["Takumi parser"]
    C["Stylesheets"] --> P
    R["Fonts + images"] --> E["Render"]
    P --> E
```

- Configure filters, globals, tests, and extensions before the first render. Jinja does
  not guarantee predictable behavior when an environment is mutated after a template
  has already been loaded.
- Templates generate HTML. Supply images through render inputs. Register custom fonts
  on an injected renderer as shown above and follow the [resource guide](resources.md).
- Explicit author CSS belongs in `stylesheets`. Eligible `<style>` elements in the
  rendered HTML are extracted automatically.
- Jinja autoescape is enabled by default for HTML, XML, and Jinja files. A caller-owned
  environment retains its own autoescape policy.

!!! caution "Custom filters execute application code"

    Treat filter functions and template directories as trusted application inputs.
    Autoescape protects interpolated markup; it does not sandbox Python filter code.

See the runnable
[`examples/render_template.py`](https://github.com/BalconyJH/takumi-py/blob/main/examples/render_template.py)
example and its
[`card.html.jinja`](https://github.com/BalconyJH/takumi-py/blob/main/examples/templates/card.html.jinja)
template. The
[`examples/render_static.py`](https://github.com/BalconyJH/takumi-py/blob/main/examples/render_static.py)
example uses `TemplateRenderer.document`, owned image resources, and a retained raster.
