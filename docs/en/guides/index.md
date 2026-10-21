---
icon: lucide/book-open
---

# Guides

Guides are organized around rendering tasks rather than Python module boundaries.

<div class="grid cards" markdown>

-   :material-layers-triple:{ .lg .middle } **Rendering model**

    Inputs, node trees, compilation, render options, viewport sizing, and parameter
    contracts.

    [:octicons-arrow-right-24: Open guide](rendering.md)

-   :material-language-html5:{ .lg .middle } **HTML and CSS**

    Parsing, document stylesheets, strict and error-tolerant CSS, parser options, and
    resource discovery.

    [:octicons-arrow-right-24: Open guide](html.md)

-   :material-image-multiple:{ .lg .middle } **Output formats**

    Raster encoders, raw RGBA, device pixel ratio, SVG, and layout measurement.

    [:octicons-arrow-right-24: Open guide](output.md)

-   :material-folder-image:{ .lg .middle } **Fonts and images**

    Resource ownership, font subsets, language metadata, and cache budgets.

    [:octicons-arrow-right-24: Open guide](resources.md)

-   :simple-jinja:{ .lg .middle } **Jinja templates**

    Template directories, render context, custom filters, and escaping boundaries.

    [:octicons-arrow-right-24: Open guide](templates.md)

-   :material-animation-play:{ .lg .middle } **Animation**

    Timeline sampling, scene sequences, raw frames, and animation encoders.

    [:octicons-arrow-right-24: Open guide](animation.md)

</div>

!!! info "Guides explain decisions; reference pages define signatures"

    Complete parameter signatures are generated from source in the
    [API reference](../reference/index.md). Guides focus on choosing an API and
    preserving its invariants so that parameter lists have a single source of truth.

Each guide links a runnable script from the
[`examples/`](https://github.com/BalconyJH/takumi-py/tree/main/examples) directory,
which the test suite executes.
