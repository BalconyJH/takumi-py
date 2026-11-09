# 下一大版本 binding 架构

日期：2026-11-09。范围：Python binding 的文档、资源、编译、布局与静态输出边界，以及公式预排版接入。

当前实现升级到正式发布标签 `takumi@2.20.0`（`ae2a35011e5cddedb0a4c8b33ab0c9242ca76b2d`），
对应 `takumi-core 0.36.0`。下表保留最初审查的 2.17.1 基线；本轮新增 retained bitmap、
原生资源快照、模板文档适配、上游 `needs()`、HTML 内嵌 CSS 与 `@font-face` 文件加载。

这是开发方案与实施记录，不是已发布版本承诺。项目元数据仍为 `0.4.0`；版本号、旧接口移除和支持矩阵由正式发布流程决定。公式运行契约与限制见 [公式渲染指南](../en/guides/math.md)，进程监督和超时回收回归见 [test_math_process.py](../../tests/test_math_process.py)，binding 公式契约见 [math-rendering.md](math-rendering.md)。

## 1. 重新审查的结论

应保留 Takumi 作为唯一宿主布局与绘制引擎，让公式、图表等生产静态资源的能力通过文档组合进入同一管线。需要调整的是 binding 的公共边界，而非新增公式原生节点或在渲染期间运行 TeX。

当前 `main@80ca0dd`、`takumilib@7ddc5c2` 的问题与证据：

| 当前行为 | 影响 | 下一版决策 |
| --- | --- | --- |
| `Renderer` 同时提供节点/HTML/模板/compiled 的 raster/measure/SVG 组合方法 | 新增一种输入需要重复扩展方法与参数 | 输入归一为 `Document`，输出收敛为三个方法 |
| `CompiledHtml` 与 `ParsedHtml` 都只有 node 与 sheets，当前 sheets 为空 | 资源不能随编译结果保留，容易遗漏每次调用的 `images=` | `CompiledDocument` 持有节点、合并样式和不可变资源集合 |
| `html.py` 导入时构造 `_PARSER = NativeRenderer(...)` | 无状态解析依赖有状态 renderer 生命周期 | `_core` 提供独立编译函数，移除全局 parser renderer |
| `src/stylesheets.rs` 每次渲染合并多个 sheet 时重新解析 CSS | “预编译”没有完成文档级编译 | 文档编译阶段合并一次；输出使用单个 compiled sheet |
| 原生字体锁覆盖完整 render/measure | 字体更新等待绘制与编码完成 | 在操作开始获取 COW 字体快照，随后释放注册表锁 |
| `RenderOptions` 混合布局、资源、编码与 DPR | 不同输出忽略不同字段，单位不直观 | 拆成 `LayoutOptions` 与 `RasterOptions`；资源随文档 |
| 原生 viewport 与测量以 device px 工作 | 直接在 Python 标注 CSS px 会造成错误 | 新接口统一 CSS 布局单位，在适配边界转换 |
| `to_serde_input` 把 bytes 展开为 Python 整数列表 | 大图片内嵌节点的桥接开销大 | 通用 Serde 值适配直接复制 bytes，保留映射顺序，交给上游 Node schema；不承诺零拷贝 |

独立运行探针已经确认：30×20 的 SVG 图片在 DPR=2 的旧测量接口中为 60×40，而显式 200×80 画布仍是 200×80；`vertical-align:-5px` 在 HTML 和节点路径中均使行内图片下移 5px；同一个 `currentColor` SVG 资源可以在两个位置分别渲染红色和蓝色。2.20 的 SVG 后端将可保留的图形展开为宿主矢量路径，含滤镜等内容仍可能使用栅格回退。

## 2. 目标管线与所有权

```text
HTML / Node / Template --> Document --> compile_document --> CompiledDocument
                               ^                                  |
                               |                                  v
TeX / Chart --> Fragment                    Renderer + LayoutOptions
                                               /   |    |     \
                                           needs measure SVG rasterize
                                                              |
                                                          RasterImage
                                                              |
                                                   encode / RGBA / Fragment
```

