# Development

## Prepare the environment

```bash
git submodule update --init --recursive
uv sync --all-groups --all-extras
uv run maturin develop
```

The Rust toolchain is pinned by `rust-toolchain.toml`. Project lock files manage
Python, Rust, and documentation dependencies; do not patch the repository environment
with ad hoc `pip install` commands.

## Common checks

```bash
make check
make docs-build
prek run --all-files
prek run actionlint --all-files --hook-stage=manual
```

`make check` runs Ruff, ty, `mypy.stubtest` for the native extension, pytest,
Rustfmt, and Clippy. The documentation build runs separately because it uses the docs
dependency group: it checks that the Chinese pages mirror the English source, then
builds both languages strictly, treating warnings as failures. The manual Actionlint
stage validates embedded workflow shell scripts in addition to the normal repository
hooks.

The checkers are pinned so that results only change when the repository does: the
Prek hooks by `rev` in `prek.toml`, and ty, which is still at 0.0.x, to one exact
version in the `dev` dependency group. Upgrade ty by raising its pin and fixing what
`make typecheck` reports in the same commit; keep the Ruff hook `rev` and the locked
Ruff version in step.

## Tests

The pytest suite lives in `tests/`. The Ubuntu quality job runs the full suite in
parallel through `make test`; the installed-wheel portability matrix runs the smaller
regression selection described below.

| Module | Covers |
| --- | --- |
| `test_render_node.py`, `test_render_html.py`, `test_render_template.py` | The node, HTML, and template entry points |
| `test_document.py`, `test_document_rendering.py` | Document and fragment ownership, compilation, layout, canvas sizing, and SVG/raster output |
| `test_html_adapter.py`, `test_inline_style.py` | HTML parsing and inline styles |
| `test_native_compile.py`, `test_stylesheet_composition.py`, `test_keyframe_options.py`, `test_render_needs.py` | Free compiler functions, CSS merging, keyframes, render options, and resource requirements |
| `test_core_binding_features.py` | Options, fonts, images, caches, measurement, SVG, and animation |
| `test_node_bytes.py`, `test_raster.py` | Buffered node data, native decoding limits, raster ownership, and image encoding |
| `test_native_stack.py` | Full-depth native and CSS pipelines under small thread stacks, boundary errors, and subprocess stage diagnostics |
| `test_takumi_core_fixtures.py` | Every upstream HTML fixture under `takumilib/takumi/tests/fixtures-html` renders |
| `test_examples.py` | Every script in `examples/` runs and writes its output |
| `test_math.py`, `test_math_validation.py`, `test_math_process.py`, `test_math_layout.py`, `test_math_integration.py` | MathJax output, SVG and TeX validation, worker crashes and deadlines, layout, and downstream rendering |
| `test_typing_surface.py` | The documented public `Renderer` surface and native typing artifacts |
| `test_repository_scripts.py` | The release, changelog, docs deployment, and docs translation scripts in `.github/scripts/` |

## CI matrix { #ci-matrix }

This section describes the workflow configuration; it does not report that every matrix
cell has completed successfully. The `quality` job runs the full pytest suite only on
Ubuntu. Portability coverage comes from the `wheel-smoke` job, which is configured for
eight targets and both `debug` and `release` profiles: 16 wheel-and-regression cells.
The targets are Linux x86_64 and aarch64, musllinux x86_64 and aarch64, macOS x86_64
and aarch64, and Windows x64 and arm64.

Each cell builds its own wheel and runs 11 selected test modules against that installed
artifact. `test-wheel.py` copies the modules from the runner checkout into a temporary
directory outside the repository, creates a fresh virtual environment, and installs
the wheel with its math extra. A probe verifies that `takumi_py`, its native extension,
and `py_mini_racer` all load from that environment. The JUnit report fails the job if
any selected test is skipped, so a missing math runtime cannot produce a false green
result.

The portability selection contains these native, node, and CSS modules:

- `test_native_stack.py`
- `test_node_bytes.py`
- `test_native_compile.py`
- `test_stylesheet_composition.py`
- `test_keyframe_options.py`
- `test_render_node.py`

It also contains these math modules:

- `test_math.py`
- `test_math_validation.py`
- `test_math_process.py`
- `test_math_layout.py`
- `test_math_integration.py`

### CI execution order { #ci-execution-order }

The six workflow files stay flat: none calls another through a reusable-workflow or
composite-action layer. Inside `ci.yml`, the job order is:

```text
quality ---------------------------------------------------------+
  |                                                              |
  +--> sdist-smoke ----------------------------------------------+
  |                                                              +--> result
  `--> wheel-smoke [8 platforms x 2 profiles] -------------------+
         `--> abi3-smoke [Python 3.11..3.15] --------------------+
```

