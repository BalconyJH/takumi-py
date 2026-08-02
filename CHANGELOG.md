# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses semantic versioning with Python-compatible prerelease
identifiers.

## [Unreleased]

## [0.3.0] - 2026-08-02

### Added

- Add custom Jinja filter registration to `TemplateRenderer` and
  `render_template_to_html`.
- Allow callers to inject a complete Jinja `Environment`, including custom
  loaders, globals, tests, extensions, and undefined-value policies, without
  giving up the custom filter convenience API.
- Allow `TemplateRenderer` to reuse an injected, preconfigured `Renderer`.
- Add typed raw RGBA image sources for node trees, including premultiplied-alpha
  input support.
- Add per-renderer resource cache budgets through `cache_max_bytes` and a
  process-wide `set_glyph_cache_max_bytes` configuration API.
- Add a Zensical documentation site with task-oriented guides, generated API
  reference, migration notes, and maintainer workflows.

### Changed

- Update Takumi from 2.0.1 to 2.5.4, including `takumi-core` 0.11.0,
  `takumi-raster` 0.4.5, `takumi-svg` 0.3.4, and `takumi-html` 0.1.17.
- Adopt Takumi's unified resource cache and new CSS support for SVG filter
  references, `font-kerning`, `tab-size`, and `text-underline-position`.
- Extend the embedded Geist last-resort font's weight axis from 400–700 to
  300–800.
- Validate the complete release artifact set and rebuild a wheel from the source
  distribution before provenance generation or publication.
- Split CI, documentation, and repository hooks into exact-commit release gates,
  then create an annotated release tag automatically when the project version changes.
- Verify published PyPI filenames and SHA-256 digests before creating or recovering
  a GitHub Release, then deploy versioned documentation from the verified release tag
  through GitHub Pages artifacts and OIDC.
- Validate `cp310-abi3` wheels on Python 3.10 through 3.14 and run distribution
  smoke tests from isolated environments outside the source checkout.
- Update GitHub Actions pins, the CI uv runtime, and repository workflow linters
  to their latest releases.
- Update the documentation framework to Zensical 0.0.52.
- Document every public `Renderer` method and keep its internal compilation
  helpers outside the public API surface.
- Reject invalid render-level BCP-47 language tags, font weights outside
  `1..=1000`, and zero-duration animation scenes or frames.

### Removed

- Remove the no-op `validate` argument from HTML compile, render, measure, and
  SVG methods; node validation remains available on node-based APIs.

### Fixed

- Align `_core.pyi` with the native runtime exports, constructor semantics, and
  non-subclassable PyO3 classes, enforced by `mypy.stubtest` in `make check`.
- Include the embedded Geist font's OFL license in source and wheel
  distributions, and verify that wheels can be rebuilt from the source
  distribution without relying on the repository checkout.
- Include the selected Takumi MIT license and third-party notice in source and
  wheel distributions.
- Prevent transparent intermediate filter buffers from underflowing while
  computing alpha bounds, which fixes valid `drop-shadow()` filter renders.
- Skip release jobs when a valid tag has not reached `main` yet instead of
  failing the pull request check, while leaving ordinary CI checks running.

## [0.2.0] - 2026-07-10

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
- Align the built-in fallback font with Takumi v2 by embedding the Geist Latin
  last-resort font instead of Manrope.
- Document that render-level `lang` drives locale-aware text shaping, while CSS
  `:lang()` matching depends on HTML or node `lang` attributes.
- Attest release wheels and source distributions before publishing them, and
  expose each PyPI release as a GitHub Deployment linked to its PyPI version.

### Deprecated

- Deprecate `fetched_resources`, `load_font`, `load_fonts`, `persistent_images`, `put_persistent_image`, and `clear_image_store` in favor of per-render `images` and `register_font(s)`.

### Removed

- Remove the Python-side HTML parser and the runtime `selectolax` dependency.

### Fixed

- Avoid an authenticated `git fetch` during release tag validation so private repositories can validate tags with persisted checkout credentials disabled.
- Check out the `takumi` submodule in CI, Prek, and release jobs before running editable builds or Cargo checks.
- Check out the repository before creating or updating GitHub Releases so `gh release create --verify-tag` has a Git directory.
- Reuse an existing GitHub Release on reruns by uploading distribution artifacts with `--clobber`.
- Support inline image byte sources in node trees without triggering a native
  deserialization panic.
- Include the Takumi workspace root manifest and embedded default font in the
  source distribution so clean sdist builds can resolve path dependencies.

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

[unreleased]: https://github.com/BalconyJH/takumi-py/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/BalconyJH/takumi-py/releases/tag/v0.3.0
[0.2.0]: https://github.com/BalconyJH/takumi-py/releases/tag/v0.2.0
[0.1.0]: https://github.com/BalconyJH/takumi-py/releases/tag/v0.1.0