| 对象 | 拥有的数据 | 生命周期与职责 |
| --- | --- | --- |
| `ResourceSet` | 资源标识、bytes、cache hint | 不可变快照；同标识冲突报错，相同资源去重 |
| `Fragment` | 节点片段与资源集合 | 预排版器、图表等输出的通用组合单位 |
| `Document` | HTML 或节点源、CSS、keyframes、资源 | 对输入建立快照；节点中的 fragment 在此展开 |
| `CompiledDocument` | 原生节点、Arc 合并样式、原生编码资源快照 | 不依赖某个 renderer；可复用且不持有 JS context |
| `Renderer` | 字体注册表、解码与绘制缓存 | 原生 needs 查询、测量与输出；不下载或生成文档资源 |
| `RasterImage` | 原生 Bitmap、实际像素宽高 | 绘制一次后多次编码；读取 RGBA 时才复制到 Python |
| `MathTypesetter` | 公式运行时、公式缓存和预算 | 显式预排版；输出后可关闭，不被文档反向持有 |

编译后的文档在这里是内容与资源的持有者，不是保存计算后布局的 scene。每次输出仍调用 Takumi 布局。当前上游 `Scene` 含 `Rc` 等内部状态，raster 和 SVG 的高层入口也各自布局；不能简单把它挂在跨线程 Python 对象上并声称完成布局复用。

图片资源随文档固定；字体注册仍属 renderer，文档的 fallback family 选择由 `LayoutOptions` 指定。因此相同文档在不同字体注册表上的结果可能不同。需要完全可复现的任务，应显式创建同配置 renderer；本阶段不假装文档已经封装字体环境。

## 3. 公共 API

```python
from takumi_py import (
    Document,
    ImageResource,
    LayoutOptions,
    RasterOptions,
    Renderer,
    ResourceSet,
    compile_document,
)

document = Document.from_html(
    '<div class="card"><img src="logo"></div>',
    stylesheets=[".card { width: 320px; height: 180px; }"],
    resources=ResourceSet(images=[ImageResource("logo", logo_bytes)]),
)
compiled = compile_document(document)
renderer = Renderer()
layout = LayoutOptions(width=320, height=180)
png = renderer.render(compiled, layout=layout, output=RasterOptions(scale=2))
geometry = renderer.measure(compiled, layout=layout)
svg = renderer.render_svg(compiled, layout=layout)
```

`logo_bytes` 是调用方已经取得的图片。这里不提供下载器或隐式网络行为。

| 操作 | 返回 | 约定 |
| --- | --- | --- |
| `Document.from_node(...)` | `Document` | 对节点建立快照，展开 fragment；CSS 严格解析 |
| `Document.from_html(...)` | `Document` | 保留显式 HTML 与资源；CSS 沿用容错解析 |
| `compile_document(document)` | `CompiledDocument` | 无 renderer，节点/样式编译一次 |
| `Renderer.render(document, layout=..., output=...)` | `bytes` | 编码图片或 raw RGBA |
| `Renderer.measure(document, layout=...)` | `MeasuredNode` | CSS px 下的布局几何 |
| `Renderer.render_svg(document, layout=...)` | `str` | CSS px viewport，不接收 raster 选项 |

三个输出方法均接受 `Document` 或 `CompiledDocument`。直接传入源文档是单次操作便利入口；循环输出应显式编译。保留具名构造函数，不靠猜测字符串是 HTML、文件路径还是 TeX。

`TemplateRenderer.document()` 与 `render_template_to_document()` 已将 Jinja 输出接入文档。
只做文档转换时不构造 renderer；模板环境不会随文档保留。保留已有直接输出方法作为兼容入口。

`Renderer.rasterize(document, layout=..., scale=...) -> RasterImage` 对齐上游
`render -> Bitmap -> write_image`。它与 `render()` 使用同一原生绘制实现，后者继续返回编码 bytes。
`RasterImage.encode()` 可以跨线程并发编码同一不可变 bitmap，实际宽高、stride 与 RGBA 数据
无需额外 measure 推断。不同格式不会重复布局与绘制；独立 SVG 和 measure 仍各自布局。

## 4. 资源组合

节点中的 fragment 会贡献内容及资源：

```python
from takumi_py import Document

document = Document.from_node(
    {
        "type": "container",
        "style": {"display": "block"},
        "children": [
            {"type": "text", "text": "Result: "},
            formula.to_fragment(),
        ],
    }
)
```

`formula` 是已完成的公式结果。该组合不启动排版器。

资源不是全局注册表。文档销毁时，其资源引用可释放；renderer 缓存可以另行保留解码结果并按预算淘汰。相同 `src` 的不同内容或 cache hint 是文档构造错误，不采用列表最后一项静默覆盖。不同 `src` 的相同内容仍可以被底层内容哈希缓存复用。

