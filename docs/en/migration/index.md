---
icon: lucide/route
---

# Migration

Migration guides describe behavioral changes and required code changes between Takumi
core versions. They do not duplicate the commit-by-commit record in the changelog.

<div class="grid cards" markdown>

-   :material-numeric-2-box:{ .lg .middle } **Takumi v2**

    Resource ownership, HTML parsing, font descriptors, language behavior, and output
    changes.

    [:octicons-arrow-right-24: Open migration guide](takumi-v2.md)

-   :material-update:{ .lg .middle } **Takumi 2.17**

    Font subsets by `unicode_range`, deprecated `subset_of` and Floyd–Steinberg
    dithering, animation frame-rate limits, and Chrome-aligned rendering.

    [:octicons-arrow-right-24: Open migration guide](takumi-2.17.md)

</div>

!!! tip "Read both migration guidance and release history"

    During the testing stage, also review the
    [changelog](https://github.com/BalconyJH/takumi-py/blob/main/CHANGELOG.md)
    entries between your current and target versions.
