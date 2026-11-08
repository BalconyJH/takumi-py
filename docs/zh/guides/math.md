# 数学公式渲染

!!! info "下一主版本预览"

    `takumi_py.math` 是当前代码检出中的下一主版本预览。这些增量 API 不会改变包版本，
    也不改变现有渲染入口。

`MathTypesetter` 把调用方显式提供的 TeX 表达式转换为自包含的 SVG 值。`MathSvg`
携带 SVG 字节、CSS 像素尺寸和有符号的基线深度，可生成图片资源、HTML、节点，或一个
同时拥有节点与图片资源的 `Fragment`。

公式转换与 HTML、Markdown 解析相互独立。包不会扫描文档中的 `$...$`、`\(...\)` 或
`\[...\]` 分隔符；应用需要自己选出表达式，并向排版器传入不带外层 Markdown 分隔符的
TeX。

## 安装 { #install }

在当前源码检出中，公式转换需要安装可选运行时 extra：

```bash
uv sync --extra math
```

当前 PyPI 发布版本不提供这个预览 extra。本地构建的预览 wheel 也接受 `math` extra；
在该 extra 随正式版本发布之前，不要使用 `takumi-py[math]` 从 PyPI 安装。该 extra 会安装
`mini-racer==0.14.1`。

可选运行时的兼容下限比 core 扩展更窄。对于 Linux glibc 目标，数学 extra 使用
MiniRacer wheel 要求 glibc 2.27，而 core wheel 的基线是 glibc 2.17。数学 extra 还提供
musllinux 1.2、macOS Intel 10.9 与 arm64 11、Windows x64 与 arm64 目标。这些只是运行时
wheel 目标，不代表执行验证已经完成；每个平台仍需通过 CI。

固定的 MathJax `4.1.3` 运行时和本地 SVG 字体数据随每个 core wheel 一同分发，即使安装
时没有选择数学 extra 也是如此。这些资源未压缩时约 11.5 MB，对压缩后 wheel 的体积贡献
更小。extra 只安装运行时，不会在首次使用时下载 MathJax 或字体。

## 运行时与进程模型 { #runtime-model }

导入 `takumi_py` 或 `takumi_py.math` 不会启动公式引擎。选择 extra 后，需要显式构造
`MathTypesetter`。构造过程会校验随包 MathJax 资产；第一次未命中缓存的 `typeset` 调用
会启动受监督的 Python worker，并由 worker 导入和校验 MiniRacer 版本。

worker 使用嵌入式 V8 执行固定的本地 MathJax bundle。它不使用 Node.js、浏览器、远程
渲染服务或网络。转换达到 `MathLimits.timeout_ms` 时，父进程会终止 worker 并抛出数学
错误。父进程还需要执行有界的进程终止宽限期，因此调用可能在截止时间之后才返回；该期限
不是绝对毫秒级的硬返回保证。之后的缓存未命中会启动新的 worker，因此可复用运行时不会
保留失控任务。

`typeset` 是同步接口；缓存未命中时，它会阻塞调用线程。异步应用可以安全地构造排版器，
但如果不希望阻塞事件循环，应把转换调用放入 executor。`close()` 释放排版器资源，可重复
调用。排版器生命周期有限时，优先使用上下文管理器。返回的 `MathSvg` 只拥有不可变字节
和几何信息，因此排版器关闭后仍然有效。

## 转换与组合 { #convert-and-compose }

`MathOptions.display=False` 生成行内 TeX。设置 `display=True` 会应用 display 样式，
并使 `MathSvg.to_node()` 和 `to_fragment()` 返回居中的块级容器。`font_size_px`
使用 CSS 像素，`ex_ratio` 设置输入环境的 x-height 比例，`color` 可选 CSS 命名颜色或
十六进制颜色。

推荐的文档路径是 `to_fragment()`。它返回一个 `Fragment`，随后由
`Document.from_node` 插入其中的节点并收集 `ResourceSet`；相同公式资源会自动去重。

