# takumi-py

[English](https://github.com/BalconyJH/takumi-py/blob/main/README.md) | **简体中文**

[Takumi](https://github.com/kane50613/takumi) Rust 渲染器的 Python 3.11+ 绑定。无需浏览器
运行时，即可把节点树、HTML 和 Jinja 模板渲染为 PNG、JPEG、WebP、ICO、原始 RGBA、SVG，以及
WebP、APNG 或 GIF 动画。

> [!IMPORTANT]
> `takumi-py` 处于测试阶段。在 Takumi 核心绑定接口补全之前，API、wheel 构建目标、发布
> 自动化和异常类型仍可能变化，请暂时不要把它当作稳定的生产依赖。

## 文档

文档站点为 [balconyjh.github.io/takumi-py/zh](https://balconyjh.github.io/takumi-py/zh/)，
另有[英文版](https://balconyjh.github.io/takumi-py/)，由
[`docs/`](https://github.com/BalconyJH/takumi-py/tree/main/docs) 构建。最新发布版本的文档：

- [快速上手](https://balconyjh.github.io/takumi-py/zh/latest/getting-started/quickstart/)
- [指南](https://balconyjh.github.io/takumi-py/zh/latest/guides/)：渲染
  模型、HTML 与 CSS、输出格式、字体与图片、Jinja 模板和动画
- [支持矩阵](https://balconyjh.github.io/takumi-py/zh/latest/reference/support/)
  与[异常](https://balconyjh.github.io/takumi-py/zh/latest/reference/exceptions/)
- [Takumi v2](https://balconyjh.github.io/takumi-py/zh/latest/migration/takumi-v2/)
  与 [Takumi 2.17](https://balconyjh.github.io/takumi-py/zh/latest/migration/takumi-2.17/)
  的迁移指南

英文文档是权威来源，中文文档逐页与其保持同步。

## 安装

```bash
uv add takumi-py
```

已发布的 `cp311-abi3` wheel 覆盖 glibc 与 musl（Alpine）上的 Linux x86_64 与 aarch64、
Apple Silicon 与 Intel 上的 macOS，以及 Windows x64 与 arm64。其他平台从源码分发包构建，
需要 Rust 1.91 或更高版本。源码检出方式见
[安装](https://balconyjh.github.io/takumi-py/zh/latest/getting-started/installation/)。

## 快速上手

```python
from pathlib import Path

from takumi_py import Renderer

png = Renderer().render_html(
    '<main class="card">Hello from Python</main>',
    stylesheets=[
        """
        .card {
          width: 1200px;
          height: 630px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          background: #111827;
          font-size: 72px;
        }
        """
    ],
    width=1200,
    height=630,
)

Path("out.png").write_bytes(png)
```

覆盖每种输入与输出的可运行脚本位于
[`examples/`](https://github.com/BalconyJH/takumi-py/tree/main/examples)。

## 功能

- 节点树、由 Takumi Rust 解析器解析的 HTML，以及支持自定义过滤器或调用方自有环境的
  Jinja 模板。
- 带编码器选项、设备像素比、抖动和原始 RGBA 的位图输出；SVG 输出；以类型化树表示的布局
  测量。
- 调用方提供的字体（支持 `unicode-range` 子集）、按次传入的图片、原始 RGBA 图片源、字体
  回退栈以及按语言的文本整形。
- CSS 与结构化关键帧采样，以及 WebP、APNG 和 GIF 动画编码。
- 渲染器级的资源缓存与进程级的字形缓存预算。
- PEP 561 类型支持，`_core.pyi` 覆盖原生扩展。

绑定保持资源归属清晰：它从不通过网络抓取资源，也不提供 Playwright 回退、中止信号协议、
data URL 辅助函数或 Node.js 旁路进程。全部排除项见
[支持矩阵](https://balconyjh.github.io/takumi-py/zh/latest/reference/support/)。

## 开发

```bash
git clone --recurse-submodules https://github.com/BalconyJH/takumi-py.git
cd takumi-py
uv sync --all-groups --all-extras
uv run maturin develop
make check
```

[开发指南](https://balconyjh.github.io/takumi-py/zh/latest/maintainers/development/)
介绍检查、测试和 Takumi 升级，[发布指南](https://balconyjh.github.io/takumi-py/zh/latest/maintainers/releasing/)
介绍自动化发布流水线。

## 许可证

`takumi-py` 以 GPL-3.0-or-later 授权，见
[LICENSE](https://github.com/BalconyJH/takumi-py/blob/main/LICENSE)。

本仓库以 git 子模块的形式包含 `takumi`。`takumi` 单独以 `MIT OR Apache-2.0` 授权，见
[THIRD_PARTY_NOTICES.md](https://github.com/BalconyJH/takumi-py/blob/main/THIRD_PARTY_NOTICES.md)。