HTML 仍通过 `formula.to_html()` 与 `ResourceSet` 显式组合。首期不引入自定义标签、字符串替换占位符或 HTML 公式扫描。后续 HTML fragment 组合应形成专门的可信标记与资源绑定接口，不能借 Jinja 的 `safe` 自动放宽所有外部文本。

`CompiledDocument.resource_urls()` 合并节点与样式的静态引用，`missing_resources()` 报告尚未
提供的已知图片标识。两者是保守诊断。`with_resources()` 保留节点和样式句柄，追加不可变资源，
无需重新解析文档；重复定义仍按 `ResourceSet` 契约处理。

实际加载决策使用上游 `Renderer.needs(document, layout=..., scale=...)`：它在 CSS 级联后处理隐藏节点、
媒体查询、变量、伪元素与字体选择，返回 `RenderNeeds(images, faces, font_files)`。
图片集合包含已提供的标识；应用自行与文档资源比较。`font_files` 表示下一步待加载的
`@font-face` 来源。获取字节后通过 `load_font_file(url, data)` 提供，失败 URL 放进单次
`LayoutOptions.failed_font_files` 以尝试下一来源。加载图片可能暴露 SVG 文本的新字体需求，
所以调用方应按需重新查询；这些 API 均不自动联网。栅格输出使用相同的 scale 查询，
让 `resolution` 媒体规则和设备视口取整一致；measure/SVG 使用默认 scale=1。

HTML 使用上游 `parse_html` 提取 `<style>`；级联次序与 NAPI 一致：显式 CSS、文档内 CSS、
结构化 keyframes。`media` 属性由上游包装为媒体规则。低层 `_core.compile_html` 仍只返回节点，
完整文档和公开 HTML 适配器使用携带 CSS 的路径。外部 `<link>` 不自动获取。

## 5. 坐标与输出

| 项目 | 新文档 API | 兼容 API |
| --- | --- | --- |
| 显式 `width/height` | CSS px | 原生输出像素 |
| 测量 | DPR 固定为 1，返回 CSS px | 受 `device_pixel_ratio` 影响 |
| 栅格倍率 | `RasterOptions.scale` | `RenderOptions.device_pixel_ratio` |
| 显式 raster 画布 | `ceil(css_size * scale)` | 不再乘 DPR |
| SVG | CSS px，不应用 scale | 保持原有行为 |

当前实现利用上游 DPR 缩放长度，同时为新入口缩放显式 viewport，避免二次缩放公式资源。宽度媒体查询和 `vw` 的验证必须覆盖该转换。小数倍率、取整、像素吸附及 resolution 媒体查询可能影响最终像素/样式；此实现不是在一份固定 display list 上做纯绘制变换，也不承诺任意倍率下浮点布局逐位一致。

`measure` 描述内容布局，不保证返回的根盒尺寸等于指定画布尺寸。栅格仍按原生规则吸附到像素；
推断画布应使用 `RasterImage.size` 与 `stride`，避免从测量结果推算缓冲区大小。
原始像素为紧凑排列的 straight-alpha RGBA8；`to_raw_source()` / `to_fragment()` 保留该契约，
显式复制像素，避免编码再解码。上游 Bitmap 与绘制资源使用的预乘 alpha 不同，因此不能宣称
两者是零复制的同一个缓冲区。

## 6. 原生边界

无状态函数包括 `_core.compile_node`、`compile_html`、`parse_html`、`compile_stylesheet`、
`compile_keyframes`、`merge_stylesheets`、`compile_resources`。保留 renderer 上的旧编译方法供兼容调用。

样式合并保留来源顺序及解析模式，不能把多份内部 `StyleSheet` 简单拼接后破坏选择器次序或
keyframes 覆盖。文档持有一个合并结果；输出时借用 `Arc<StyleSheet>`，不深复制样式或来源树。
每份 CSS 在自身 EOF 处完成恢复，再将闭合后的 token 来源按顺序交给同一个上游 parser，
保留跨来源的全局 layer 次序。结构化关键帧先序列化为受控声明并解析为规范结果，再在原始
来源位置参与合并；不能统一追加到所有 CSS 之后。畸形 URL、未闭合注释和字符串不得吞掉
下一份样式。编译与合并均释放 GIL。
编码图片在编译阶段复制到 `CompiledResources`，输出时借用 Arc，不重复跨 Python/Rust 复制。
解码仍经所选 renderer 的上游 ResourceCache，尊重 `cache="none"` 和预算。

