# Options and resources

These types group rendering, animation, HTML parsing, font, and image inputs.

Common validation contracts:

- `RenderOptions.lang`, when set, must be a valid BCP-47 language tag.
- `FontResource.weight`, when set, must be finite and within 1 through 1000.
- Each `FontResource.unicode_range` entry is an inclusive `(start, end)` pair with
  `0 <= start <= end <= 0x10FFFF`.
- `LayoutOptions.failed_font_files` is a per-operation sequence of `@font-face` URLs
  whose application-side download failed.
- `AnimationEncodeOptions.quality` accepts 0 through 100, and `webp_speed` accepts
  0 through 6.

Violations of these numeric or language-tag contracts raise `ValueError`.

::: takumi_py.options.RenderOptions

::: takumi_py.options.AnimationEncodeOptions

::: takumi_py.options.HtmlOptions

::: takumi_py.options.LayoutOptions

::: takumi_py.options.ImageResource

::: takumi_py.options.FontResource

## Structured keyframes

Structured keyframes can be passed to render methods or stored in
`RenderOptions.keyframes`. The mapping form uses animation names as keys.

On rendering entry points that accept a `keyframes` override, omitting it
inherits the applicable renderer, template, or `RenderOptions.keyframes` value.
Passing a keyframe input replaces that value, while `None` clears it.

::: takumi_py.options.Keyframe

::: takumi_py.options.KeyframesRule
