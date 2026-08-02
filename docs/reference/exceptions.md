# Exceptions

All public exception classes can be imported from `takumi_py`.

| Exception | Typical boundary |
| --- | --- |
| `TakumiError` | Base class exposed by the binding |
| `NodeValidationError` | Python input does not match the typed node structure |
| `NodeDecodeError` | A native node or measurement result cannot be decoded |
| `HtmlParseError` | The HTML parser rejects its input |
| `StyleSheetError` | CSS or keyframe compilation fails |
| `FontError` | Font description, parsing, or registration fails |
| `ResourceError` | An image or another resource is invalid or undecodable |
| `RenderError` | Layout or static rendering fails |
| `AnimationError` | Frame generation or animation encoding fails |
| `UnsupportedFormatError` | The requested output format is unsupported |

Catch the narrowest useful exception. Catch `TakumiError` only at an API boundary
that intentionally translates every binding failure into an application-level error:

```python
from takumi_py import FontError, FontResource, Renderer

try:
    Renderer().register_font(FontResource(b"not a font"))
except FontError as error:
    raise ValueError("invalid configured font") from error
```

!!! danger "Preserve the original error"

    Do not catch `Exception` and discard the cause. Native error messages carry the
    context required to locate invalid render inputs.