`quality` gates both build branches and then `sdist-smoke` and `wheel-smoke` run in
parallel. `wheel-smoke` has 16 cells. Only its eight `release` cells upload a
`ci-wheel-*` wheel; both profiles retain their `ci-regressions-*` results. The matrix
dependency makes `abi3-smoke` wait for every cell, then exercise the Linux x86_64
release wheel on Python 3.11 through 3.15. `result` directly reads the four job results
for `quality`, `sdist-smoke`, `wheel-smoke`, and `abi3-smoke`; those direct needs are
what make it the required four-layer check. It writes a summary table for all four
layers, and failure, cancellation, or skipping in any layer fails Required checks.

At workflow level, trusted `main` pushes have one exact-SHA coordination path and one
independent preview path:

```text
Check - Build and test ---+
Check - Docs -------------+--> exact-SHA join --> Release - Tag --> Publish
Check - Lint -------------+

Check - Docs --> Preview - Docs --> gh-pages --> Pages
```

Each of the three completed `workflow_run` events re-queries all three `main` push runs
with GitHub's API and requires their successful `head_sha` to equal the tag source SHA,
so whichever check finishes first cannot tag early. Preview runs from its own
`workflow_run` branch and does not wait for CI, tagging, or publishing. Release and
preview Pages jobs share the `github-pages` concurrency group; that lock serializes
deployments but is not a `needs` edge. The release jobs after tagging are described in
the [automatic release pipeline](releasing.md#automatic-release-pipeline).

After building exactly one current-platform wheel into `dist/`, reproduce the selected
installed-wheel suite locally from the repository root:

```bash
python .github/scripts/test-wheel.py dist --python 3.11 --uv uv --junit-xml reports/regressions.xml
```

The command creates its own temporary environment and writes both the JUnit report and
a matching pytest log under `reports/`.

## Distribution contract

Build the current platform wheel and sdist through the same local contract used by CI:

```bash
make build-artifacts
```

The target checks metadata and archive contents, installs the wheel in a temporary
environment outside the checkout, rebuilds a wheel from the sdist, and runs the native
rendering smoke against both paths. Use `make verify-artifacts DIST_DIR=/path/to/dist`
to validate an existing local pair.

## Native extension

The Python package loads from `python/`, and the native module is named
`takumi_py._core`. Rebuild it after changing Rust binding code:

```bash
uv run maturin develop
```

!!! warning "Rebuild before testing binding changes"

    Running Python tests without rebuilding can accidentally exercise a stale native
    artifact from the previous compilation.

## Takumi submodule

Takumi is an explicit source dependency of this repository. Pin `takumilib` to the
upstream release commit that a `takumi@X.Y.Z` tag points to, never to a branch tip or
a local merge:

```bash
git -C takumilib fetch origin --tags
git -C takumilib checkout --detach 'takumi@2.20.0^{commit}'
cargo update -w
```

The current next-major static preview follows the canonical Takumi 2.20 APIs:
crate-root `render`, `measure`, `render_svg`, and `needs`, with scene reuse left as an
internal, same-thread concern. The Python surface retains the finished bitmap instead
of exposing an unstable `Scene`. HTML resources follow the released `parse_html`
contract: the node and `<style>` CSS are separate, renderer methods return the
cascade-aware `RenderNeeds`, and applications supply `@font-face` bytes explicitly.

An upgrade must check:

- The submodule revision and `Cargo.lock`
- Version constraints for `takumi` and `takumi-core`
- Deprecations in the upstream API: Clippy runs with `-D warnings`, so a deprecated
  call fails the build. Adopt the replacement that the Node binding in
  `takumilib/takumi-napi` uses, and surface the change as a Python
  `DeprecationWarning`
- New upstream capabilities worth exposing, by comparing the Node binding's surface
  with `Renderer`
- That the build stays within the toolchain in `rust-toolchain.toml`: `rust-version`
  keeps the resolver on compatible crates, and running
  `cargo +1.91.0 clippy --locked --all-targets` through rustup confirms it
- That the HTML fixtures read by `tests/test_takumi_core_fixtures.py` still exist under
  `takumilib/takumi/tests/fixtures-html`
- Whether the source distribution can still rebuild a wheel in isolation
- Whether assets referenced by the binding under `takumilib/assets` changed. The
  2.20 binding embeds both `geist-latin-wght-300-800.ttf` and
  `geist-latin-wght-300-800.woff2`, so both must remain in the source distribution.
- Whether new crates or vendored sources change the license inventory. Cargo's source
  package currently carries `takumi-core/LICENSE-CHROMIUM`,
  `LICENSE-EMOJI-SEGMENTER`, and `LICENSE-ICU`. They are listed in
  `[project].license-files`, so every sdist and wheel carries the notices and records
  their paths in package metadata.

Upstream's `[patch.crates-io]` forks of fontations and harfrust apply only inside the
Takumi workspace. This crate builds against the crates.io releases, so a patch upstream
adds is not inherited.

!!! danger "The repository checkout is not an sdist dependency"

    Never hide missing distribution files by reading them from the surrounding
    checkout. The CI sdist smoke test must build and run entirely from the isolated
    source archive.
