# 文档

## 语言 { #languages }

文档为双语。美式英语是第一语言，简体中文逐页镜像英文：

| 语言 | 源文件 | 配置 | 发布位置 |
| --- | --- | --- | --- |
| 英文 | `docs/en/` | `zensical.toml` | 站点根目录 |
| 简体中文 | `docs/zh/` | `zensical.zh.toml` | `zh/` |

- 英文页面是权威来源。先修改英文，再在同一次变更中更新中文页面，使两者永远不会描述不同
  的行为。
- 两棵目录树在相同路径下包含相同的页面，两份配置声明相同的导航。代码示例完全相同，只翻译
  正文、标题和导航标题。
- API 参考在两个站点上都渲染英文文档字符串。中文参考页只翻译生成签名周围的说明文字。
- `make docs-build` 在严格构建之前运行 `.github/scripts/check-docs-i18n.py`。页面缺少对应
  版本、两种语言的导航不一致，或两份配置在语言相关键之外存在差异时，检查都会失败。

### 英文写作风格 { #english-style }

使用美式英语书写，例如 "behavior"、"color"、"initialize"，"license" 兼作名词和动词。
使用第二人称和现在时，并点明句子所涉及的 API。

### 中文术语 { #chinese-terminology }

API 名称、参数和字面量保持代码字体，不做翻译。反复出现的概念统一译为：

| English | 中文 |
| --- | --- |
| renderer | 渲染器 |
| node tree | 节点树 |
| compiled node | 已编译节点 |
| stylesheet | 样式表 |
| viewport | 视口 |
| raster output | 位图输出 |
| measurement | 测量 |
| font family | 字体族 |
| fallback | 回退 |
| subset | 子集 |
| golden image | 基准图 |
| deprecation warning | 弃用警告 |
| source distribution (sdist) | 源码分发包（sdist） |

中文页面的每个标题都要写出与英文页面相同的锚点，例如 `## 字体子集 { #font-subsets }`，
这样两种语言的页内链接保持一致。

## 信息架构 { #information-architecture }

每种语言的目录树都按读者和任务划分：

```text
docs/en/ 与 docs/zh/
├── getting-started/  # 完成一次成功渲染的最短路径
├── guides/           # 面向任务的解释与组合
├── reference/        # 精确约定、支持矩阵、生成的 API
├── migration/        # 核心升级带来的行为变化与必需改动
└── maintainers/      # 仓库工作流与发布操作
```

新增页面之前，先判断它回答的是 **如何完成任务**、**精确的约定是什么**、**升级时改变了
什么**，还是 **如何维护仓库**。无法归入任何一类的页面很可能混杂了多种职责，应先拆分。

## 内容归属 { #content-ownership }

- `README.md` 及其中文版本 `README.zh-CN.md` 提供项目概览、安装方式、最小示例和进入文档
  的链接，不重复指南内容。
- `docs/*/guides/` 负责使用行为。每个主题只有一个归属页面，其他页面链接到它，而不是重述。
- `docs/*/reference/api/` 用 mkdocstrings 渲染源码签名，不手工复制参数表。
- 可运行示例位于 `examples/`，由 `tests/test_examples.py` 执行。指南链接这些示例，而不是
  嵌入完整脚本。
- `CHANGELOG.md` 以英文记录发布事实；迁移页面解释跨版本的取舍和必需改动。
- 发布操作，包括版本化文档的部署，只记录在 `maintainers/releasing.md` 中。

## 本地编写 { #authoring-locally }

每次预览一种语言：

```bash
make docs-serve
make docs-serve-zh
```

语言切换器链接到已发布站点的布局，即站点根目录和 `zh/`，因此只在部署后的站点上生效。
提交变更之前，运行与 CI 相同的检查和严格构建：

```bash
make docs-build
```

`zensical.toml` 和 `zensical.zh.toml` 位于仓库根目录。显式的 `nav` 是公共信息架构的一部分：
新增、移动或删除页面时，必须同时更新两份文件。

### 可用的编写组件 { #available-authoring-components }

在有助于理解时使用框架组件：

| 需求 | 组件 |
| --- | --- |
| 比较可替换的输入或命令 | 联动的内容标签页 |
| 不打断主线地提示警告 | 提示框或可折叠详情 |
| 在索引页展示并列的去处 | 卡片网格 |
| 解释流水线或状态转换 | Mermaid 图 |
| 不打断可运行示例地解释某一行 | 代码注释 |

避免使用不增加信息层次的装饰性组件。

## 版本管理 { #versioning }

站点使用兼容 Zensical 的 mike 分支。版本准备在
[自动发布链路](releasing.md#automatic-release-pipeline) 末尾、基于已验证的发布标签运行。
生成的 `gh-pages` 分支是持久的版本状态，而不是 Pages 的发布来源；发布工作流把它导出为
Pages 制品，并通过 `github-pages` 环境部署。英文版本位于分支根目录，中文版本位于 `zh/`
之下，各自维护 `versions.json`，因此每个站点的版本选择器只列出自己的部署。普通的文档构建
只校验站点，不会更新任何一个目标。
