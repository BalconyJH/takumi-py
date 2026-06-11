# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Publish PyPI distributions and GitHub Release artifacts in parallel after wheel and sdist builds complete.
- Limit the release wheel matrix to Linux x86_64, Linux aarch64, macOS arm64, and Windows x64.

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

[unreleased]: https://github.com/BalconyJH/takumi-py/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/BalconyJH/takumi-py/releases/tag/v0.1.0
