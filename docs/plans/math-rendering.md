# takumi-py 公式渲染实现计划

状态：当前代码检出已实现，作为下一大版本预览验收。本方案已经转向 [整体 binding 架构](binding-next.md)，不再以“不扩展 Renderer、每次手动传 images”为设计约束。静态公式契约、可选 MathJax 引擎与分发验证分别验收；发布版本与平台支持以正式门禁结果为准。

日期：2026-11-08。目标项目为 `takumi-py`；公式引擎不放在 Entari 或其他机器人框架插件中。

2026-11-09 补充：整体静态管线已升级到正式 `takumi@2.20.0` / `takumi-core 0.36.0`
（`ae2a35011e5cddedb0a4c8b33ab0c9242ca76b2d`）。以下基线表记录最初审查状态；
当前架构加入可保留的 `RasterImage`、原生资源快照、`needs()`、HTML `<style>` 提取与
`@font-face` 文件加载，详见 [binding 架构](binding-next.md)。MathJax bundle 保持不变；
SVG 后端现在可将公式展开为宿主路径，测量按上游 1/64 px 布局单位量化。

## 1. 目标与基线

为 Python 调用方提供显式的 TeX 公式预排版能力，输出带尺寸与基线信息的静态 SVG，再复用 Takumi 的图片、布局、测量和输出管线。运行时不需要浏览器，不依赖 NoneBot、Entari 或 Markdown 解析器。

| 项目 | 本次核查结果 |
| --- | --- |
| Python 仓库 | `main@80ca0ddb37d3244d59288378f9c2f5cad9226623` |
| 项目版本 | `takumi-py 0.4.0`，Python 3.11+ |
| Rust 依赖 | `takumi 2.17.1`、`takumi-core 0.32.0` |
| 原生子模块 | `takumilib@7ddc5c2b7467020144750945ed85625b3137557d` |
| 补充上游审查 | Takumi `master@346ecd69e6a61be9481ce8313cc3edd2f05eac4b`，2026-11-08 |
| 可复用接口 | `ImageResource`、`ImageNode`、HTML `<img>`、compiled node、measure 和 raster/SVG 输出 |
| 需要补齐 | TeX 到 SVG、尺寸与基线归一化、可选引擎运行时、缓存及分发 |

当前及核查到的最新原生上游均没有 TeX 排版器，也没有 MathML 的分式、根式、伸缩符号等专门布局。最新 HTML parser 识别 MathML 命名空间，后续仍将这些元素转为普通文本和容器。`font-family: math`、CSS 数学函数和 SVG 数学基线不能替代公式排版；`render_svg_*` 是输出接口。

当前[支持矩阵](../en/reference/support.md)明确排除 Node.js sidecar。普通 `import takumi_py` 和文档编译/渲染保持这一边界，不自动启动 JavaScript 引擎、查找 Node 或访问网络。下一大版本允许重构 Python/Rust binding；当前保留旧入口兼容性，不自动修改发布版本或升级子模块。

## 2. 方案选择

采用 **MathJax SVG 预排版 + 资源随文档持有 + Takumi 布局与输出**。新增独立、可选的 `takumi_py.math` 模块；公式输出通用 `Fragment`，由 `Document` 组合并编译为 `CompiledDocument`。不增加原生 `NodeKind::Math`，不在 HTML 渲染中隐式识别 `$...$` 或执行脚本。

```text
TeX + MathOptions
        |
        v
MathTypesetter -> Python worker [MiniRacer + local MathJax bundle]
        |
        v
MathSvg [SVG bytes + CSS-px size + signed depth]
        |
        +--> Fragment [node + ResourceSet]
        |             |
        |             v
        |       Document.from_node
        |
        +--> HTML <img> + ResourceSet --> Document.from_html
                            |
                            v
                     compile_document
                            |
                            v
                     CompiledDocument
                            |
                            v
            Renderer + LayoutOptions (CSS px)
                    /       |       \
                   v        v        v
                measure   raster     SVG
                            |
                      RasterOptions
```

