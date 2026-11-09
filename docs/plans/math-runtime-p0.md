# takumi-py 数学层运行时 P0 报告

状态：P0 在本地真实执行通过，可用于下一大版本集成。正式发布仍需完成其他 wheel
目标的执行验收。

日期：2026-11-08；2026-11-09 完成 review 修正，以下资产与几何数据已更新。

## 1. 结论

公式引擎使用固定版本的 MathJax 4 本地 bundle，在 MiniRacer 0.14.1 中执行，并由
父 Python 进程监督一个独立 worker。运行阶段不需要 Node.js、浏览器、外部字体、
CDN 或公式服务。

MiniRacer 自身的 `eval` timeout 不能可靠中断失控的 Promise microtask，且 V8
崩溃不能由同一 Python 进程隔离。因此不能把 MiniRacer context 直接放在调用方进程。
当前实现把 bundle 加载和 JS 执行放进
`python -I -u -m takumi_py.math._worker` 子进程；超时、崩溃、非法响应或资源耗尽时，
父进程终止并丢弃 worker，下一次 cache miss 再创建新 worker。

本地已实际证明的内容：

- 基础公式、分式、根式、上下标、AMS 矩阵、显式 mhchem 和完整行内运算符可输出。
- MathJax 字体与扩展全部来自预加载的本地模块，没有运行时动态下载路径。
- CPU 死循环、Promise microtask 死循环和子进程崩溃不会突破父进程墙钟边界。
- 一个 32 MiB V8 heap 限制可以阻止持续分配；默认值是 256 MiB。
- `close()` 可以打断在途请求；失败后的 worker 不复用。
- 同一资源可由 Takumi 的 raster、measure、SVG 和 `currentColor` 路径使用。
- macOS arm64 完成真实执行。其余平台目前只有 wheel 可用性证据，没有执行结论。

## 2. 固定依赖与制品

| 项目 | 固定值 |
| --- | --- |
| Python runtime dependency | `mini-racer==0.14.1` |
| MathJax | `@mathjax/src` 4.1.3 |
| SVG 字体 | `@mathjax/mathjax-newcm-font` 4.1.3 |
| mhchem 字体扩展 | `@mathjax/mathjax-mhchem-font-extension` 4.1.3 |
| mhchem parser | `mhchemparser` 4.2.1 |
| Build tool | Bun 1.4.4 |
| Runtime asset | `python/takumi_py/math/assets/mathjax.bundle.js` |
| Bundle bytes | 11,515,590 |
| Bundle SHA-256 | `bc09bf62b474f76568b8df3810cc4a62140eaae6d25f08050f87ce95223c740d` |
| Bundle gzip bytes in manifest | 3,707,780 |
| Entry SHA-256 | `21f4b80029579ee89f434148596056f71d16cfa3fe71328285b1684a027a2ba6` |
| Bun lock SHA-256 | `3e7984f29b1f34b973c64768ad862eb50368b5074aa5dd002a0f46f13409a4f5` |

Manifest：

```text
python/takumi_py/math/assets/manifest.json
```

`MathTypesetter` 构造时读取 manifest，并在启动 worker 前校验 bundle 文件名、字节数
和 SHA-256。最终 manifest 与 bundle 的上述值一致。资产目录只放
`mathjax.bundle.js` 和 `manifest.json`。

构建命令：

```bash
cd tools/mathjax
bun install --frozen-lockfile
bun run build
```

构建需要 Bun；wheel 和 sdist 消费者直接使用预生成的 bundle，不需要 Bun 或 Node。
sdist 包含 `package.json`、`bun.lock`、`build.mjs`、`mathjax-entry.mjs` 和预生成资产，
因此发布安装不会临时下载 npm 包。

首版保留 11.5 MB 未压缩 JS。manifest 记录 gzip 大小供分发评估，但 wheel 先采用
原始文件，避免运行时解压和额外的可复现性变量。因此即使不安装 `[math]` extra，
核心 wheel 也包含这部分资产；独立数据包留给后续按真实 wheel 体积决定。

## 3. 运行时结构

```text
caller thread
    |
    v
MathTypesetter (LRU cache, batch, input/output limits)
    |
    v
ProcessRuntime (wall-clock deadline, one request at a time)
    |
    v
python -I -u -m takumi_py.math._worker
    |
    +-- JSON Lines stdin/stdout
    |
    +-- version-checked mini-racer==0.14.1
            |
            +-- preloaded local MathJax/NewCM bundle
            +-- LiteDOM, no browser or Node runtime
```

