# 下一大版本 binding 架构

日期：2026-11-08。范围：Python binding 的文档、资源、编译、布局与输出边界，以及公式预排版接入。

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
| `to_serde_input` 把 bytes 展开为 Python 整数列表 | 大图片内嵌节点的桥接开销大 | 优先资源引用；直接 bytes 解码另行实现，不承诺零拷贝 |

独立运行探针已经确认：30×20 的 SVG 图片在 DPR=2 的旧测量接口中为 60×40，而显式 200×80 画布仍是 200×80；`vertical-align:-5px` 在 HTML 和节点路径中均使行内图片下移 5px；同一个 `currentColor` SVG 资源可以在两个位置分别渲染红色和蓝色；SVG 输出保留嵌套 SVG。探针只验证宿主行为，不证明 MathJax 排版或所有 CSS 场景。

## 2. 目标管线与所有权

```text
HTML adapter ----+
Node input ------+--> Document --> compile_document --> CompiledDocument
Template -> HTML-+       ^                                  |
                        |                                  v
TeX -> MathSvg -> Fragment                       Renderer + LayoutOptions
Chart -> SVG --> Fragment                               /    |    \
                                                      /     |     \
                                                measure  raster   SVG
                                                          |
                                                     RasterOptions
```

| 对象 | 拥有的数据 | 生命周期与职责 |
| --- | --- | --- |
| `ResourceSet` | 资源标识、bytes、cache hint | 不可变快照；同标识冲突报错，相同资源去重 |
| `Fragment` | 节点片段与资源集合 | 预排版器、图表等输出的通用组合单位 |
| `Document` | HTML 或节点源、CSS、keyframes、资源 | 对输入建立快照；节点中的 fragment 在此展开 |
| `CompiledDocument` | 原生节点、合并样式、资源快照 | 不依赖某个 renderer；可复用且不持有 JS context |
| `Renderer` | 字体注册表、解码与绘制缓存 | 执行测量与输出；不发现、下载或生成文档资源 |
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

当前 Jinja 适配器仍可生成 HTML，再交给 `Document.from_html`。不把模板加载生命周期放进原生编译器。下一阶段可以新增返回 `Document` 的模板便利方法，但无需再复制所有输出方法。

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

图片引用缺失、外部 stylesheet 中的资源发现和来源位置诊断尚未形成统一编译诊断。`CompiledNode.resource_urls()` 也不能代表整个文档的 CSS 资源闭包；本阶段不添加不完整的“资源已齐全”保证。

## 5. 坐标与输出

| 项目 | 新文档 API | 兼容 API |
| --- | --- | --- |
| 显式 `width/height` | CSS px | 原生输出像素 |
| 测量 | DPR 固定为 1，返回 CSS px | 受 `device_pixel_ratio` 影响 |
| 栅格倍率 | `RasterOptions.scale` | `RenderOptions.device_pixel_ratio` |
| 显式 raster 画布 | `ceil(css_size * scale)` | 不再乘 DPR |
| SVG | CSS px，不应用 scale | 保持原有行为 |

当前实现利用上游 DPR 缩放长度，同时为新入口缩放显式 viewport，避免二次缩放公式资源。宽度媒体查询和 `vw` 的验证必须覆盖该转换。小数倍率、取整、像素吸附及 resolution 媒体查询可能影响最终像素/样式；此实现不是在一份固定 display list 上做纯绘制变换，也不承诺任意倍率下浮点布局逐位一致。

`measure` 描述内容布局，不保证返回的根盒尺寸等于指定画布尺寸。栅格仍按原生规则吸附到像素；raw 输出仍是 bytes，若画布使用推断尺寸，调用方须通过布局与已定义的原生取整规则确定大小。后续可添加携带尺寸与 stride 的 `RasterImage` 结果，另行设计兼容性。

## 6. 原生边界

新增无状态函数 `_core.compile_node`、`compile_html`、`compile_stylesheet`、`compile_keyframes`、`merge_stylesheets`。保留 renderer 上的旧编译方法供兼容调用。

样式合并保留来源顺序及解析模式，不能把多份内部 `StyleSheet` 简单拼接后破坏选择器次序或 keyframes 覆盖。文档持有一个合并结果；渲染快速路径只克隆其原生 stylesheet，不再克隆 CSS source 树。

Python 负责高层对象组合、资源所有权、选项模型和公式生命周期。Rust 负责不可信原生参数校验、node/CSS/HTML 解析、字体快照、解码、布局、绘制、编码以及释放 GIL。不能只在 Python 验证有限数值而允许直接 `_core` 调用把超大 f64 转为无穷 f32。

字体快照利用上游 `Fonts` 的 Arc/COW 注册表，避免持有读锁跨越整个渲染。线程内创建原生布局对象，不把未证明 Send/Sync 的 scene 或 JS context 置入通用共享缓存。

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
| 后续 | 字体随文档、typed image handles、布局复用、模板 document adapter | 按独立问题和上游稳定接口实施，不虚报为本阶段完成 |

下一大版本允许改变公共架构，但不要求当前工作区立刻删除全部旧接口。保留兼容层能逐项比较结果；正式版本决定弃用时间，沿用既有弃用承诺。版本号与发布不在实现时自动触发。

完成基础架构不代表数学引擎已完成；完成本地引擎测试不代表八个平台发布验证通过。实现记录及最终交付必须分别报告。

## 9. 验证

- 文档与 fragment 输入/暴露副本突变不影响已持有数据；资源重复、冲突、循环与深度均有确定行为。
- 同一 compiled 文档跨 renderer 与多输出可用；CSS 级联、keyframes 与旧编译方法保持语义。
- 行内基线、字体大小、DPR、viewport、媒体查询、公式颜色与矢量资源保留分别验证。
- core-only 环境不导入可选 JS；实际 math profile 不允许跳过引擎测试。
- 修改 Rust 后重建扩展，再跑 stubtest、类型检查、pytest、Rustfmt 与 Clippy。
- 双语文档、wheel 内容、许可清单、仓库外 wheel 安装及 sdist 重建使用仓库现有门禁。