| 路线 | 取舍 |
| --- | --- |
| MathJax SVG + 嵌入式 JS | 当前实现；公式图形与宿主布局解耦，固定本地 bundle 由受监督的 Python worker 执行，Promise 失控由进程级 deadline 回收 |
| MathJax SVG + Node sidecar | 可由应用自管；本包不默认采用，不隐式突破现有支持策略 |
| KaTeX 服务端 HTML/CSS | KaTeX 常规输出为 HTML/MathML，不直接输出 SVG；其 CSS 与字体布局需要另行验证，本计划不采用 |
| 直接渲染 MathML | 原生上游缺数学布局，升级 Python binding 不足以完成 |
| Rust 自写 TeX/MathML 引擎 | 工作量与维护面过大，应作为原生上游的独立项目 |
| 浏览器先生成图片 | 不满足本项目无浏览器运行时的目标 |

P0 当前实现选择 MathJax 4.1.3、NewCM 4.1.3 与 MiniRacer 0.14.1。macOS arm64 已验证嵌入式执行、Promise、直接 CPU 中断和 V8 硬内存限制；Promise 回调死循环存在超时缺口，使用父进程监督的 Python worker 兜底回收。其他平台的 wheel 可用性不等于运行验收。构建阶段使用锁定 Bun 入口，运行阶段不需要 Node。运行契约与限制见 [公式渲染指南](../en/guides/math.md)，本地执行证据与平台边界见 [P0 运行时报告](math-runtime-p0.md)，进程监督回归见 [test_math_process.py](../../tests/test_math_process.py)。

若 P0 无法满足嵌入式执行要求，应记录阻碍并重新评估引擎，或先交付静态 `MathSvg` 与外部转换器协议。后一种交付只能称为“静态公式资源接入”，不能宣称已完成内建 TeX 支持；禁止静默回退到 Node、浏览器或在线服务。

## 3. 首期支持范围

首期支持显式的单公式和批量排版，覆盖分式、上下标、根式、积分、求和、矩阵、分段函数、伸缩括号及选定的 AMS 环境，提供行内和块级模式。mhchem 作为显式启用的固定扩展，覆盖化学式与反应式。

调用方传入不带 Markdown 外层分隔符的 TeX，例如 `r"\frac{a}{b}"`。Markdown 分隔符、代码块排除、HTML 遍历和模板生命周期由调用方负责；本模块不添加 Markdown 解析器，也不扫描任意文档。

首期不承诺完整 LaTeX 文档、任意宏包、磁盘 `\input`、网络资源、跨公式编号与 `\label`/`\ref`、自动跨行断式、任意字体或 HTML 注入命令。不支持的语法返回明确错误，不生成看似成功的错误图像。

## 4. Python API 契约

API 从 `takumi_py.math` 显式导入，采用同步调用风格。业务框架自行将任务放入线程或进程工作池。下一版 `Renderer` 增加接收文档的 `render`、`measure`、`render_svg`，由各输入适配器共用，不为公式新增专用渲染方法。

| 类型或方法 | 职责 |
| --- | --- |
| `MathOptions` | 单公式选项：`display`、`font_size_px`、`ex_ratio`、显式前景 `color` |
| `MathConverter` | 窄转换协议，约定 `typeset(tex, *, options=None) -> MathSvg`，允许应用提供转换器 |
| `MathTypesetter` | 显式创建、持有并关闭排版引擎，拥有资源预算和缓存 |
| `typeset(tex, *, options=None)` | 裸 TeX 转为不可变 `MathSvg` |
| `typeset_many(expressions, *, options=None)` | 同一组选项的批量排版，保持顺序并去重 |
| `MathSvg` | 不依赖引擎生命周期的纯值：SVG bytes、CSS px 尺寸、基线深度 |
| `MathSvg.to_image_resource()` | 返回现有 `ImageResource`，使用确定性的内容摘要作为资源 ID |
| `MathSvg.to_html(*, alt="")` | 生成已转义的 `<img>`；行内设置基线偏移，块级使用居中 wrapper |
| `MathSvg.to_node()` | 返回现有 `ImageNode` 或块级 `ContainerNode`，`src` 与 `to_image_resource()` 使用同一 ID |
| `MathSvg.to_fragment()` | 返回通用 `Fragment`，同时携带节点和 `ResourceSet`，供文档自动组合 |
| `MathTypesetter.close()` / 上下文管理 | 取消进行中的转换并释放 worker 进程与缓存；关闭后拒绝新调用 |