```python
from pathlib import Path

from takumi_py import (
    Document,
    LayoutOptions,
    RasterOptions,
    Renderer,
    compile_document,
)
from takumi_py.math import MathOptions, MathTypesetter

with MathTypesetter() as typesetter:
    inline = typesetter.typeset(
        r"E = mc^2",
        options=MathOptions(font_size_px=30, color="#000000"),
    )
    display = typesetter.typeset(
        r"\frac{x^2 + y^2}{a + b}",
        options=MathOptions(display=True, font_size_px=40, color="#000000"),
    )

    document = Document.from_node(
        {
            "type": "container",
            "style": {
                "width": "920px",
                "padding": "64px",
                "backgroundColor": "#ffffff",
                "color": "#000000",
                "fontSize": "30px",
                "lineHeight": "1.5",
            },
            "children": [
                {"type": "text", "text": "Energy and mass: "},
                inline.to_fragment(),
                {"type": "text", "text": " are related."},
                display.to_fragment(),
            ],
        }
    )

compiled = compile_document(document)
layout = LayoutOptions(width=920, height=None)
renderer = Renderer()

png = renderer.render(compiled, layout=layout, output=RasterOptions(scale=2))
measured = renderer.measure(compiled, layout=layout)
svg = renderer.render_svg(compiled, layout=layout)

Path("math.png").write_bytes(png)
Path("math.svg").write_text(svg, encoding="utf-8")
```

行内公式是一个原子图片盒，其 CSS `verticalAlign` 根据 `MathSvg.depth_px` 计算。块级
公式会改变 TeX 样式，并把图片包在居中块容器中。同一个 `CompiledDocument` 随后可以用于
测量、以一个或多个缩放比例栅格化，或输出 SVG，而不需要再次运行公式引擎。

`color=None` 时，生成的填充和描边使用 `currentColor`。Takumi 已通过验证的行内图片颜色
继承路径解析该值。公式必须保持黑色、匹配品牌配色，或在不同宿主之间保留精确缓存键时，
应显式设置 `MathOptions.color`。

## 显式 HTML 资源 { #explicit-html-resources }

`MathSvg.to_html()` 返回一个已转义的 `<img>`，包含显式宽高和行内基线对齐。
`Document.from_html` 不会自动发现该图片资源，因此需要显式传入
`MathSvg.to_image_resource()`：

```python
from takumi_py import (
    Document,
    LayoutOptions,
    Renderer,
    ResourceSet,
    compile_document,
)
from takumi_py.math import MathOptions, MathTypesetter

with MathTypesetter() as typesetter:
    formula = typesetter.typeset(
        r"\int_0^1 x^2\,dx",
        options=MathOptions(font_size_px=32, color="#000000"),
    )

html = '<p class="formula">Integral: ' + formula.to_html(alt="integral") + "</p>"
document = Document.from_html(
    html,
    resources=ResourceSet([formula.to_image_resource()]),
    stylesheets=[
        ".formula { width: 900px; padding: 48px; color: black; background: white; }"
    ],
)
compiled = compile_document(document)

svg = Renderer().render_svg(
    compiled,
    layout=LayoutOptions(width=900, height=None),
)
```

同样两件资源也可以通过现有 HTML API 使用：把资源传给
`Renderer.render_html` 的 `images` 参数。若资源需要与源一起经过编译并用于后续多种
输出，文档路径更合适。

公式资源 ID 是 SVG 字节的 SHA-256 摘要。因此，在文档多个位置复用同一个 `MathSvg`
fragment 时，编译后的文档只会获得一个相同 `ImageResource`。若同一个源对应不同字节，
文档创建资源快照时会抛出 `ResourceError`。

## 批量、限制与生命周期 { #batch-limits-and-lifecycle }

`typeset_many` 保持输入顺序、对完全相同的语义请求去重，并对整个批次应用同一个
`MathOptions`。该操作是全有或全无：任一表达式失败都会抛出 `MathBatchError`，不会返回
部分成功的元组。超过 `MathLimits.max_batch_size` 时会在开始转换前抛出
`MathLimitError`。

