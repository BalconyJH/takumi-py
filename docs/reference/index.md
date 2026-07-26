---
icon: lucide/braces
---

# Reference

Reference pages define exact support and API contracts. For decision-oriented
explanations and complete examples, start with the [guides](../guides/index.md).

<div class="grid cards" markdown>

-   :material-check-decagram:{ .lg .middle } **Support matrix**

    Runtime versions, published wheels, formats, resource ownership, and exclusions.

    [:octicons-arrow-right-24: Support matrix](support.md)

-   :material-alert-circle-outline:{ .lg .middle } **Exceptions**

    Public exception hierarchy and the narrowest boundary callers should catch.

    [:octicons-arrow-right-24: Exceptions](exceptions.md)

-   :material-code-braces:{ .lg .middle } **Renderer API**

    Generated signatures for compilation, measurement, static output, SVG, and
    animation.

    [:octicons-arrow-right-24: Renderer](api/renderer.md)

-   :material-shape-outline:{ .lg .middle } **Supporting types**

    Render options, resources, nodes, results, and template entry points.

    [:octicons-arrow-right-24: Options](api/options.md) ·
    [:octicons-arrow-right-24: Types](api/types.md) ·
    [:octicons-arrow-right-24: HTML](api/html.md) ·
    [:octicons-arrow-right-24: Templates](api/templates.md)

</div>

!!! note "Import from the public package"

    `_core` is the native extension implementation module. Application code should
    import from `takumi_py` and must not treat `_core` as a compatibility boundary.