当前结果模型的关键字段：

```python
@dataclass(frozen=True, slots=True)
class MathSvg:
    data: bytes
    width_px: float
    height_px: float
    depth_px: float
    display: bool
```

单位统一为 CSS px。`depth_px` 表示图像底边低于公式基线的正向距离；从顶部计算的基线位置为 `height_px - depth_px`。是否需要负深度等边界应通过真实结果确认，不裁剪有效几何量。SVG `viewBox` 的 user units 不直接等同 CSS px。

当前用法：

```python
from takumi_py import Renderer
from takumi_py.math import MathOptions, MathTypesetter

with MathTypesetter() as typesetter:
    formula = typesetter.typeset(
        r"\frac{a}{b} + \sqrt{x}",
        options=MathOptions(display=False, font_size_px=20),
    )

html = "<p>Result: " + formula.to_html(alt="a/b + sqrt(x)") + "</p>"
png = Renderer().render_html(
    html,
    images=[formula.to_image_resource()],
    width=640,
    height=None,
)
```

`MathSvg` 在排版器关闭后仍有效。推荐通过 `to_fragment()` 与 `Document.from_node()` 组合，或将 `to_html()` 和图片资源交给 `Document.from_html(resources=...)`。`CompiledDocument` 显式持有这些资源，后续三个文档输出方法不必重复传 `images=`。旧 `compile_html()` 和旧 compiled 方法维持原契约。文档持有资源与隐藏的全局图片注册表不同。

`MathTypesetter` 实现 `MathConverter` 协议；协议不负责加载或启动外部进程。若内建引擎的 P0 验证失败，应用可自行实现该协议，包内静态资源接口仍可独立使用。

当前错误定义在 `python/takumi_py/math/errors.py`。`MathError` 继承 `TakumiError`；运行时缺失、TeX 语法、预算、输入/SVG 校验及 worker 失败分别使用 `MathRuntimeUnavailableError`、`MathSyntaxError`、`MathLimitError`、`MathValidationError` 和 `MathRuntimeError`。`MathBatchError` 包含输入索引并保留底层原因，批量转换采用整体失败，不返回半个成功列表。

## 5. 引擎、分发与生命周期

### P0 可行性门槛

从 MathJax 的 TeX input、SVG output、轻量 adaptor 和选定扩展构建专用 bundle，在不提供浏览器 DOM、Node `require`、文件系统或网络接口的候选引擎中证明：

1. 基础公式、AMS、矩阵和 mhchem 可输出完整 SVG。
2. MathJax 4 的字体数据、扩展及异步加载全部本地化，新字符不会触发 CDN 请求。
3. `Promise`、microtask 和异步字体加载被正确驱动，完成信号涵盖所有排版工作。
4. 长计算能被真正中断，具备内存与栈预算；不是只在调用前后检查时间。
5. macOS、Linux glibc/musl、Windows 存在可分发的运行时，或明确记录 math extra 的较窄支持矩阵。
6. 多请求之间不泄漏宏、公式编号和未完成的异步任务；只读字体数据可复用，加载失败不能污染下一请求。

现成的 Node 入口和浏览器 bundle 均不能直接视为嵌入式引擎输入：前者可能依赖 `process`、`path` 和动态模块加载，后者可能要求 `window`/`document`。P0 应从 LiteDOM/adaptor 和源模块构建专用入口，比较 `tex-svg-nofont` 加固定字体 chunk 与 combined bundle，记录真实依赖闭包。字体、扩展通过固定的本地模块表注册，不向运行时补齐通用 Node 或网络接口。

MiniRacer 0.14.1 的 Linux glibc wheel 使用 `manylinux_2_27`，所以 `[math]` 的 glibc 最低版本是 2.27，高于 core 的 2.17；不能把架构覆盖描述为运行时支持完全一致。

