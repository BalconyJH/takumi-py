# 开发

## 准备环境 { #prepare-the-environment }

```bash
git submodule update --init --recursive
uv sync --all-groups --all-extras
uv run maturin develop
```

Rust 工具链由 `rust-toolchain.toml` 固定。项目的锁文件管理 Python、Rust 和文档依赖；
不要用临时的 `pip install` 命令修补仓库环境。

## 常用检查 { #common-checks }

```bash
make check
make docs-build
prek run --all-files
prek run actionlint --all-files --hook-stage=manual
```

`make check` 运行 Ruff、ty、针对原生扩展的 `mypy.stubtest`、pytest、Rustfmt 和
Clippy。文档构建使用 docs 依赖组，因此单独运行：它先检查中文页面是否与英文源文件保持
镜像，再以严格模式构建两种语言，并把警告视为失败。手动的 Actionlint 阶段在常规仓库钩子
之外，还会校验工作流中内嵌的 shell 脚本。

## 测试 { #tests }

pytest 测试套件位于 `tests/`，通过 `make test` 并行运行：

| 模块 | 覆盖范围 |
| --- | --- |
| `test_render_node.py`、`test_render_html.py`、`test_render_template.py` | 节点、HTML 和模板入口 |
| `test_html_adapter.py`、`test_inline_style.py` | HTML 解析与内联样式 |
| `test_core_binding_features.py` | 选项、字体、图片、缓存、测量、SVG 和动画 |
| `test_takumi_core_fixtures.py` | `takumilib/takumi/tests/fixtures-html` 下的每个上游 HTML 样例都能渲染 |
| `test_examples.py` | `examples/` 中的每个脚本都能运行并写出输出 |
| `test_typing_surface.py` | 文档化的公共 `Renderer` 接口和原生类型文件 |
| `test_repository_scripts.py` | `.github/scripts/` 中的发布、changelog、文档部署与文档翻译脚本 |

## 分发约定 { #distribution-contract }

通过与 CI 相同的本地约定构建当前平台的 wheel 和 sdist：

```bash
make build-artifacts
```

该目标会检查元数据和归档内容，在检出目录之外的临时环境中安装 wheel，从 sdist 重新构建
wheel，并对两条路径运行原生渲染冒烟测试。使用 `make verify-artifacts DIST_DIR=/path/to/dist`
校验已有的本地制品对。

## 原生扩展 { #native-extension }

Python 包从 `python/` 加载，原生模块名为 `takumi_py._core`。修改 Rust 绑定代码后需要
重新构建：

```bash
uv run maturin develop
```

!!! warning "测试绑定改动前先重新构建"

    不重新构建就运行 Python 测试，可能会意外地测到上一次编译留下的过期原生产物。

## Takumi 子模块 { #takumi-submodule }

Takumi 是本仓库显式的源码依赖。请把 `takumilib` 固定到上游 `takumi@X.Y.Z` 标签所指向的
发布提交，绝不要固定到分支末端或本地合并提交：

```bash
git -C takumilib fetch origin --tags
git -C takumilib checkout --detach 'takumi@2.17.1^{commit}'
cargo update -w
```

升级时必须检查：

- 子模块版本和 `Cargo.lock`
- `takumi` 与 `takumi-core` 的版本约束
- 上游 API 中的弃用项：Clippy 以 `-D warnings` 运行，因此调用弃用 API 会导致构建失败。
  采用 `takumilib/takumi-napi` 中 Node 绑定所使用的替代方案，并以 Python
  `DeprecationWarning` 暴露这一变化
- 值得暴露的上游新能力：对比 Node 绑定的接口与 `Renderer`
- 构建是否仍在 `rust-toolchain.toml` 指定的工具链之内：`rust-version` 让依赖解析停留在
  兼容的 crate 上，通过 rustup 运行 `cargo +1.91.0 clippy --locked --all-targets` 可以
  确认这一点
- `tests/test_takumi_core_fixtures.py` 读取的 HTML 样例是否仍位于
  `takumilib/takumi/tests/fixtures-html`
- 源码分发包能否仍在隔离环境中重新构建出 wheel
- 绑定在 `takumilib/assets` 下引用的资源是否发生变化

上游针对 fontations 和 harfrust 的 `[patch.crates-io]` 分叉只在 Takumi 工作区内部生效。
本 crate 基于 crates.io 上的发布版本构建，因此不会继承上游新增的补丁。

!!! danger "仓库检出不是 sdist 的依赖"

    绝不要从外围的检出目录读取文件来掩盖分发包中缺失的文件。CI 的 sdist 冒烟测试必须
    完全基于隔离的源码归档构建并运行。