Python 负责高层对象组合、资源所有权、选项模型和公式生命周期。Rust 负责不可信原生参数校验、node/CSS/HTML 解析、字体快照、解码、布局、绘制、编码以及释放 GIL。不能只在 Python 验证有限数值而允许直接 `_core` 调用把超大 f64 转为无穷 f32。

字体快照利用上游 `Fonts` 的 Arc/COW 注册表，避免持有读锁跨越整个渲染。线程内创建原生布局对象，不把未证明 Send/Sync 的 scene 或 JS context 置入通用共享缓存。

小栈审查确认，最初的进程崩溃发生在 binding 自己的递归 Python 值快照，尚未进入
上游 Serde。快照构造与清理现改为显式工作栈，测量结果的 Rust/Python 转换和 Python
节点校验同样迭代执行。上游 Serde、CSS、HTML 与布局仍包含递归，binding 负责为这些
调用提供足够栈空间，不能把可接受的 512 层文档直接交给任意 Python 工作线程的原生栈。

`CompiledNode` 保存 `Arc<Node>` 和迭代计算的深度标记；克隆、资源遍历与完整输出在
释放 GIL 后进入统一栈边界。节点深度达到 16、Python 结构深度达到 32，或字符串中
可能嵌套 CSS 的标记达到 8 时，使用 64 MiB 栈的临时 scoped worker；普通浅层输入直接
执行。这些是保守的执行阈值，不是输入限制，也不改变 CSS 语义。深度检查必须覆盖节点
与内联 CSS 的组合：debug 下单独可通过的两种递归相加也曾导致 512 KiB 线程崩溃。
公开节点上限仍为 512；HTML 的 `max_depth` 不得大于 512。最终节点释放沿用上游
迭代式 drop，测量树则由 binding 迭代释放。

异常继续以现有 `TakumiError` 为公共基础。数学模块的异常可以在 Python 中继承它，不要求为了纯 Python 扩展而新增 PyO3 异常。基础选项形状错误仍用 `TypeError`/`ValueError`，资源同名冲突用 `ResourceError`。

## 7. 公式引擎与分发决策

数学排版处于文档编译之前，产物必须已经有自包含 SVG、尺寸和基线。MathJax 4.1.3 与 MiniRacer 0.14.1 是当前实现选择。MiniRacer 的 Linux glibc wheel 要求 2.27+，高于 core 的 2.17；平台架构 wheel 可用性和实际执行通过必须分别报告。

原建议的“独立引擎包”有利于避免 core 用户下载字体数据，但要求新增可发布制品、版本握手与独立安装测试。不能先写一个指向不存在包的 extra。首轮如果将 bundle 放在本 wheel 中，必须明确：extra 仅让 JS 运行时依赖可选，bundle 大小与许可仍属于每个 core wheel。构造排版器只验证随包 bundle；`mini-racer` 缺失或版本不匹配在第一次未命中缓存的转换启动 worker 时报告。根据实测体积再决定是否拆成正式引擎发行包。

专用线程不保证强制终止。复核实验证明 MiniRacer 的直接 eval 超时能中断 CPU 死循环，但 `Promise.resolve().then(() => { while (true) {} })` 可以让 `Promise.get(timeout=...)` 超时等待失效。因此本实现由受监督的 Python 工作进程承载 MiniRacer。父进程通过有界 JSON IPC、墙钟 deadline 和 terminate/kill 回收覆盖 bundle 启动、JS 执行及异步任务；故障进程不复用。V8 内存限制不是整个操作系统进程 RSS 限制，不能把它描述为跨平台进程内存沙箱。完整证据、固定 bundle 哈希和当前平台边界见 [P0 运行时报告](math-runtime-p0.md)。

## 8. 实施顺序与完成口径

| 阶段 | 内容 | 完成口径 |
| --- | --- | --- |
| A | 文档、fragment、资源快照与独立编译 | 无全局 parser renderer；资源随 compiled 文档保留；样式合并一次 |
| B | 三个输出入口与选项分离 | CSS 单位、scale、媒体查询、跨 renderer 与旧接口回归通过 |
| C | 静态公式资源契约 | 基线、SVG 校验、HTML/node/fragment 一致，结果脱离引擎生命周期 |
| D | 可选 MathJax 引擎 | 离线 bundle、真实中断、预算、宏隔离、错误与缓存通过 |
| E | 分发与发布准备 | 隔离 wheel/sdist、math 平台 profile、双语文档、许可与基准 |
| F | 静态图片结果与资源桥接 | 原生 Bitmap 独立编码、实际像素尺寸、原生资源快照、直接 bytes 解码 |
| G | 2.20 上游能力 | HTML 内嵌 CSS、needs、字体文件加载/回退、正式发布点、新增字体与许可分发 |
| 后续独立议题 | 可移植字体环境、分页/PDF、跨后端 Scene 复用 | 不为本次静态图片场景引入不稳定或跨线程不安全的抽象 |

