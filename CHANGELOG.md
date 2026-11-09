# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses semantic versioning with Python-compatible prerelease
identifiers. From 0.4.0 on, `make changelog` ends each release with its commits and
contributors, and the release's section is published as its GitHub Release notes.

## [Unreleased]

### Fixed

- Avoid native stack exhaustion while compiling, measuring, rendering, and releasing
  deeply nested nodes on small Python worker stacks; reject cycles with binding errors.
- Validate Python node trees and convert measured output iteratively, preserving the
  supported depth without leaking Python recursion errors.
- Honor omitted, cleared, and explicitly overridden keyframes consistently across
  node, HTML, template, SVG, measurement, sequence, and animation entry points.
- Preserve independent CSS source EOF recovery and the relative order of CSS and
  structured keyframe rules when composing existing stylesheets.

### Changed

- Run maintenance-branch checks and installed-wheel regressions on eight platforms
  in both debug and release profiles, retaining separate regression reports.

## [0.4.0] - 2026-11-07

### Added

- Add `FontResource.unicode_range` so each subset of a family registers under one
  `name` and serves only the codepoints its `@font-face` declares.
- Add `Renderer.unregister_font` and `Renderer.clear_fonts` to release registered
  fonts.
- Add a budgeted font cache, Takumi's `cacheFont`/`cachedFonts`:
  `Renderer.cache_font(font, key)` registers a font the renderer may release,
  `Renderer.cached_fonts(key)` reports whether it still holds one, and
  `Renderer(font_cache_max_bytes=...)` releases the least recently used cached
  families past the budget. Renders mark the families in `font_families` used, and
  fonts from `register_font` are never released.
- Decode `data:` URI images through the renderer's resource cache, so repeated
  renders that inline the same image decode it once.
- Add a Takumi 2.17 migration guide, and document font subsets, font release,
  animation frame-rate limits, and the Takumi submodule upgrade procedure.
- Deploy the documentation on `main` as a `dev` version in both languages, listed
  above the releases in the version selector, through the new `Preview · Docs`
  workflow; `latest` stays on the newest release.
- Add `make changelog`, which dates the `[Unreleased]` notes as the project version
  and appends the release's commits, grouped by type and linked by hash, with
  @-mentions of its contributors, generated with git-changelog.
- Publish the documentation in Simplified Chinese alongside the American English
  primary, with a one-click language toggle in the header that keeps the version,
  page, and anchor, a Chinese README, and a docs build check that keeps both
  languages' pages, anchors, code samples, and configuration in sync.
- Add `make release VERSION=x.y.z`, which sets the version in `pyproject.toml`,
  `Cargo.toml`, and both lock files, writes the changelog entry, and checks the
  release contract.
- Release alphas, betas, and release candidates, such as `0.4.0rc1` (`0.4.0-rc.1` in
  `Cargo.toml`): they publish as GitHub prereleases, and their documentation never
  takes `latest`.
- Publish wheels for four more platforms: musllinux_1_2 x86_64 and aarch64, for
  Alpine and other musl-based Linux, macOS on Intel, and Windows on arm64. These
  platforms no longer build from the source distribution.
- Smoke-test the `cp311-abi3` wheel on Python 3.15.
- Publish project links, classifiers, and keywords on PyPI.
- Document the versioning and deprecation policy in the support matrix. Deprecation
  warnings now name the release that removes the API: `FontResource.subset_of` and
  `dithering="floyd-steinberg"` go in 0.6.0.
- Add `SECURITY.md`, which asks for vulnerability reports through GitHub's private
  vulnerability reporting.
- Have Dependabot propose weekly uv and Cargo updates alongside GitHub Actions, with
  separate pull requests for the exactly pinned ty and Zensical.
- Show a banner on every documentation version but the latest release: the `dev`
  preview says it comes from `main` and can describe unreleased changes, and older
  releases and prereleases link to the latest one.

### Changed

- Clarify that compiled HTML bundles currently return no stylesheets, and describe
  render options, resources, keyframes, and result types in the generated API
  reference.
- Update Takumi from 2.5.4 to 2.17.1, including `takumi-core` 0.32.0,
  `takumi-raster` 0.5.9, `takumi-svg` 0.3.31, and `takumi-html` 0.6.0. Layout,
  text, filters, backgrounds, decorations, and paint order now follow Chrome more
  closely; see the upstream changelog for the rendering changes.
- Update PyO3 from 0.28 to 0.30 and refresh compatible Rust dependencies.
- Declare `rust-version = "1.91"` so dependency resolution stays within the
  pinned CI toolchain.
