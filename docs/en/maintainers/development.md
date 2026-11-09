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

The pytest suite lives in `tests/` and runs in parallel through `make test`:

| Module | Covers |
| --- | --- |
| `test_render_node.py`, `test_render_html.py`, `test_render_template.py` | The node, HTML, and template entry points |
| `test_html_adapter.py`, `test_inline_style.py` | HTML parsing and inline styles |
| `test_core_binding_features.py` | Options, fonts, images, caches, measurement, SVG, and animation |
| `test_takumi_core_fixtures.py` | Every upstream HTML fixture under `takumilib/takumi/tests/fixtures-html` renders |
| `test_examples.py` | Every script in `examples/` runs and writes its output |
| `test_typing_surface.py` | The documented public `Renderer` surface and native typing artifacts |
| `test_repository_scripts.py` | The release, changelog, docs deployment, and docs translation scripts in `.github/scripts/` |
| `test_native_stack.py`, `test_node_bytes.py` | Subprocess checks on 512 KiB and 1 MiB worker stacks, snapshot cleanup, and buffer fidelity |
| `test_keyframe_options.py`, `test_stylesheet_composition.py` | Keyframe inheritance/clearing and ordered CSS source composition |

## Maintenance branches { #maintenance-branches }

`0.4.x` starts from `v0.4.0` and accepts fixes for the existing API. It keeps
Takumi 2.17.1 and does not contain the document, math, or static raster APIs being
prepared on `dev`. Backport individual fixes after verifying the release baseline;
do not merge `dev` into the maintenance branch.

Pushes to `0.4.x` run build, documentation, and lint checks. The wheel job covers
eight platforms in both debug and release profiles. Each wheel runs the isolated
`test_native_stack.py`, `test_node_bytes.py`, `test_render_node.py`,
`test_keyframe_options.py`, and `test_stylesheet_composition.py` regressions through
`.github/scripts/test-wheel.py`. Missing tests, skipped cases, crashes, and timeouts
fail the job. Only release-profile wheels are uploaded as distribution artifacts.
This configuration is not evidence that every remote platform has passed.

The three Check workflows run independently. Within the build workflow, quality
must pass before either distribution job, and the ABI checks consume release wheels:

```text
push / pull_request
+-- Check: Build and test
|   +-- quality
|       +-- sdist-smoke
|       +-- wheel-smoke [8 platforms x debug/release]
|           +-- abi3-smoke [Python 3.11-3.15]
+-- Check: Docs
+-- Check: Prek
```

The small-stack fix belongs in the binding: the old Python-to-native conversion
recursed on the caller's stack before Takumi could enforce its node-depth limit.
The replacement snapshots and releases Python value trees iteratively, detects
cycles, and gives recursive native decoding, cloning, and rendering controlled
stack headroom. Measured output conversion and cleanup are also iterative.
Takumi still owns the schema and rendering behavior; this does not upgrade it.

The automatic tag and publish gates remain restricted to the existing `main`
release flow. Creating or pushing a maintenance branch does not authorize a release.
The source-branch policy must be reviewed separately before publishing from `0.4.x`.

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
git -C takumilib checkout --detach 'takumi@2.17.1^{commit}'
cargo update -w
```

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
- Whether assets referenced by the binding under `takumilib/assets` changed

Upstream's `[patch.crates-io]` forks of fontations and harfrust apply only inside the
Takumi workspace. This crate builds against the crates.io releases, so a patch upstream
adds is not inherited.

!!! danger "The repository checkout is not an sdist dependency"

    Never hide missing distribution files by reading them from the surrounding
    checkout. The CI sdist smoke test must build and run entirely from the isolated
    source archive.
