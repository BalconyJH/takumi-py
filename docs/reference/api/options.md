# Options and resources

These types group rendering, animation, HTML parsing, font, and image inputs.

Common validation contracts:

- `RenderOptions.lang`, when set, must be a valid BCP-47 language tag.
- `FontResource.weight`, when set, must be finite and within 1 through 1000.
- `AnimationEncodeOptions.quality` accepts 0 through 100, and `webp_speed` accepts
  0 through 6.

Violations of these numeric or language-tag contracts raise `ValueError`.

::: takumi_py.options.RenderOptions

::: takumi_py.options.AnimationEncodeOptions

::: takumi_py.options.HtmlOptions

::: takumi_py.options.ImageResource

::: takumi_py.options.FontResource