- The renderer resource cache now defaults to 64 MiB, up from 16 MiB.
- Publish each version's `CHANGELOG.md` section as its GitHub Release notes, instead of
  GitHub's generated notes.
- `Release · Tag` and `Release · Publish` share one release-contract check, which now
  also requires the commit list `make changelog` generates.
- Refresh the toolchain to Zensical 0.0.72, ty 0.0.91, Ruff 0.17, mypy 2.4, and
  maturin 1.15, with current Prek hooks. ty and Zensical, still at 0.0.x, are pinned
  exactly so that each upgrade is deliberate, and the commit message hook now
  accepts `chore` and `typing` commits.
- Name the GitHub Actions workflows by stage: `Check · Build and test`, `Check · Docs`,
  `Check · Lint`, `Release · Tag`, and `Release · Publish`, with verb-first job names.
  Workflow file names, and so the PyPI Trusted Publisher binding, are unchanged.
- Stream `render_animation` frames straight into the encoder, so an animation holds
  one raw frame at a time instead of all of them.
- Split the native extension into focused modules and pass resolved options, fonts,
  images, and frames across the private `_core` boundary as objects instead of
  positional keyword lists and tuples. The public Python API and its output are
  unchanged.
- Reject conflicting encoder options, such as `lossless=True` with PNG output,
  before rendering rather than after.
- Link the READMEs to the hosted documentation of the latest release instead of the
  Markdown sources, and check that each link names an existing page in both
  languages.
- Restructure the documentation: English sources move to `docs/en/`, new HTML and
  CSS and Output formats guides take over from the overloaded rendering guide, the
  release guide is now in English, and the README keeps only the overview,
  installation, and quickstart.
- `<img>` without a `src` now parses as an empty box instead of raising
  `HtmlParseError`.
- Run the core fixture smoke test over upstream's relocated `fixtures-html`
  sources, which restores coverage to all 336 HTML fixtures.

### Deprecated

- `FontResource.subset_of` now only sets the family name, taking precedence over
  `name`; use `name` with `unicode_range` instead.
- `dithering="floyd-steinberg"` is an alias of `"ordered-bayer"` now that Takumi
  has dropped its whole-image error-diffusion pass.

### Removed

- Remove the testing-stage warnings from the READMEs and documentation home pages.
- **Breaking:** remove the compatibility shims deprecated in 0.2.0: the
  `fetched_resources` argument of every render call and `RenderOptions`,
  `Renderer(persistent_images=...)`, and `Renderer.load_font`, `load_fonts`,
  `put_persistent_image`, and `clear_image_store`. Pass `images` to each render and
  register fonts with `register_font` or `register_fonts`; the Takumi v2 migration
  guide maps each one.
- Drop Python 3.10 support. takumi-py now requires Python 3.11 or later and
  publishes `cp311-abi3` wheels.
- Drop the `typing-extensions` runtime dependency; `TypedDict` and `NotRequired`
  come from the standard library on Python 3.11.
- Drop the unused direct `parley` dependency, which Takumi no longer uses.

### Fixed

- Point deprecation warnings at the calling code. Nested public calls, such as
  `render_node` delegating to `render_compiled`, attributed them to `takumi_py`
  itself, where Python's default filters hide `DeprecationWarning`.
- Enforce the documented frame-rate limits in `render_animation`: above 90 fps for
  WebP and APNG, or 50 fps for GIF, it now raises `ValueError` instead of writing
  frame delays that decoders clamp to 100 ms.
- Document that `set_glyph_cache_max_bytes` has no effect once the glyph cache is
  in use, instead of claiming it raises `RuntimeError`.

### Commits

#### Breaking changes