平台报告逐项列出当前八个 wheel 目标：Linux glibc/musl 的 x86_64 与 aarch64、macOS Intel 与 Apple Silicon、Windows x64 与 arm64。候选 JS 包在 macOS Intel、Windows arm64 等目标上的 wheel 可用性须单独核实；缺口可以导致明确收窄实验性 extra 的范围，但不能宣称与 core 全平台同等支持。

P0 交付可重复实验、依赖锁、输出样本及结论。“运行机器只装 Python 即可”的承诺由隔离安装测试证明，不能根据本机构建成功推断。

### 打包与加载

- `[math]` extra 固定 `mini-racer==0.14.1`；核心导入不加载运行时。bundle 暂随主 wheel 分发，因此 extra 不减少 core 下载的资源体积。独立引擎发行包延后，以实际大小、维护成本决定是否拆包。
- 固定 MathJax、字体、扩展和构建工具版本，提交构建入口、锁文件、资源清单及 SHA-256。按选定 4.x 版本核对实际 npm 包名，不混用 3.x 示例。
- JS/字体数据随 wheel 和 sdist 分发，通过 `importlib.resources` 读取。禁止首次调用时执行 `npm install`、`npx`、下载字体或调用远端公式服务。
- TeX 通过结构化参数传给固定 JS 入口，不拼接为代码；不接受调用方提供任意 JS callback、模块路径和动态 loader。
- core 导入和静态结果使用不加载可选运行时；构造排版器只验证随包 bundle，缺 `mini-racer` 或版本不匹配在第一次未命中缓存的 `typeset()` 启动 worker 时报告。
- 分别核实 MathJax 与字体许可，更新 `THIRD_PARTY_NOTICES.md`、`LICENSES/` 和分发清单。

当前[分发检查](../../.github/scripts/check-distributions.py)要求 `.ttf`、`.woff2`、`.ttc` 字体内嵌于扩展，并严格比对许可文件集合。SVG 字形路径的 JS 数据也须纳入资源清单、哈希和许可审计；不能因后缀不在检查范围就视作已符合分发规则。若需要新增字体二进制，先明确调整分发契约及检查，再纳入制品。

### 生命周期和并发

每个 `MathTypesetter` 持有自己的 `ProcessRuntime`，不使用进程级隐式单例。第一次未命中缓存的转换会启动受监督的 Python worker；排版器事务锁串行化调用，调用方可从不同线程进入，但实际 JS 执行不会并发。`close()` 通过独立状态锁终止在途 worker，重复关闭安全；故障 worker 不回到可复用状态。

调用拥有真实执行预算。超时或运行时故障后销毁/重建 context，不将可能损坏的对象放回池。测试在途关闭、重复关闭、关闭后调用和资源释放。同步排版的执行中断不意味着整个 `Renderer` 新增异步取消协议。

父进程为 bundle 启动、JS 执行和异步任务统一施加墙钟 deadline。到期的 worker 会先 terminate、再有界等待并用 kill 兜底回收，因此调用方返回超时后不会留下继续无限运行的后台任务。这个进程级监督覆盖 MiniRacer 自身无法中断 Promise 回调死循环的缺口。

进程创建本身也计入期限：最多一个后台启动尝试，取消后迟到的进程立即回收，重试期间
不累积启动线程。操作系统中阻塞的 `Popen` 调用不能被强行结束；该单个后台线程可能
稍晚退出，但调用方等待和 `close()` 均有明确边界。`max_nesting_depth` 默认且最多
128，先检查源代码中的分组、环境和成对定界符，忽略注释、转义与 `\verb`；这是输入
预算，宏展开仍通过 worker 的时间与内存限制隔离。

## 6. SVG、尺寸与基线

### 自包含 SVG

当前实现使用 MathJax SVG output 的 `fontCache: "none"`，让字形路径进入每个公式，不依赖其他公式或页面级全局字体缓存。严格验证器的实际元素白名单是 `svg`、`g`、`path`、`rect` 和 `line`；`use`、`defs` 与 `style` 不在当前接受范围内。

