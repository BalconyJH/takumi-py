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

检查工具均已固定版本，因此只有仓库本身变化时结果才会变化：Prek hook 由 `prek.toml` 中的
`rev` 固定，仍处于 0.0.x 的 ty 在 `dev` 依赖组中固定为一个确切版本。升级 ty 时，提高其固定
版本，并在同一提交中修复 `make typecheck` 报告的问题；Ruff hook 的 `rev` 与锁定的 Ruff 版本
需保持一致。

## 测试 { #tests }

`pytest` 测试套件位于 `tests/`。Ubuntu quality job 通过 `make test` 并行运行完整套件；
安装包可移植性矩阵运行下文所述的较小回归选择。

| 模块 | 覆盖范围 |
| --- | --- |
| `test_render_node.py`、`test_render_html.py`、`test_render_template.py` | 节点、HTML 和模板入口 |
| `test_document.py`、`test_document_rendering.py` | Document 与 fragment 所有权、编译、布局、画布尺寸和 SVG/raster 输出 |
| `test_html_adapter.py`、`test_inline_style.py` | HTML 解析与内联样式 |
| `test_native_compile.py`、`test_stylesheet_composition.py`、`test_keyframe_options.py`、`test_render_needs.py` | 独立编译器函数、CSS 合并、关键帧、渲染选项和资源需求 |
| `test_core_binding_features.py` | 选项、字体、图片、缓存、测量、SVG 和动画 |
| `test_node_bytes.py`、`test_raster.py` | 缓冲节点数据、原生解码限制、位图所有权和图片编码 |
| `test_native_stack.py` | 小线程栈下的全深度原生与 CSS 管线、边界错误和子进程阶段诊断 |
| `test_takumi_core_fixtures.py` | `takumilib/takumi/tests/fixtures-html` 下的每个上游 HTML 样例都能渲染 |
| `test_examples.py` | `examples/` 中的每个脚本都能运行并写出输出 |
| `test_math.py`、`test_math_validation.py`、`test_math_process.py`、`test_math_layout.py`、`test_math_integration.py` | MathJax 输出、SVG 与 TeX 校验、工作进程崩溃和截止时间、布局以及下游渲染 |
| `test_typing_surface.py` | 文档化的公共 `Renderer` 接口和原生类型文件 |
| `test_repository_scripts.py` | `.github/scripts/` 中的发布、changelog、文档部署与文档翻译脚本 |

## CI 矩阵 { #ci-matrix }

本节描述工作流配置，并不表示每个矩阵单元都已成功完成。`quality` job 只在 Ubuntu 上运行完整
`pytest` 套件。可移植性覆盖来自 `wheel-smoke` job：它配置了八个目标和 `debug`、`release` 两种
构建配置，共 16 个 wheel 与回归测试单元。八个目标是 Linux x86_64 与 aarch64、musllinux
x86_64 与 aarch64、macOS x86_64 与 aarch64，以及 Windows x64 与 arm64。

每个单元都会构建自己的 wheel，并针对安装后的制品运行 11 个选定的测试模块。
`test-wheel.py` 会把这些模块从 runner 检出目录复制到仓库之外的临时目录，创建全新的虚拟
环境，并安装带 math extra 的 wheel。探针会确认 `takumi_py`、其原生扩展和
`py_mini_racer` 都从该环境加载。只要任何选定测试被跳过，JUnit 报告就会让 job 失败，
因此缺少 math runtime 不会产生虚假通过。

可移植性选择包含以下 native、node 与 CSS 模块：

- `test_native_stack.py`
- `test_node_bytes.py`
- `test_native_compile.py`
- `test_stylesheet_composition.py`
- `test_keyframe_options.py`
- `test_render_node.py`

它还包含以下数学模块：

- `test_math.py`
- `test_math_validation.py`
- `test_math_process.py`
- `test_math_layout.py`
- `test_math_integration.py`

### CI 执行顺序 { #ci-execution-order }

六个 workflow 文件保持平铺：没有任何一个通过 reusable workflow 或 composite action
调用另一个 workflow。`ci.yml` 内部的 job 顺序如下：

