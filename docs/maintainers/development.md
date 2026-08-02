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
Rustfmt, and Clippy. The strict documentation build runs separately because it uses
the docs dependency group and treats warnings as failures. The manual Actionlint
stage validates embedded workflow shell scripts in addition to the normal repository
hooks.

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

Takumi is an explicit source dependency of this repository. An upgrade must check:

- The submodule revision and `Cargo.lock`
- Version constraints for `takumi` and `takumi-core`
- Whether the source distribution can still rebuild a wheel in isolation
- Whether assets referenced by the binding under `takumilib/assets` changed

!!! danger "The repository checkout is not an sdist dependency"

    Never hide missing distribution files by reading them from the surrounding
    checkout. The CI sdist smoke test must build and run entirely from the isolated
    source archive.
