# Upgrade to Takumi 2.17

The next takumi-py release moves the native renderer from Takumi 2.5.4 to 2.17.1. The
Python API stays compatible, but a few inputs change meaning and Takumi's output moves
closer to Chrome's.

## Expect pixel changes

Takumi 2.6 through 2.17 port more of Chromium's layout and paint behavior: text and
inline layout, line heights, text decorations, filters and `backdrop-filter`,
backgrounds, borders, outlines, `box-shadow`, tables, and CSS paint order. An image
that was correct under 2.5 can shift by a few pixels or change where it previously
diverged from a browser.

Regenerate golden images after upgrading, and compare a suspicious difference with
Chrome before treating it as a binding regression. The upstream
[Takumi changelog](https://github.com/kane50613/takumi/blob/master/takumi/CHANGELOG.md)
lists every rendering change.

## Required changes

| Before | After | Why |
| --- | --- | --- |
| One `FontResource(name="Inter-latin", subset_of="Inter")` per subset | `FontResource(name="Inter", unicode_range=[...])` for every subset | `subset_of` now only sets the family name |
| `font_families=["Inter-latin", "Inter-cyrillic"]` | `font_families=["Inter"]` | Subsets no longer register under their own names |
| `dithering="floyd-steinberg"` | `dithering="ordered-bayer"` | Takumi removed error diffusion; the old name is an alias |
| `render_animation(..., fps=60, format="gif")` | `fps` of at most 50 for GIF, 90 for WebP and APNG | Higher rates now raise `ValueError` |

### Font subsets

Register each subset of a family under the family's own name, with the codepoint
ranges its `@font-face` declares. Takumi serves each codepoint from the subset whose
range covers it:

=== "Takumi 2.17"

    ```python
    from pathlib import Path

    from takumi_py import FontResource, Renderer

    renderer = Renderer()
    renderer.register_fonts(
        [
            FontResource(
                Path("Inter-Latin.woff2").read_bytes(),
                name="Inter",
                unicode_range=[(0x0000, 0x00FF)],
            ),
            FontResource(
                Path("Inter-Cyrillic.woff2").read_bytes(),
                name="Inter",
                unicode_range=[(0x0400, 0x045F)],
            ),
        ]
    )
    ```

=== "Takumi 2.5"

    ```python
    renderer.register_fonts(
        [
            FontResource(latin, name="Inter-latin", subset_of="Inter"),
            FontResource(cyrillic, name="Inter-cyrillic", subset_of="Inter"),
        ]
    )
    ```

`subset_of` still works, but it emits a `DeprecationWarning` and takes precedence
over `name`, so `register_font` returns the `subset_of` value. Without
`unicode_range`, a later font registered under the same name and descriptors shadows
the earlier one, as a later `@font-face` rule does in a browser.

## Behavior changes

- `<img>` without a `src` attribute parses as an empty box sized by its `width` and
  `height`, as Chrome draws it. It used to raise `HtmlParseError`.
- `compile_stylesheet` accepts CSS that Takumi 2.5 rejected, such as
  `text-decoration: none`. Values Takumi still cannot parse raise `StyleSheetError`
  as before.
- The renderer resource cache defaults to 64 MiB instead of 16 MiB. Images embedded
  as `data:` URIs now decode through it, once per renderer.
- `render_animation` streams frames into the encoder, so it holds one raw frame at a
  time. The encoded bytes are the same as before.

## New APIs

- `FontResource.unicode_range` limits the codepoints a font serves.
- `Renderer.unregister_font(name)` releases a family with all of its subsets.
- `Renderer.clear_fonts()` releases every registered font, leaving only the bundled
  fallback when the renderer loads it.

See [Fonts and images](../guides/resources.md#font-subsets) for usage.

## Upgrade checklist

- [ ] Replace `subset_of` with one family `name` plus `unicode_range` per subset.
- [ ] Drop per-subset family names from `font_families` and CSS `font-family`.
- [ ] Replace `dithering="floyd-steinberg"` with `"ordered-bayer"`.
- [ ] Keep `fps` within 50 for GIF and 90 for WebP and APNG.
- [ ] Run the test suite with `-W error::DeprecationWarning` to find deprecated calls.
- [ ] Regenerate and review golden images.