下一大版本允许改变公共架构，但不要求当前工作区立刻删除全部旧接口。保留兼容层能逐项比较结果；正式版本决定弃用时间，沿用既有弃用承诺。版本号与发布不在实现时自动触发。

完成基础架构不代表数学引擎已完成；完成本地引擎测试不代表八个平台发布验证通过。实现记录及最终交付必须分别报告。

## 9. 验证

- 文档与 fragment 输入/暴露副本突变不影响已持有数据；资源重复、冲突、循环与深度均有确定行为。
- 同一 compiled 文档跨 renderer 与多输出可用；CSS 级联、keyframes 与旧编译方法保持语义。
- 行内基线、字体大小、DPR、viewport、媒体查询、公式颜色与矢量资源保留分别验证。
- core-only 环境不导入可选 JS；实际 math profile 不允许跳过引擎测试。
- 修改 Rust 后重建扩展，再跑 stubtest、类型检查、pytest、Rustfmt 与 Clippy。
- 双语文档、wheel 内容、许可清单、仓库外 wheel 安装及 sdist 重建使用仓库现有门禁。

## 10. 初轮验收记录

2026-11-09，macOS arm64 / CPython 3.11.17，原生依赖为正式 `takumi@2.20.0`。
本节保留 review 修复前的历史记录；当前修复验收见下一节，旧制品不能代替最终源代码。

| 要求 | 当前证据 |
| --- | --- |
| 静态架构与上游一致 | 调用 crate-root render/measure/needs/render_svg/write_image；不导出不稳定 Scene |
| 可复用静态结果 | `test_raster.py` 覆盖实际尺寸、透明度、跨线程编码、原始像素组合 |
| 输入和资源所有权 | `test_document.py` 覆盖快照、资源追加、冲突、原生句柄与禁止重复 Python 读取 |
| 高效桥接与可靠错误 | `test_node_bytes.py` 覆盖 bytes/bytearray/memoryview、顺序、512/513 层、循环；keyframe 错误不再触发旧解码器崩溃 |
| 上游静态需求 | `test_render_needs.py` 覆盖 CSS 变量、隐藏节点、视口、resolution 与 font-file 回退 |
| HTML 样式语义 | `test_html_adapter.py` 覆盖内嵌样式、media、显式样式顺序、公开兼容入口 |
| 公式完整性 | 完整 MathJax 测试继续运行；2.20 的路径展开与量化尺寸已纳入回归 |
| 全套门禁 | `make check` 通过；最终新增倍率查询测试后全量 pytest 为 722 passed，Ruff/ty 通过 |
| 文档与示例 | 英文/中文严格构建与翻译镜像通过；静态卡片与公式示例已实际渲染并检查 |
| 分发 | Twine、归档内容、直接 wheel core/math、sdist 重建后的 core/math 安装均通过 |

验收 wheel 和 sdist 位于 `/private/tmp/takumi-next-major-artifacts`，安装验证日志为
`/private/tmp/takumi-next-major-verify-final.log`。已逐文件核对 wheel 中所有 Python 源码、
stub 及 sdist 中 Rust 源码和锁文件与当前工作区一致。Maturin 对 sdist 的 Cargo.toml
只增加 `package.readme`。

| 制品 | SHA-256 |
| --- | --- |
| `takumi_py-0.4.0-cp311-abi3-macosx_11_0_arm64.whl` | `e2d899302e4887a9041b7c837af950b32969b88dce0252a6f95fbf9f271a30b1` |
| `takumi_py-0.4.0.tar.gz` | `dfc5f0275ef5acee587cb09357e58a5ccd92082de1fe54de2af626c8e2aed1c3` |

本轮完成的是下一大版本静态能力的实现、审查和本地验收，不触发正式发布或修改项目版本。
跨平台执行仍由既有 CI 矩阵验收；本地通过不能替代其余 OS/CPU 目标。
不引用缺少可重复脚本与构建配置的性能倍率。确定的优化是消除了每字节 Python 整数列表、
重复资源上传、样式深复制及多格式导出时的重复绘制；实际吞吐依输入与编解码成本而异。

