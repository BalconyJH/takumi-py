# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses semantic versioning with Python-compatible prerelease
identifiers.

## [Unreleased]

## [0.2.0rc1] - 2026-07-05

### Added

- Add Takumi v2 SVG rendering through `render_svg_node`, `render_svg_html`, `render_svg_template`, and `render_svg_compiled`.
- Add per-render `images`, `font_families`, `lang`, and `lossless` options.
- Add `register_font` and `register_fonts` as the v2 font registration APIs.
- Add explicit `stylesheets` parameters to HTML render, measure, SVG, and template calls.
- Add `HtmlOptions` for Rust-backed HTML parser presets, Tailwind attribute mapping, and maximum parse depth.
- Add `ImageResource.cache`, v2 `FontResource` descriptor fields, typed node `lang`, `CompiledNode.resource_urls()`, and structured keyframe inputs across render APIs.

### Changed

- Migrate the native renderer from Takumi 1.7 to Takumi 2.0.1.
- Use Takumi v2's explicit `Fonts`, `ImageCache`, per-render images, and new raster output format model.
- Follow Takumi 2.0's public API for animation writers, font metadata overrides, language tags, fallback font families, structured keyframes, and image URL discovery.
- Route HTML parsing through Takumi's Rust `from_html` parser instead of the Python `selectolax` adapter.
- Refresh README and runnable examples around explicit HTML stylesheets, resource descriptors, parser options, and structured keyframes.
- Make ordinary CI run the full project check suite, including pytest and Cargo checks.
- Publish PyPI distributions and GitHub Release artifacts in parallel after wheel and sdist builds complete.
- Limit the release wheel matrix to Linux x86_64, Linux aarch64, macOS arm64, and Windows x64.

### Deprecated

- Deprecate `fetched_resources`, `load_font`, `load_fonts`, `persistent_images`, `put_persistent_image`, and `clear_image_store` in favor of per-render `images` and `register_font(s)`.

### Removed

- Remove the Python-side HTML parser and the runtime `selectolax` dependency.

### Fixed

- Avoid an authenticated `git fetch` during release tag validation so private repositories can validate tags with persisted checkout credentials disabled.
- Check out the `takumi` submodule in CI, Prek, and release jobs before running editable builds or Cargo checks.
- Check out the repository before creating or updating GitHub Releases so `gh release create --verify-tag` has a Git directory.
- Reuse an existing GitHub Release on reruns by uploading distribution artifacts with `--clobber`.

## [0.1.0] - 2026-06-10

### Added

- Initial Python 3.10+ bindings for the Takumi Rust renderer.
- Node Tree, HTML string, and Jinja template rendering into image bytes.
- Typed `RenderOptions` for viewport, output format, quality, font size, device pixel ratio, debug borders, time sampling, dithering, and per-render resources.
- Layout measurement APIs returning typed measured node trees.
- Custom font loading, persistent image resources, and per-render fetched image resources.
- CSS animation time sampling, sequence animation rendering, and WebP/APNG/GIF animated encoders.
- PEP 561 typing with `py.typed` and `_core.pyi` for the native binding surface.
- Examples for node rendering, HTML rendering, templates, render options, measurement, resources, and animation.
- GitHub Actions quality checks, Prek hooks, tag-based release automation, and release artifact builds.

### Changed

- Replaced the initial pydantic/msgpack validation and packing path with `msgspec`.
- Documented the project as testing-stage software while the core binding surface is still stabilizing.

### Removed

- Removed the experimental `pack_node()` API and `codec="msgpack"` compile path.
- Removed unused benchmark scripts.

[unreleased]: https://github.com/BalconyJH/takumi-py/compare/v0.2.0rc1...HEAD
[0.2.0rc1]: https://github.com/BalconyJH/takumi-py/releases/tag/v0.2.0rc1
[0.1.0]: https://github.com/BalconyJH/takumi-py/releases/tag/v0.1.0
