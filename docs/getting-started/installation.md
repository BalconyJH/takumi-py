# Installation

`takumi-py` requires Python 3.10 or later. Choose a published wheel for normal use or
a source checkout when developing the binding.

=== "PyPI"

    Add the binding to a project with `uv`:

    ```bash
    uv add takumi-py
    ```

    Other standards-compliant Python package managers also work. See the
    [support matrix](../reference/support.md) for the published wheel platforms.

=== "Source checkout"

    A source build requires a Rust toolchain, Python 3.10+, and `uv`. Takumi is a Git
    submodule, so clone it recursively:

    ```bash
    git clone --recurse-submodules https://github.com/BalconyJH/takumi-py.git
    cd takumi-py
    uv sync --all-groups --all-extras
    uv run maturin develop
    ```

    For an existing non-recursive checkout, initialize the submodule first:

    ```bash
    git submodule update --init --recursive
    ```

## Verify the installation

```bash
uv run python -c "from takumi_py import Renderer; print(Renderer())"
```

!!! info "Self-contained distributions"

    The source distribution contains the Takumi workspace and default font sources
    required to rebuild the native extension. Published wheels embed the default font
    in the extension and do not depend on font files in the runtime working directory.