空格字形允许带合法 `data-c` 的空 `d`，使命名运算符和含空格文本保持有效。bbox 的
polygon 在桥接层转换为 path，array 的描边类转换为明确属性，再移除已识别的 MathJax
元数据。任意原始 `style`、URL 与无来源标记的空 path 仍然拒绝。

验证 SVG 根、有效 `viewBox`、有限坐标及数值尺寸。拒绝脚本、事件属性、外部 URL、`foreignObject`、外部字体、XML 外部实体和超预算的树；引擎 safe 配置与输出检查共同使用，不能把 safe 扩展当作完整沙箱，并显式限制 `\href`、`\style`、`\class` 等命令。

优先输出字形路径，减少系统字体差异。对 `\text{中文}` 等超出数学字体覆盖范围的内容单独验证；若无法完整路径化，明确报告支持边界，不依赖开发机字体悄悄补齐。

当前 Takumi 已在 raster 与 SVG 两条路径实现图片 `currentColor` 的宿主颜色注入，并按颜色区分 raster 缓存；同资源红/蓝混用的运行探针通过。公式允许保留 `currentColor`，也允许显式设置颜色；显式选项与输出策略进入排版缓存键，同时保留允许的 TeX 局部颜色。导出的独立原始 SVG 脱离 Takumi 后不保证继承任意外层页面颜色。首期 `fontCache: none` 避免 ID 引用，静态结果验证使用 `g`/`path`/`rect`/`line` 路径图形子集。

### 尺寸归一化

MathJax 常见输出含 `ex` 尺寸及负的 `vertical-align`，不能原样塞进当前 Takumi HTML 的 CSS。适配层需要：

- 实际读取 `svgJax.getBBox()` 的 `w/h/d`，将 em 几何乘一次显式字号得到 CSS px。
- 使用显式 `font_size_px`；`ex_ratio` 描述输入环境的 x-height/em。0.5 可以作为实验默认值，但须明确记录并允许覆盖，不能当作所有字体的事实。
- 为图片输出明确的宽高，并由 BBox 重建 `viewBox`；最小盒为固定 `0.001 em`。
  不能直接复用 MathJax 随输入 em 增大的最小 SVG 盒，否则 1000/2000 px 等大字号
  会产生二次缩放。计算后的 f32 溢出抛出 `MathLimitError`。
- 公式尺寸始终为 CSS px，不预乘 DPR。新文档 API 通过 `RasterOptions.scale` 在适配层缩放 viewport，并把倍率交给原生长度解析；它也影响原生布局，而非纯绘制后处理。`measure(document)` 固定 DPR=1，SVG 同样使用 CSS 单位。旧测量接口仍可能返回 device px。
- 首期不自动解析父元素的继承字号；字号变化后重新排版，或使用经过验证的显式等比缩放。

### 行内与块级布局

行内公式是原子图片盒。若图片底边默认落在正文基线上，则使用 `vertical-align: -depth_px`；通过真实正文、上下标和分式验证偏移方向、行高、换行和裁剪。不能只检查“成功生成 PNG”。

`to_html()` 和 `to_node()` 采用相同的基线语义；节点路径使用现有 `style={"verticalAlign": f"{-depth_px}px"}`，同时显式声明行内 display、宽高，避免常见图片 reset 改变公式盒。块级 `to_node()` 返回带块级、居中样式的 `ContainerNode`，不把行内偏移错误应用于外层容器。

块级公式使用块容器居中，`display=True` 同时改变 TeX display style。超宽公式首期遵循显式尺寸及宿主 overflow 策略，不自动缩小或断式。

如果当前原生接口确实缺少必要基线能力，只增加最小、可上游化的通用图片基线绑定，并同步 Rust/stub/测量测试；不预设必须改 Rust，也不通过公式专用 tag 或 magic offset 绕过。

## 7. 状态、预算与缓存

默认每个公式独立。自定义宏若支持，只接受有界的声明映射，每次请求恢复初始状态，避免 `\def` 污染后续调用。关闭文档级编号和跨公式引用；输入编码、非有限参数和控制字符按明确规则验证。

分别限制输入字节、批量数、宏展开、执行时间、输出字节、SVG 元素/路径数量及画布尺寸。初始默认值由 P0 的正常与极端语料确定，并允许调用方收紧。超限返回稳定错误，不截断输出。