```text
quality ---------------------------------------------------------+
  |                                                              |
  +--> sdist-smoke ----------------------------------------------+
  |                                                              +--> result
  `--> wheel-smoke [8 platforms x 2 profiles] -------------------+
         `--> abi3-smoke [Python 3.11..3.15] --------------------+
```

`quality` 是这两条构建分支的前置门禁，随后 `sdist-smoke` 与 `wheel-smoke` 并行。`wheel-smoke`
包含 16 个矩阵单元；只有其中八个 `release` 单元上传 `ci-wheel-*` wheel，两种配置都会保留
各自的 `ci-regressions-*` 结果。矩阵依赖使 `abi3-smoke` 等待全部单元完成，再用 Python
3.11 至 3.15 检查 Linux x86_64 release wheel。`result` 直接读取 `quality`、
`sdist-smoke`、`wheel-smoke` 与 `abi3-smoke` 这四层 job 结果；这些直接 `needs` 使它成为
真正的四层 Required checks。它会写出四层状态摘要表，任一层失败、取消或跳过都会使
Required checks 失败。

在 workflow 层面，可信的 `main` 推送有一条精确 SHA 协调路径和一条独立预览路径：

```text
Check - Build and test ---+
Check - Docs -------------+--> exact-SHA join --> Release - Tag --> Publish
Check - Lint -------------+

Check - Docs --> Preview - Docs --> gh-pages --> Pages
```

三个 `workflow_run` 各自完成时，都会重新通过 GitHub API 查询 `main` 上三个 push run，
并要求三者的成功 `head_sha` 都等于标签源 SHA，因此最先结束的检查不能提前创建标签。
预览走自己独立的 `workflow_run` 分支，不等待 CI、打标签或发布。发布与预览的 Pages job
共用 `github-pages` 并发组；该锁只串行部署，不构成 `needs` 依赖。打标签后的发布 job
见[自动发布链路](releasing.md#automatic-release-pipeline)。

把恰好一个当前平台的 wheel 构建到 `dist/` 后，从仓库根目录重现选定的安装包测试套件：

```bash
python .github/scripts/test-wheel.py dist --python 3.11 --uv uv --junit-xml reports/regressions.xml
```

该命令会创建自己的临时环境，并在 `reports/` 下同时写入 JUnit 报告和对应的 pytest 日志。

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
git -C takumilib checkout --detach 'takumi@2.20.0^{commit}'
cargo update -w
```

当前下一主版本的静态渲染预览遵循 Takumi 2.20 的规范 API：crate 根部的 `render`、
`measure`、`render_svg` 和 `needs`，场景复用仍作为同线程内部的实现细节。Python 接口
保留完成的位图，不暴露不稳定的 `Scene`。HTML 资源遵循正式发布的 `parse_html` 契约：
节点与 `<style>` CSS 分开返回，渲染器方法返回级联感知的 `RenderNeeds`，应用显式提供
`@font-face` 字节。

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
- 绑定在 `takumilib/assets` 下引用的资源是否发生变化。2.20 绑定会内嵌
  `geist-latin-wght-300-800.ttf` 和 `geist-latin-wght-300-800.woff2`，因此两者都必须
  保留在源码分发包中。
- 新增 crate 或内置源码是否改变许可证清单。Cargo 源码包目前会携带
  `takumi-core/LICENSE-CHROMIUM`、`LICENSE-EMOJI-SEGMENTER` 和 `LICENSE-ICU`；
  它们已列入 `[project].license-files`，因此每个 sdist 和 wheel 都会携带通知，并在包
  元数据中记录这些路径。

上游针对 fontations 和 harfrust 的 `[patch.crates-io]` 分叉只在 Takumi 工作区内部生效。
本 crate 基于 crates.io 上的发布版本构建，因此不会继承上游新增的补丁。

!!! danger "仓库检出不是 sdist 的依赖"

    绝不要从外围的检出目录读取文件来掩盖分发包中缺失的文件。CI 的 sdist 冒烟测试必须
    完全基于隔离的源码归档构建并运行。