父进程的 timeout 从获取 typesetter 事务锁之前开始计时，覆盖等待另一个调用、启动
worker、读取 bundle、JS eval、Promise 等待和读取响应。到期后终止 worker；正常
Terminate 有短等待，必要时再执行 Kill。因此 `timeout_ms` 是执行预算，最终返回时间
还会受有界的进程回收步骤影响。

`Popen` 本身在单个后台启动线程内执行，等待启动也受同一个 deadline 与 `close()`
取消信号约束。取消之后才成功启动的进程会被回收；启动尚未结束时不再创建第二个启动
线程。操作系统中阻塞的进程创建无法由 Python 强行中断，因此该后台线程可能晚于调用
返回才退出，但不再阻塞调用方，也不会因连续重试无限增加线程。

worker 默认不继承 `PYTHONPATH`、`PYTHONHOME`、动态加载器注入等运行路径变量。
`py_mini_racer` 在 worker 的第一次 cache miss 中才导入；普通 core 和
`takumi_py.math` 导入不会加载它。

## 4. 关键缺陷与修正

### Promise 与 microtask 边界

直接实验曾执行：

```javascript
Promise.resolve().then(() => { while (true) {} })
```

MiniRacer 的 `eval(timeout_sec=...)` 可以返回，但随后 `JSPromise.get(timeout=...)`
超过 5 秒仍未返回。这说明该 Promise timeout 在此场景中既不能保证 Python 调用及时
返回，也不能作为中断 V8 microtask 的可靠边界。

最终方案不把该 Promise 边界当作资源边界。worker 由父进程墙钟监督，超时后整个
worker 被终止。回归测试把该 runaway microtask 放在受监督的子进程中，在 0.75 秒
预算下验证有界返回，并验证下一次请求由新 worker 完成。

### 行内公式被截断

MathJax 4 SVG output 默认 `linebreaks.inline=true`，完整行内表达式可能生成多个同级
SVG。早期桥接只取第一个 SVG，因此 `a+b`、`E = mc^2` 等曾只显示第一个操作数或符号。

最终入口显式设置：

```javascript
const svgJax = new SVG({
  linebreaks: { inline: false },
});
```

并在返回前要求 `adaptor.tags(container, "svg").length === 1`。这不是只增加“非空 SVG”
断言，而是禁止退化为部分输出。回归用例检查 `a+b` 的完整节点顺序和 8 路径复杂公式，
不再以生成一张图片作为通过条件。

### 动态字体加载

NewCM 的 SVG dynamic chunks 在入口中静态 import，并进入固定的预加载路径集合。
`mathjax.asyncLoad` 只接受集合中的精确模块名；未知路径立即报错，不会静默返回、
重复等待或回退到网络。

mhchem 默认关闭，只在
`MathTypesetter(extensions=("mhchem",))` 时加入 TeX packages。未显式启用时，
`\ce{...}` 返回语法错误。

### 不支持的公式编号

`\label`、`\ref`、`\eqref` 和 `\tag` 被固定为内部未定义宏，因此直接调用和通过
`\newcommand` 别名调用都会失败。公式编号和跨公式引用不会静默消失。

每次转换创建新的 TeX/SVG jax，因此 `\def` 或 `\newcommand` 不进入下一请求；只复用
不可变字体数据。宏泄漏测试包含定义、使用、下一次引用失败和后续正常转换。

## 5. 几何、基线与 SVG

`MathSvg` 是冻结值：

```python
MathSvg(
    data: bytes,
    width_px: float,
    height_px: float,
    depth_px: float,
    display: bool,
)
```

宽度和高度必须是有限正 float32 范围内的 CSS px。`depth_px` 是有符号 float32：
正值表示底边在基线下方，负值表示基线在图片底边下方。实现不对有效负深度做
`[-height, height]` 夹取，也不要求图像盒包含基线。

直接读取 MathJax `svgJax.getBBox(svgJax.math, html)` 的 `w/h/d`，使用 em 几何
乘一次显式字号计算宽高与深度，并据此重写 `viewBox`。MathJax 原始 SVG 的最小盒
依赖当前 em；直接复用它会在大字号下再次乘 em，产生二次放大。修正后最小盒固定为
`0.001 em`，不影响正常公式的比例；仍将实际字号传入排版器，保留 TeX `px` 长度的
绝对单位。宽度和高度属性使用 `px` 后缀，拒绝 `%` 或缺失单位。计算后越过有限 f32
范围返回 `MathLimitError`；输入字号不足以表示最小盒时返回 `MathValidationError`。

