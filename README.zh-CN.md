# takumi-py

[English](https://github.com/BalconyJH/takumi-py/blob/main/README.md) | **简体中文**

通过 Python 调用 [Takumi](https://github.com/kane50613/takumi) Rust 渲染器，生成社交分享卡片、
报表等图片。无需浏览器运行时，即可把节点树、HTML 或 Jinja 模板渲染为位图、SVG 和动画。

需要 Python 3.11+。
已发布版本见 [PyPI](https://pypi.org/project/takumi-py/) 和
[GitHub Releases](https://github.com/BalconyJH/takumi-py/releases)。

## 功能

- **三种输入模型**：类型化节点树、由 Rust 解析的 HTML，以及支持自定义过滤器或调用方
  自有环境的 Jinja 模板。
- **静态输出**：PNG、JPEG、WebP、ICO、原始 RGBA 和 SVG；布局测量返回类型化的树。
- **动画**：对 CSS 或结构化关键帧采样、渲染场景序列，或将原始帧编码为 WebP、APNG 和 GIF。
- **字体与图片**：显式提供图片字节，支持原始 RGBA 图片源、字体子集、回退栈和按语言的
  文本整形。
- **复用与缓存**：已编译节点与样式表、带预算的图片和字体缓存，以及可配置的进程级字形
  缓存。
- **Python 类型支持**：提供 PEP 561 类型信息和原生扩展存根。

## 安装

```bash
uv add takumi-py
```

也可以用 pip 安装到现有的 Python 环境：

```bash
python -m pip install takumi-py
```

这些命令安装最新的已发布版本。使用当前源码，请按[开发](#开发)一节操作。

安装兼容的 wheel 不需要 Rust。源码构建需要 Rust 1.91 或更高版本及原生构建工具链，
平台兼容性见[支持矩阵](https://balconyjh.github.io/takumi-py/zh/dev/reference/support/)，
源码构建步骤见[安装指南](https://balconyjh.github.io/takumi-py/zh/dev/getting-started/installation/)。

## 快速上手

将以下代码存为 `render.py`，用 `uv run python render.py` 运行；也可以在已安装本包的环境中
运行 `python render.py`：

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

示例会将一张 1200 × 630 的 PNG 写入 `out.png`。

- 文档级 CSS 通过 `stylesheets` 传入。支持内联 `style` 属性，HTML 中的 `<style>` 元素会被
  忽略。
- 内置的 Geist 回退字体覆盖拉丁文字。中文、日文、韩文、emoji 和其他文字需要注册合适的
  字体。
- 渲染器从不通过网络抓取资源。请通过 `images` 提供图片字节，并在渲染器上注册字体。

资源配置见[字体与图片](https://balconyjh.github.io/takumi-py/zh/dev/guides/resources/)。
[`examples/`](https://github.com/BalconyJH/takumi-py/tree/main/examples) 提供节点、HTML、模板、
资源、测量和动画的可运行脚本。

## 文档

以下链接指向从 `main` 构建的 `dev` 文档，另有
[英文版](https://balconyjh.github.io/takumi-py/dev/)。其中可能包含尚未发布到 PyPI 的变更。
使用已发布的包时，请在[文档站点](https://balconyjh.github.io/takumi-py/)选择对应版本。

| 任务 | 文档 |
| --- | --- |
| 渲染第一张图片 | [快速上手](https://balconyjh.github.io/takumi-py/zh/dev/getting-started/quickstart/) |
| 选择输入和输出 | [渲染模型](https://balconyjh.github.io/takumi-py/zh/dev/guides/rendering/)、[HTML 与 CSS](https://balconyjh.github.io/takumi-py/zh/dev/guides/html/)、[输出格式](https://balconyjh.github.io/takumi-py/zh/dev/guides/output/) |
| 渲染动态内容 | [Jinja 模板](https://balconyjh.github.io/takumi-py/zh/dev/guides/templates/)、[动画](https://balconyjh.github.io/takumi-py/zh/dev/guides/animation/) |
| 查询签名和行为 | [API 参考](https://balconyjh.github.io/takumi-py/zh/dev/reference/)、[异常](https://balconyjh.github.io/takumi-py/zh/dev/reference/exceptions/) |
| 确认兼容性与 API 策略 | [支持矩阵](https://balconyjh.github.io/takumi-py/zh/dev/reference/support/) |

文档源文件位于 [`docs/`](https://github.com/BalconyJH/takumi-py/tree/main/docs)。英文为权威
来源，中文逐页同步，代码示例保持一致。

## 升级到 0.4.0

- 需要 Python 3.11+，移除 Python 3.10 支持。
- 将自 0.2.0 起弃用的资源 API 替换为单次渲染的 `images` 和
  `register_font` / `register_fonts`。
- 从 Takumi 2.5 升级到 2.17 时，检查字体子集、抖动、动画帧率限制和渲染结果变化。

请按 [Takumi v2 迁移指南](https://balconyjh.github.io/takumi-py/zh/dev/migration/takumi-v2/)
和 [Takumi 2.17 迁移指南](https://balconyjh.github.io/takumi-py/zh/dev/migration/takumi-2.17/)
完成升级，并阅读[变更日志](https://github.com/BalconyJH/takumi-py/blob/main/CHANGELOG.md)。

## 开发

安装 `uv` 和 Rust，然后连同 Takumi 子模块一起克隆仓库：

```bash
git clone --recurse-submodules https://github.com/BalconyJH/takumi-py.git
cd takumi-py
make sync
make check
make docs-build
```

`make check` 会运行代码规范检查、类型检查、Python 测试和 Rust 检查，并为运行时检查重新
构建原生扩展。使用 `make docs-serve` 或 `make docs-serve-zh` 可在本地预览文档。
[开发指南](https://balconyjh.github.io/takumi-py/zh/dev/maintainers/development/)介绍检查和
Takumi 升级，[发布指南](https://balconyjh.github.io/takumi-py/zh/dev/maintainers/releasing/)
介绍自动化发布流水线。

## 许可证

`takumi-py` 以 GPL-3.0-or-later 授权，见
[LICENSE](https://github.com/BalconyJH/takumi-py/blob/main/LICENSE)。

本仓库以 git 子模块的形式包含 `takumi`。`takumi` 单独以 `MIT OR Apache-2.0` 授权，见
[THIRD_PARTY_NOTICES.md](https://github.com/BalconyJH/takumi-py/blob/main/THIRD_PARTY_NOTICES.md)。