`MathLimits` 控制执行和缓存预算。默认值为 5,000 ms 截止时间、worker 内 256 MiB 的 V8
堆上限、65,536 字节输入上限、1,000,000 字节 SVG 上限、1,024 个表达式的批次上限、
128 个缓存条目，以及 UTF-8 TeX 键与 SVG 字节合计 16 MiB 的缓存。该堆上限不限制
worker 进程的总常驻内存。应用输入可信度较低或规模更小时，可收紧这些值。超时和堆预算
还必须落在平台等待时间和原生整数范围内；超出范围时，构造阶段即抛出 `ValueError`。

排版器默认使用内存 LRU 缓存。传入 `cache=False` 可以禁用它；该缓存不会读写磁盘。

```python
from takumi_py.math import MathLimits, MathOptions, MathTypesetter

limits = MathLimits(
    timeout_ms=2_000,
    max_input_bytes=16_384,
    max_batch_size=64,
    cache_entries=32,
)

with MathTypesetter(limits=limits, extensions=("mhchem",)) as typesetter:
    formulas = typesetter.typeset_many(
        (r"E = mc^2", r"\ce{H2O}", r"E = mc^2"),
        options=MathOptions(font_size_px=24, color="#000000"),
    )

# Formula values remain immutable and usable after the worker is closed.
```

扩展在 typesetter 上选择，而不是放在 `MathOptions` 中。首期支持的扩展是 `"mhchem"`；
没有传入 `extensions=("mhchem",)` 时，化学命令不可用。每次转换都从新的 TeX 声明开始，
因此某个表达式定义的宏不会延续到后续调用。

## 语法与支持范围 { #syntax-and-support }

首期数学路径有意面向公式，而不是通用 LaTeX 文档。已验证的子集包括基础 TeX、AMS math
与 align 环境、矩阵与 cases、可伸缩定界符、颜色、`\cancel`、`\bbox`，以及显式启用的
mhchem 化学式。

该路径不承诺完整 LaTeX 包、具有持久状态的任意宏、`\input`、文件访问、网络获取、公式
编号与交叉引用、自动断行、MathML 或 Markdown 公式发现。断行和分页应交给外围布局。

目前不支持 `\text{中文}` 这类 CJK 文本。固定的 path-only 输出策略会拒绝文本节点，而
不是静默依赖宿主上可能不存在的字体。普通 CJK 正文仍需要使用 Takumi 常规字体 API
注册字体。

本地集成已在 macOS arm64 上验证。上列其他目标需要等待 CI 验证；在对应任务通过前，本文
不把这些平台描述为已验证。

## 错误与公共 API { #errors-and-api }

所有数学专用错误都继承自 `MathError`，而 `MathError` 同时继承 `TakumiError`。运行时
打包失败使用 `MathRuntimeUnavailableError`；TeX 语法失败使用 `MathSyntaxError`；不可信
或过大的输入使用 `MathValidationError`；预算失败使用 `MathLimitError`；worker 或引擎
失败使用 `MathRuntimeError`。`MathBatchError` 标识失败批次中的索引，并保留底层原因。

公共模块导出：

```python
from takumi_py.math import (
    MathBatchError,
    MathConverter,
    MathError,
    MathLimitError,
    MathLimits,
    MathOptions,
    MathRuntimeError,
    MathRuntimeUnavailableError,
    MathSvg,
    MathSyntaxError,
    MathTypesetter,
    MathValidationError,
)
```

`MathConverter` 是一个窄协议，供应用提供自定义转换器。它定义
`typeset(tex, *, options=None) -> MathSvg`，不拥有也不启动内建 worker。

## 可运行示例 { #runnable-example }

[`examples/render_math.py`](https://github.com/BalconyJH/takumi-py/blob/main/examples/render_math.py)
使用文档流水线把行内公式与正文、块级分式组合起来，在 `examples/output` 中写入 PNG 和
SVG，并演示如何把 `MathSvg.to_fragment()` 交给 `Document.from_node`。