普通上标通常不会产生真实负深度：`{}^{2}` 的直接 BBox 深度为 `0.0`，`x^2` 得到正值。
独立值测试使用真实 `depth_px=-3` 的合法 SVG，确认 HTML 的
`vertical-align:3px` 和 node 的 `verticalAlign: "3px"` 都保留符号，不发生夹取。

行内 HTML 明确设置：

```text
display:inline-block
width:<px>
height:<px>
max-width:none
vertical-align:<-depth_px>px
```

块级 mode 同时使用 TeX display style 和居中 block wrapper。`to_html(alt=...)`
转义 alt；`to_image_resource()`、`to_node()`、`to_html()` 和 `to_fragment()` 使用
SVG bytes 的同一 `sha256:<hex>` 资源 ID。

## 6. 最终公式矩阵

最终 bundle 在字号 20、40、1000、2000，以及 `ex_ratio` 0.4 和 0.5 下真实执行。
`viewBox`、尺寸、深度均为有限值，且每次恰好一个 SVG root。

| TeX | path 数 | 20 px, ex 0.5 宽 | 高 | 深度 |
| --- | ---: | ---: | ---: | ---: |
| `\frac{x^2+y^2}{a+b}` | 8 | 47.169124 | 29.566530 | 8.073797 |
| `a+b` | 3 | 43.608889 | 15.54 | 1.66 |
| `E = mc^2` | 5 | 76.942179 | 16.898662 | 0.22 |
| `\sqrt{x}` | 2 | 28.5 | 21.2 | 4.34 |
| `{}^{2}` | 1 | 8.731068 | 16.678662 | 0.0 |
| `x` | 1 | 11.44 | 9.06 | 0.22 |

40 px 的对应几何按 2 倍缩放通过；`x` 在 1000 px 为 `572 x 453`，在 2000 px
为 `1144 x 906`，确认比例而非仅检查非零。`ex_ratio=0.4` 和 `0.5` 均覆盖。所选公式没有以 `ex`
表示的用户长度，因此这两个输入得到相同形状是合理的；测试验证的是选项路径和完整
输出，不虚构一个“必须改变”的像素差。

空字符串和纯空白现在返回 `MathValidationError`，不会生成零 path 的伪成功图片。

## 7. 安全与资源边界

生成的 SVG 经过独立、窄范围的校验后才能构造 `MathSvg`：

- 根必须是 SVG namespace、显式 `viewBox` 和有限 px 尺寸。
- 每个子元素必须处于 SVG namespace。
- 只接受 MathJax path 输出所需的元素和属性。
- 拒绝 `<script>`、`<style>`、事件属性、`foreignObject`、外部 URL、CSS `url(...)`
  和外部引用。
- path data 解析器按命令推进，closepath 后若继续携带隐式参数会失败。
- 多个 transform function 允许空白或逗号分隔。
- `\cancel` 的 `line` 和 `\bbox` 的受控 `rect data-bgcolor="true"` 已做窄例外。
- `data-c` 合法的空 glyph path 保留空间字形；普通空 path 仍拒绝。命名运算符和
  `\text{hello world}` 不再因为空格字形而失败。
- bbox 边框的 polygon 转换为 path；array 分隔线的类名转换为明确的描边属性。
  只移除已经识别的 MathJax 边框样式与元数据，不放宽任意 `style` 或 URL 的白名单。
- 颜色只允许命名颜色和 3/4/6/8 位 hex；CSS 函数和 URL 被拒绝。
- 树深度、元素数、path 数、输出字节数和输入字节数均有上限。

这些检查限制的是 MathJax 生成结果，不把任意调用方 XML 变成受信任 SVG。

默认预算：

| `MathLimits` 字段 | 默认值 |
| --- | ---: |
| `timeout_ms` | 5,000 |
| `memory_limit_bytes` | 268,435,456 |
| `max_input_bytes` | 65,536 |
| `max_nesting_depth` | 128 |
| `max_svg_bytes` | 1,000,000 |
| `max_batch_size` | 1,024 |
| `cache_entries` | 128 |
| `cache_bytes` | 16,777,216 |

