# 安装

`takumi-py` 需要 Python 3.10 或更高版本。日常使用请选择已发布的 wheel，开发绑定时请
使用源码检出。

=== "PyPI"

    用 `uv` 把绑定加入项目：

    ```bash
    uv add takumi-py
    ```

    其他符合标准的 Python 包管理器同样可用。已发布 wheel 覆盖的平台见
    [支持矩阵](../reference/support.md)。

=== "源码检出"

    源码构建需要 Rust 1.91 或更高版本、Python 3.10+ 和 `uv`。Takumi 是 Git 子模块，
    因此请递归克隆：

    ```bash
    git clone --recurse-submodules https://github.com/BalconyJH/takumi-py.git
    cd takumi-py
    uv sync --all-groups --all-extras
    uv run maturin develop
    ```

    对于未递归克隆的现有检出，先初始化子模块：

    ```bash
    git submodule update --init --recursive
    ```

## 验证安装 { #verify-the-installation }

```bash
uv run python -c "from takumi_py import Renderer; print(Renderer())"
```

!!! info "自包含的分发包"

    源码分发包（sdist）包含重新构建原生扩展所需的 Takumi 工作区和默认字体源文件。
    已发布的 wheel 把默认字体嵌入扩展，不依赖运行时工作目录中的字体文件。