| 缓存 | 所有者 | 规则 |
| --- | --- | --- |
| TeX 到 `MathSvg` | `MathTypesetter` | 有界 LRU，按条目及字节限制；实例持有固定 bundle/runtime 版本，缓存不跨实例共享；键包含 TeX、display、字号、ex_ratio、color、扩展及输出策略 |
| SVG 解码/绘制 | 现有 `Renderer` | 沿用资源缓存与 `ImageResource.cache`；不能代替公式排版缓存 |

批量去重使用完整语义键并保持顺序。缓存不写磁盘，已返回的纯值不受淘汰影响。日志记录操作、错误类别与预算，不默认记录完整公式。

## 8. 文件落点

当前实现落点如下：

```text
python/takumi_py/math/
  __init__.py           # public exports
  errors.py             # public math exceptions
  models.py             # MathSvg, converter protocol, options, limits
  typesetter.py         # lifecycle, batch, bounded cache
  _process.py           # supervised worker transport and deadline handling
  _worker.py            # MiniRacer request loop
  _validation.py        # input and SVG validation
  assets/
    mathjax.bundle.js   # pinned build output
    manifest.json       # versions, hashes, font/extension inventory
tests/
  test_math.py
  test_math_integration.py
  test_math_layout.py
  test_math_process.py
  test_math_validation.py
  test_document_rendering.py
examples/render_math.py
tools/mathjax/
  package.json
  bun.lock
  build.mjs
  mathjax-entry.mjs
  README.md
```

| 当前文件 | 当前状态 |
| --- | --- |
| `pyproject.toml`、`uv.lock` | 可选引擎 extra、资源打包；core 不强制安装 JS 引擎 |
| `python/takumi_py/math/errors.py` | 公开数学异常，并保持其与 `TakumiError` 的继承关系 |
| `python/takumi_py/__init__.py` | 保持轻量，可选 API 优先从 `takumi_py.math` 导入 |
| `document.py`、`options.py`、`types.py` | 文档/fragment/资源快照、布局与输出选项；不新增数学原生节点 |
| `src/`、`_core.pyi` | 新增无状态编译函数、样式合并与字体快照；基线沿用通用 CSS |
| `.github/scripts/check-distributions.py`、`smoke-wheel.py`、`verify-distributions.py` | 校验本地资源、可选依赖和仓库外安装 |
| CI、发布 workflow | 增加 math extra 平台矩阵及禁网运行 smoke |
| `docs/en/`、`docs/zh/`、两个 README | 同步 API、安装、尺寸/基线、限制与错误说明 |
| `THIRD_PARTY_NOTICES.md`、`LICENSES/` | 补齐 MathJax 和字体许可 |

本计划放在公开站点的 `docs/en`、`docs/zh` 之外，不将实现中的预览 API 写成稳定已发布能力。正式文档继续遵守英文来源与中文镜像规则。

## 9. 分阶段交付

| 阶段 | 交付内容 | 通过条件 |
| --- | --- | --- |
| P0：技术验证 | 嵌入式运行时实验、固定 bundle、公式样本、baseline 与平台报告 | 无 Node/浏览器/网络运行；基础与 AMS/mhchem 可用；可中断；基线正确；明确平台缺口 |
| P1：静态资源契约 | `MathSvg`、`MathConverter`、选项、资源/HTML/node 转换、错误契约 | 无引擎也可使用静态结果；render/measure/compiled 路径尺寸一致 |
| P2：可选排版器 | 单公式、批量、生命周期、预算、缓存和状态隔离 | 无宏污染；超时可恢复；关闭释放资源；缺依赖有明确诊断 |
| P3：分发集成 | 原生回归、示例、跨平台 wheel/sdist、math extra 矩阵 | 运行不依赖 checkout、Node、CDN 或开发机数学字体；core 安装维持现状 |
| P4：发布准备 | 双语文档、许可、API 审查、性能基线与迁移说明 | 门禁通过，实验性和稳定能力标注准确，由正常 release 流程决定版本 |