`timeout_ms` 还受平台 `threading.TIMEOUT_MAX`，`memory_limit_bytes` 受
`sys.maxsize` 约束。cache 字节数按 UTF-8 TeX key 加 SVG bytes 计算。
`max_nesting_depth` 不可超过 128，先扫描源代码中的分组、环境与成对定界符，忽略
注释、转义和 `\verb` 内容。它不保证宏展开深度；宏执行仍在受监督进程中。

### CPU、Promise 与 heap

- worker CPU 死循环在 0.1 秒预算下通过进程 deadline 有界失败，并可由下一请求恢复。
- Promise microtask 死循环由独立进程测试覆盖，在 0.75 秒预算下有界失败并恢复。
- V8 heap 16、24、32 MiB 的上限会在加载 bundle 时返回 `MathLimitError`，48 MiB
  和 64 MiB 可以加载并转换。该实验证明限制生效，不把临界值作为公开最低内存要求。
- `set_hard_memory_limit()` 只约束 V8 heap，不是整个 worker 的 RSS 上限。
- Promise 拒绝原因缺失时通过 `was_hard_memory_limit_reached()` 区分真实堆耗尽，
  返回 `MathLimitError`；普通未知运行时异常不伪装为预算错误。
- 一次直接无限递归实验使 MiniRacer 子进程异常退出。父进程只观察到 EOF 并走既有
  worker 丢弃恢复路径；调用方进程不崩溃。该项进一步说明 MiniRacer context 不能与
  调用方共享进程，也不把“JS 永远安全”作为承诺。

## 8. 与 Takumi 的输出集成

`MathSvg.to_fragment()` 返回：

```python
Fragment(
    svg.to_node(),
    ResourceSet(images=(svg.to_image_resource(),)),
)
```

文档路径测试覆盖 `Document.from_node(fragment)` 后的：

- root 图像资源从 `MathSvg` 自有 fragment 进入文档；
- raster PNG 与 raw RGBA；
- `measure()` 使用 CSS px intrinsic 尺寸；
- 原始 2.17.1 验收中 `render_svg()` 将 SVG 作为 data URI 嵌入；升级 2.20 后改为
  转换成宿主 SVG 的矢量路径，新的回归验证字形和分数线没有丢失；
- DPR 1/2 下行内 node 与 HTML 基线一致；
- display 容器居中；
- `currentColor` 在同一资源下分别由红色和蓝色父容器解析，raster 和 SVG 输出不同。

缺省颜色保留 `currentColor`；显式 `MathOptions.color` 写入输出并进入 cache key，
因此相同 TeX 的红/蓝结果不会误命中共用条目。

## 9. 性能观察

初版 P0 bundle 的历史探针结果，仅作为基线；未用来声称 review 后版本的性能：

| 场景 | 观察值 |
| --- | ---: |
| 新 typesetter 首次复杂公式，5 次中位数 | 240.643 ms |
| 同一实例 cold process 首次 | 241.363 ms |
| 同实例 cache hit | 0.011 ms |
| 已有 worker 的新公式 | 14.994 ms |

耗时包括 worker 启动、11.5 MB bundle 加载和真实 MathJax 转换；cache hit 不经过
worker。不同机器、OS 和 wheel 不应直接复用绝对毫秒作为发布阈值。

## 10. 平台矩阵

PyPI 上 `mini-racer==0.14.1` 提供：

| 平台 | wheel 可用 | 本次真实执行 |
| --- | --- | --- |
| macOS 11 arm64 | 是 | 通过 |
| macOS 10.9 x86_64 | 是 | 未运行 |
| manylinux 2.27 x86_64 | 是 | 未运行 |
| manylinux 2.27 aarch64 | 是 | 未运行 |
| musllinux 1.2 x86_64 | 是 | 未运行 |
| musllinux 1.2 aarch64 | 是 | 未运行 |
| Windows x64 | 是 | 未运行 |
| Windows arm64 | 是 | 未运行 |

本地执行环境为 macOS 27.3 arm64、Python 3.11.17。manifest 只声明
`macos-aarch64` 为已测试平台。

数学 extra 的 Linux glibc 最低版本是 2.27，而 core 的 manylinux2014 基线是 2.17。
发布说明必须保留这个差异；不能仅凭两个 wheel 都有相同 CPU 架构就声称运行要求相同。
Windows 的 smoke network guard 还需要在真实 Windows 进程/事件循环行为上验证。

