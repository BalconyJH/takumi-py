# Support matrix

## Runtime

| Component | Supported range |
| --- | --- |
| Python | 3.11+ |
| ABI | CPython abi3, minimum cp311 |
| Linux wheels | x86_64 and aarch64, manylinux2014 |
| macOS wheels | Apple Silicon, macOS 11+ |
| Windows wheels | x64 |

Other platforms may build from the source distribution, but they are outside the
published wheel matrix.[^sdist]

## Versioning and deprecations

While takumi-py is at 0.x, its version numbers mean:

- A patch release, such as 0.4.1, only fixes bugs and keeps the public API.
- A minor release, such as 0.5.0, may change or remove public APIs. The changelog
  lists each change, and a [migration guide](../migration/index.md) covers the larger
  ones.
- A deprecated API keeps working, with a `DeprecationWarning`, through at least the
  next minor release. It is removed no earlier than the second minor release after
  the one that deprecated it, and the warning names that release.

| Deprecated | Since | Removed in | Use instead |
| --- | --- | --- | --- |
| `FontResource.subset_of` | 0.4.0 | 0.6.0 | `name` with `unicode_range` |
| `dithering="floyd-steinberg"` | 0.4.0 | 0.6.0 | `dithering="ordered-bayer"` |

## Inputs and outputs

| Category | Supported range |
| --- | --- |
| Inputs | Node trees, raw RGBA pixels, HTML, Jinja templates, compiled nodes |
| Raster | PNG, JPEG, WebP, ICO, raw RGBA |
| Vector | SVG |
| Animation | WebP and APNG up to 90 fps, GIF up to 50 fps |
| Layout | Measurement of nodes, HTML, and compiled nodes |

## Resource model

- One Latin Geist last-resort font is compiled into the extension.
- Callers provide all other font and image bytes. Fonts register per renderer, can be
  split into `unicode_range` subsets, and can be released again.
- `resource_urls()` discovers URLs without accessing the network.
- Images accept a per-render cache hint; the binding does not provide an HTTP client.
- Each renderer exposes a resource-cache budget; glyph caches use a separate
  process-wide budget configured before first use.

## Explicit exclusions

- Playwright or browser fallback
- Remote resource fetching
- `AbortSignal` or an asynchronous cancellation protocol
- Data URL convenience APIs
- A Node.js sidecar
- Direct mappings of Takumi's internal layout, cache, or glyph implementation types

!!! info "Compose infrastructure at the application boundary"

    These exclusions keep binding responsibilities aligned with Takumi core. Compose
    remote fetching, persistent caching, or task cancellation in the application
    instead of reaching through renderer internals.

[^sdist]: A source build requires Rust 1.91 or later, a Python development
    environment, and the native dependencies of the target platform.

*[ABI]: Application Binary Interface