下一大版本按 [整体 binding 阶段](binding-next.md#8-实施顺序与完成口径) 与公式阶段共同推进。静态资源、引擎、分发各自报告完成度；本地 P0 不代替跨平台发行验收。本文不直接修改 `0.4.0` 元数据。

## 10. 验证与验收

| 层级 | 必须覆盖 |
| --- | --- |
| 纯值/API | 数值与编码校验、不可变结果、HTML 转义、稳定资源 ID、显式资源传递 |
| 排版语义 | 分式、上下标、根号、伸缩括号、积分/求和、矩阵、AMS、mhchem、非法 TeX |
| SVG 完整性 | 离线资源、路径字形、`g`/`path`/`rect`/`line` 元素白名单、重复公式、currentColor、缺字和超预算结果 |
| 原生视觉 | 行内基线与行高、块级居中、多行混排、宽度限制、不同字号/DPR、透明背景 |
| 多输出 | 相同资源的 measure/raster/compiled/SVG 结果一致；矢量输出保留公式图形 |
| 生命周期 | 多实例、多线程约束、宏隔离、批量失败、超时中断、故障后重建、关闭 |
| 缓存 | 完整语义键、去重、容量/字节淘汰、禁用缓存、已返回结果不失效 |
| 分发 | core-only 导入、`[math]` 隔离安装、无 Node/PATH 环境、禁网运行、sdist 重建 |

视觉基准用固定公式与固定引擎/字体版本；可用开发环境中的 MathJax 浏览器输出作参考，但浏览器不成为运行时依赖。比较几何、基线及有容差的像素结果，避免跨平台脆弱的 PNG 字节相等断言。

新增可选引擎测试在 core-only 环境可以跳过，但发布用 math profile 必须安装该能力并真实运行，不能以 skip 代替通过。基础无依赖测试仍应验证缺引擎诊断。

记录冷启动、首次复杂公式、热缓存命中、批量重复与不同公式吞吐、常驻内存、wheel 增量；P0 建立基线后确定可接受阈值，不预先承诺未经测量的毫秒数。

实现阶段沿用仓库门禁，并增加 math profile：

```bash
make check
make docs-build
prek run --all-files
make build-artifacts
```

修改 workflow 时再运行 manual `actionlint`。修改 Rust 时按开发流程重建扩展并验证 stub/runtime 一致；不能用旧本地二进制作为验证结果。

完成条件为：Python 调用方能显式排版 TeX，将自包含公式资源交给既有 Takumi 接口，得到基线与尺寸正确的输出；可选依赖、离线运行、生命周期、平台范围和失败行为均可重现。仅能导入模块或生成一张 PNG 不算完成。

## 11. 证据与参考

- [当前 Python 资源模型](../../python/takumi_py/options.py)、[节点模型](../../python/takumi_py/types.py)、[Renderer](../../python/takumi_py/renderer.py)、[原生图片解码](../../src/images.rs)。
- [当前绑定版本](../../Cargo.toml)、[支持矩阵](../en/reference/support.md)、[开发及子模块升级规则](../en/maintainers/development.md)。
- [上游 HTML 节点构建](https://github.com/kane50613/takumi/blob/346ecd69e6a61be9481ce8313cc3edd2f05eac4b/takumi-core/src/html/mod.rs#L495-L527)：特殊处理 SVG，其他标签落到文本/容器。
- [上游 MathML 命名空间解析](https://github.com/kane50613/takumi/blob/346ecd69e6a61be9481ce8313cc3edd2f05eac4b/takumi-core/src/html/markup.rs#L269-L274)：不能等同数学布局。
- [上游静态 SVG 集成示例](https://github.com/kane50613/takumi/blob/346ecd69e6a61be9481ce8313cc3edd2f05eac4b/docs/content/docs/charts.mdx)：先由外部库排版/绘图，再由 Takumi 渲染。
- [MathJax 官方仓库](https://github.com/mathjax/MathJax-src)、[SVG 输出配置](https://docs.mathjax.org/en/latest/options/output/svg.html)、[服务器端使用](https://docs.mathjax.org/en/latest/server/start.html)：实施 P0 时核对选定版本的实际 API 与字体加载机制。
