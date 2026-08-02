# Support matrix

## Runtime

| Component | Supported range |
| --- | --- |
| Python | 3.10+ |
| ABI | CPython abi3, minimum cp310 |
| Linux wheels | x86_64 and aarch64, manylinux2014 |
| macOS wheels | Apple Silicon, macOS 11+ |
| Windows wheels | x64 |

Other platforms may build from the source distribution, but they are outside the
published wheel matrix.[^sdist]

## Inputs and outputs

| Category | Supported range |
| --- | --- |
| Inputs | Node trees, raw RGBA pixels, HTML, Jinja templates, compiled nodes |
| Raster | PNG, JPEG, WebP, ICO, raw RGBA |
| Vector | SVG |
| Animation | WebP, APNG, GIF |
| Layout | Measurement of nodes, HTML, and compiled nodes |

## Resource model

- One Latin Geist last-resort font is compiled into the extension.
- Callers provide all other font and image bytes.
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

[^sdist]: A source build requires a supported Rust toolchain, a Python development
    environment, and the native dependencies of the target platform.

*[ABI]: Application Binary Interface