## 11. 许可

四个 JS package 元数据均为 Apache-2.0。分发包保留：

```text
LICENSES/MathJax-Apache-2.0.txt
sha256 cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30

LICENSES/mhchemparser-Apache-2.0.txt
sha256 b40930bbcf80744c86c46a12bc9da056641d722716c378f5659b9e555ef833e1
```

NewCM 和 mhchem font extension 的 npm metadata 声明 Apache-2.0，但包内没有独立的
顶层 LICENSE/NOTICE。其字体定义包含 `Copyright (c) 2024 MathJax, Inc.
(www.mathjax.org)`；根 `THIRD_PARTY_NOTICES.md` 和 bundle banner 记录该归属、MathJax
源版权、Martin Hensel 归属及修改说明。`assets/` 仍只含运行资产，不复制许可文件。

## 12. 最终验证与边界

2026-11-09 review 修复后：数学专项 91 项、进程生命周期专项 16 项通过；整仓 release
全量为 845 passed。常用命名运算符、文本空格、bbox 实际红色边框像素、array 中间
分隔线、20/1000/2000 px 比例、启动超时与取消后的迟到进程回收均有针对性覆盖。
新 bundle 和 manifest 的哈希已在第 2 节更新；当前整体验收记录见
[binding 架构修复验收](binding-next.md#11-review-修复验收)。以下保留 P0 历史数据。

初版 P0 focused gate（历史记录）：

```text
68 passed in 8.06s
Ruff: All checks passed
ty: All checks passed
```

测试范围包括纯值、严格 SVG 校验、真实 MathJax、进程 timeout/崩溃恢复、cache、
batch、close、in-lock sync、HTML/node/fragment、raster/measure/SVG、DPR 和
`currentColor`。

初版整体验收（2026-11-08，macOS arm64；不代替 review 后重新验证）：

- `make check` 通过：重建原生扩展、Ruff、ty、stubtest、591 项 pytest、Rustfmt 和 Clippy。
- 英文和中文文档严格构建、翻译镜像检查、prek 与 manual actionlint 通过。
- 新增文件单独经过 prek，生成 bundle 排除在拼写修复之外，最终哈希保持一致。
- release wheel 与 sdist 的资源、依赖、许可和 manifest 检查通过，Twine 检查通过。
- 仓库外分别安装直接构建的 wheel 与由 sdist 重建的 wheel；两者的 core-only 和
  `[math]` smoke 均通过。math smoke 的 PATH 不含 Node，worker 启用网络及进程审计。
- `Makefile` 的测试和类型检查命令显式请求 `--extra math`，避免 `uv run` 同步时移除
  可选依赖而跳过真实引擎测试。

初版历史制品在 `/private/tmp/takumi-math-artifacts-34435f1a`，完整安装验证日志在
`/private/tmp/takumi-math-final-verification.log`。这些是开发验收产物，不是正式发布：

| 制品 | SHA-256 |
| --- | --- |
| `takumi_py-0.4.0-cp311-abi3-macosx_11_0_arm64.whl` | `cbcc3ec77606a137c416d91ba88ed92e8773bbea89126cfdcda3718991013869` |
| `takumi_py-0.4.0.tar.gz` | `c419a8a1b943ff7c1a6634132638498579f22b4ea79d90e57bdec256deb2100f` |

当前支持边界：

- 需要 `[math]` extra；core-only 或 `takumi_py.math` 普通导入仍可静态使用，
  首次未缓存转换返回 `MathRuntimeUnavailableError`。
- 不扫描 Markdown/HTML 分隔符。
- 不承诺完整 LaTeX、任意宏包、`\input`、文件、网络、公式编号、交叉引用、自动换行、
  MathML 转换或任意 CSS 颜色函数。
- `\text{中文}` 等需要未打包 text glyph 的内容会被严格校验拒绝，不依赖宿主机字体
  静默生成 `<text>`。
- 只有 macOS arm64 的执行已证明；其余平台等待 CI，不能报告为通过。

相关实现与回归：

- [公式渲染计划](math-rendering.md)
- [公式指南](../en/guides/math.md)
- `tests/test_math.py`
- `tests/test_math_validation.py`
- `tests/test_math_process.py`
- `tests/test_math_layout.py`
- `tests/test_math_integration.py`