- **build:** require Python 3.11 or later ([56927f1](https://github.com/BalconyJH/takumi-py/commit/56927f14c235383917e263bf93d6ceeee766ce6f))
- **build(release):** generate changelog entries with git-changelog ([0f0233f](https://github.com/BalconyJH/takumi-py/commit/0f0233facfe73e1e55f773801224883ff4305112))
- **refactor:** remove the compatibility shims deprecated in 0.2.0 ([0fcd62c](https://github.com/BalconyJH/takumi-py/commit/0fcd62c0f0e9e53ea2da69028f9a5cba2c4a9515))

#### Features

- **core:** update Takumi to 2.17.1 ([e04b503](https://github.com/BalconyJH/takumi-py/commit/e04b5037af8b4f88cd7e4485bc4b7fb91f07db09))
- **api:** adapt bindings to Takumi 2.17.1 ([ca03d58](https://github.com/BalconyJH/takumi-py/commit/ca03d58c7a0059a6eaeacd2407caddc9cf4f88ca))
- **core:** expose registered fonts ([3caeb02](https://github.com/BalconyJH/takumi-py/commit/3caeb02af9d2fffe4d3393b41966f45e8160714e))
- **api:** release registered fonts ([b3c3300](https://github.com/BalconyJH/takumi-py/commit/b3c3300c0ea2fa5a76004cefd7a99e4368fc8e6b))
- add a budgeted font cache ([884061d](https://github.com/BalconyJH/takumi-py/commit/884061d6eff9eaef8982572aa426644850be4855))

#### Bug fixes

- **docs:** open dev at a language root that has no release yet ([a3d644b](https://github.com/BalconyJH/takumi-py/commit/a3d644b717d51f29887a0158ed0ffa58fd80a924))

#### Performance

- **animation:** stream frames into the encoder ([a78dad7](https://github.com/BalconyJH/takumi-py/commit/a78dad7076ce3077ad5ec537f09d3b4dcac356a9))

#### Refactoring

- **core:** split the native extension into modules ([fc7f8cd](https://github.com/BalconyJH/takumi-py/commit/fc7f8cdc7552f3f8de38dd58bb7dd685171e0111))
- **api:** pass native options as objects ([835535f](https://github.com/BalconyJH/takumi-py/commit/835535f1acd27d5633c74d072311d26e6d80d8c2))

#### Documentation

- document the Takumi 2.17 upgrade ([5ec5110](https://github.com/BalconyJH/takumi-py/commit/5ec51105e0f4d08e60f662ff1fce0ffef2fcc40a))
- document registered fonts ([edafd79](https://github.com/BalconyJH/takumi-py/commit/edafd795871b14426209c77e3796014622318109))
- record the PyO3 update ([4cbb4c7](https://github.com/BalconyJH/takumi-py/commit/4cbb4c737c165c1142644184bfec2059b754d4a8))
- **animation:** describe streamed encoding ([1e22b22](https://github.com/BalconyJH/takumi-py/commit/1e22b229062269531580d663461a89d45f86771a))
- record the animation streaming optimization ([73250e6](https://github.com/BalconyJH/takumi-py/commit/73250e69d4ecf163a01570eeccade56c73512cb7))
- **migration:** document the Takumi 2.17 upgrade ([01a7415](https://github.com/BalconyJH/takumi-py/commit/01a74153f8cdc170ce1170dfdb5da47d24f467c7))
- refresh Takumi 2.17 guidance ([772d79e](https://github.com/BalconyJH/takumi-py/commit/772d79e5f34dc433ed0bc537394354c5fa530926))
- add the Takumi 2.17 migration page ([b4f5742](https://github.com/BalconyJH/takumi-py/commit/b4f5742fc4e148f123f41062a383df15b66f7e07))
- record the Takumi 2.17 migration ([d118cd4](https://github.com/BalconyJH/takumi-py/commit/d118cd4ab8bec73d0bfc27ca195e416bb9c0de3d))
- restructure the English documentation site ([28cd761](https://github.com/BalconyJH/takumi-py/commit/28cd761356a0f8e11437e1656826f6be63cc390a))
- add the Simplified Chinese documentation site ([838c206](https://github.com/BalconyJH/takumi-py/commit/838c206937bf0df1cb5a1d06f04e09977dec0b2d))
- add bilingual project readmes ([2ab7ff3](https://github.com/BalconyJH/takumi-py/commit/2ab7ff3247fd9369f0cb9574c168d7aa2a091d5c))
- record the bilingual documentation site ([81f0ddd](https://github.com/BalconyJH/takumi-py/commit/81f0ddd220ede17f862cd3e24e4df365d8d4a788))
- document bilingual deployment ([e8e2c89](https://github.com/BalconyJH/takumi-py/commit/e8e2c890a0868ff74081d7f818402d98b495e4f7))
- **en:** document icon conventions ([688c616](https://github.com/BalconyJH/takumi-py/commit/688c616c3ed2cfe33c2e5e7e7fc9340620377e08))
- **zh:** document icon conventions ([57ee622](https://github.com/BalconyJH/takumi-py/commit/57ee622719fd3e02cf574b15101814399fd5b61e))
- record the native extension refactor ([1057596](https://github.com/BalconyJH/takumi-py/commit/1057596d88ff85d1fbf4d7a0cb33e11b63f5b3da))
- update the Python version requirement ([79495de](https://github.com/BalconyJH/takumi-py/commit/79495de4a8b74462016c50a44142d39f3e3ee1cd))
- record the Python 3.11 requirement ([0d3416e](https://github.com/BalconyJH/takumi-py/commit/0d3416e2eb64a42cd31c1e12bf7a5b02958072a4))
- document changelog generation ([7943a3a](https://github.com/BalconyJH/takumi-py/commit/7943a3a16545573713564ec2fc9ec22cb77e7d8c))
- use the stage-based workflow names ([bc5cbb7](https://github.com/BalconyJH/takumi-py/commit/bc5cbb76d6e2aae43d063e23159ef1c9841419a0))
- switch languages with a one-click header toggle ([df48946](https://github.com/BalconyJH/takumi-py/commit/df48946f6598c59cd56794b97eef621506f8a9e5))
- document the language toggle ([4b13043](https://github.com/BalconyJH/takumi-py/commit/4b130431a70b25e9b5104c296428aec577e6829b))
- document the dev documentation preview ([b23a13c](https://github.com/BalconyJH/takumi-py/commit/b23a13c57e112c94840f3e1c258ac740c0847fbd))
- mark dev and older versions with a version banner ([4db0e66](https://github.com/BalconyJH/takumi-py/commit/4db0e6602531ff043aa7d87e91f90db9d3fa85f4))
- **readme:** link to the Python API reference ([34cc635](https://github.com/BalconyJH/takumi-py/commit/34cc63504150fff46c2c7ee26cf654ec59e00a77))
- **readme:** include documentation builds in development checks ([9314968](https://github.com/BalconyJH/takumi-py/commit/931496855195f7653be3cd321736c7f737a3ab2c))
- **html:** clarify parser options and compiled stylesheet bundles ([a704dc0](https://github.com/BalconyJH/takumi-py/commit/a704dc076cb23190c36f41fd479d89e9edaecfbf))
- **animation:** document structured keyframe types ([fed338b](https://github.com/BalconyJH/takumi-py/commit/fed338b4c8a5ba2266732544f90a20636738c23d))
- **options:** describe render and animation encoder settings ([88c5188](https://github.com/BalconyJH/takumi-py/commit/88c5188f81d6b7637a6ebdf312b3a87404b56e6b))
- **types:** describe node inputs and image resources ([2e58f10](https://github.com/BalconyJH/takumi-py/commit/2e58f10dcc6dfda25ed9f7494d1c5cc7d523ffea))
- **types:** describe measurement results and animation frames ([542bd48](https://github.com/BalconyJH/takumi-py/commit/542bd48c4e84a14dba3d88591fe2245807daa0a5))
- **changelog:** record API reference improvements ([7d323bb](https://github.com/BalconyJH/takumi-py/commit/7d323bb9120acd9c817d565d7e2b67e6d336b5c4))
- **readme:** remove testing-stage warnings ([20eff05](https://github.com/BalconyJH/takumi-py/commit/20eff0584c75acd204f4437c38b31535a2035578))
- **site:** retire testing-stage notices and guidance ([58b0701](https://github.com/BalconyJH/takumi-py/commit/58b0701a672083c2fe541e10588c1eb1cde34a1f))
- **migration:** clarify the 0.4.0 upgrade and removed APIs ([ce675a4](https://github.com/BalconyJH/takumi-py/commit/ce675a4def609309855a1d3dd1ebd48905328512))
- **readme:** refresh installation and usage guidance ([0a93f08](https://github.com/BalconyJH/takumi-py/commit/0a93f088a8c660284309705c755d8adb67a7cd0b))

#### Tests

- **animation:** cover streamed frame encoding ([a97c09e](https://github.com/BalconyJH/takumi-py/commit/a97c09e33e29c149dc6157b7bce96549133f8f7d))
- **api:** cover the split native extension ([95e35ed](https://github.com/BalconyJH/takumi-py/commit/95e35edfd6ca08bddd99ef173d8f37108ed9bc62))
- **docs:** validate README links to the dev preview ([3a24fef](https://github.com/BalconyJH/takumi-py/commit/3a24fef654ea59df15f37784248c48063a52613e))

#### Build

- **deps:** update PyO3 to 0.30 ([72f5af4](https://github.com/BalconyJH/takumi-py/commit/72f5af4696f01f319f9178386df9c7b0eca6f36a))
- **docs:** add bilingual documentation tooling ([d5178c8](https://github.com/BalconyJH/takumi-py/commit/d5178c8345165b6325999add12875134289bb8ca))
- align release tooling with Python 3.11 ([623b3da](https://github.com/BalconyJH/takumi-py/commit/623b3daa87610ca6ea5719f8357d411c7810ab2b))
- **docs:** require Python 3.11 for translation checks ([f05284b](https://github.com/BalconyJH/takumi-py/commit/f05284b69147661e68dc1f2c590e0be89394a574))
- refresh the toolchain and pin the 0.0.x tools exactly ([e485fd2](https://github.com/BalconyJH/takumi-py/commit/e485fd2bd3ca8db49318b1a50da1ee6b92676776))
- publish PyPI metadata, a security policy, and a deprecation policy ([6355180](https://github.com/BalconyJH/takumi-py/commit/6355180b704b619646feef3e7aef9aa55aceff73))
- **deps-dev:** bump zensical from 0.0.71 to 0.0.72 (#13) ([57d1490](https://github.com/BalconyJH/takumi-py/commit/57d1490e3d6bb589e90740d46c49f15ef9eb0323))

#### Continuous integration

- **docs:** deploy the Simplified Chinese docs under zh ([17daf67](https://github.com/BalconyJH/takumi-py/commit/17daf67857cd55c45eab8014e77b2a3595c20960))
- **release:** publish changelog sections as release notes ([4d98db0](https://github.com/BalconyJH/takumi-py/commit/4d98db034a2e8e21898ddfd7156366a4538aea94))
- name workflows and jobs by stage ([ce18ebc](https://github.com/BalconyJH/takumi-py/commit/ce18ebc8223a9eb17c498f80906d9d6d96603bd2))
- **release:** share docs deployment and serialize Pages deploys ([94cb5f2](https://github.com/BalconyJH/takumi-py/commit/94cb5f2958cbc9070ba087e52b2ae0ff66506132))
- **docs:** deploy main as the dev documentation preview ([f0bb159](https://github.com/BalconyJH/takumi-py/commit/f0bb1598e1e3b174ee23e2b75dd77c7d67b8126b))
- **release:** support prereleases and gate on the generated changelog ([0db6d29](https://github.com/BalconyJH/takumi-py/commit/0db6d29955ea72bc1eb88e99ad74cd06119b0417))
- build wheels for musllinux, Intel macOS, and Windows on arm64 ([996ffe1](https://github.com/BalconyJH/takumi-py/commit/996ffe1c20cced68881210e904c393c791ae1f4d))

#### Chores

- **deps:** bump astral-sh/setup-uv to 10.3.0 ([f60a49d](https://github.com/BalconyJH/takumi-py/commit/f60a49dcddea24e5dd89c6dca7e5e98f4fe02f9c))
- **deps:** bump setup-rust-toolchain to 2.0.0 ([b38f1a4](https://github.com/BalconyJH/takumi-py/commit/b38f1a4ecdc7fe41c692ce42d1965a41794f73a6))
- **deps:** bump upload-artifact to 7.0.2 ([4362503](https://github.com/BalconyJH/takumi-py/commit/43625031ac3b957a29423fbc7e2108a8c4406b71))
- **deps:** bump download-artifact to 8.0.2 ([f0797bc](https://github.com/BalconyJH/takumi-py/commit/f0797bccefce228bbc815d0dc8ae3790752b6a0c))
- **deps:** bump prek-action to 3.0.1 ([861290e](https://github.com/BalconyJH/takumi-py/commit/861290e64688747fb77a79995ab134fce87fe389))
- **deps:** bump attest-build-provenance to 4.2.2 ([4cba980](https://github.com/BalconyJH/takumi-py/commit/4cba980d69071dfa179939b021f612d9ef370d84))
- **deps:** bump deploy-pages to 5.0.1 ([b4f905e](https://github.com/BalconyJH/takumi-py/commit/b4f905e903e45ec0d015329ba40e1f9a26001002))
- **deps:** bump the github-actions group with 4 updates (#12) ([46e7f2b](https://github.com/BalconyJH/takumi-py/commit/46e7f2b628bbb9f99f6805a8eb371173c133915e))

#### Other

- **typing:** require Python 3.11 syntax ([5e15e1f](https://github.com/BalconyJH/takumi-py/commit/5e15e1ff97c8a51ffedaa46535e294651ea2ba94))

**Full diff**: [v0.3.0...v0.4.0](https://github.com/BalconyJH/takumi-py/compare/v0.3.0...v0.4.0)

**Contributors**: @BalconyJH, @dependabot

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

[unreleased]: https://github.com/BalconyJH/takumi-py/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/BalconyJH/takumi-py/releases/tag/v0.4.0
[0.3.0]: https://github.com/BalconyJH/takumi-py/releases/tag/v0.3.0
[0.2.0]: https://github.com/BalconyJH/takumi-py/releases/tag/v0.2.0
[0.1.0]: https://github.com/BalconyJH/takumi-py/releases/tag/v0.1.0