## 11. Review 修复验收

2026-11-09 的复核修复覆盖原生小栈崩溃、常用公式与边框、线性公式几何、独立 CSS
来源边界、CSS/结构化关键帧顺序、测量与验证递归、旧入口关键帧覆盖，以及数学进程启动
期限和取消竞态。详细数学契约与新 bundle 哈希见 [运行时报告](math-runtime-p0.md)。

`tests/test_native_stack.py` 的 23 个独立子进程用例覆盖 512 KiB / 1 MiB 线程、512
层节点与 HTML、513 层拒绝、循环输入、资源查询、测量、raster、SVG、序列与动画、
CSS 深嵌套、结构化 calc 和节点/CSS 组合深度。debug 与 release 均须运行；只证明
优化构建能通过不算解决。样式来源回归还覆盖 BadUrl 尾随反斜杠、NUL 规范化和全局 layer。

本地最终原生逻辑的 debug 全量通过 839 项，随后补充的 6 个样式恢复用例也单独通过；
release 全量为 845 passed。23 项小栈用例在两种构建下都通过。Ruff、ty、stubtest、
Rustfmt、Clippy、双语镜像与文档严格构建均通过。新的分发验收目录为
`/private/tmp/takumi-review-fixed-artifacts`，日志为 `/private/tmp/takumi-review-fixed-verify.log`；
该轮制品替代上一节的旧 wheel/sdist，仍为本地预览，不执行发布。

## 12. 跨平台 CI 回归接入

CI 与发布工作流现均配置八个平台乘 debug/release 的 16 个矩阵任务。平台为 Linux
glibc、Linux musl、macOS、Windows 各自的 x86_64/x64 与 ARM64；musl 在 Alpine
容器内实际安装并执行。每个任务先验证 core/math 安装冒烟，再通过
`.github/scripts/test-wheel.py` 执行 11 个测试文件的专项回归，包括原生小栈、节点
解码、样式来源、关键帧、测量和数学生命周期。完整仓库测试仍由 Ubuntu quality job
执行。ABI3 Python 3.11-3.15 的 Linux wheel 冒烟也启用 math。

专项入口将所选测试复制到仓库外，创建新的 venv，安装目标 wheel 与固定版本 pytest，
显式隔离 pytest 配置，并检查 Python 包、原生扩展与 MiniRacer 的实际加载路径。
缺少运行时、跳过测试、空报告、崩溃或超时均失败；每个矩阵保存独立的 JUnit 和日志。
任一 debug/release 任务失败都会阻止 CI required check 和后续发布，只有 release
wheel 进入发行制品集合。

本地 macOS arm64 的真实安装包回归为 debug/release 各 219 passed；此记录证明
测试入口和本地制品通过，不代表远端八个平台已经运行成功。远端运行仍需提交工作流后
按对应源提交 SHA 验收，不自动提交、创建标签或触发发布。
CI 接入后的本地整仓测试为 854 passed；Ruff、ty、Actionlint、Zizmor、工作流 schema、
变更文件 Prek 检查及中英文文档严格构建通过。隔离执行报告保存在
`/private/tmp/takumi-ci-regressions-debug.xml` 与
`/private/tmp/takumi-ci-regressions-release.xml`。

## 13. CI 层级与执行顺序

工作流保持平铺，不引入新的 reusable workflow 或 composite action。普通 CI 先执行
`quality`，成功后并行运行 `sdist-smoke` 与 16 单元 `wheel-smoke`；`abi3-smoke`
等待整个 wheel 矩阵，再使用 Linux x86_64 release 制品。`Required checks` 显式
汇总四层状态，逐层记录结果，失败、取消或跳过均不视为通过。

发布工作流删除 9 条可由前驱传递保证的重复 `needs`，但保留直接读取
`release-guard` 输出所需的边。完整制品校验、provenance、PyPI 上传、PyPI 摘要
核验、GitHub Release、版本文档、Pages 仍严格串行。三个 Check 工作流按同一
main push SHA 汇合后才允许打标签；文档预览是独立分支，仅与发布共用 Pages 部署锁。

维护者执行图见[开发说明](../zh/maintainers/development.md#ci-execution-order)和
[自动发布链路](../zh/maintainers/releasing.md#automatic-release-pipeline)。
