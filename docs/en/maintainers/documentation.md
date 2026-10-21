# Documentation

## Languages

The documentation is bilingual. American English is the primary language, and
Simplified Chinese mirrors it page for page:

| Language | Source | Configuration | Published at |
| --- | --- | --- | --- |
| English | `docs/en/` | `zensical.toml` | Site root |
| Simplified Chinese | `docs/zh/` | `zensical.zh.toml` | `zh/` |

- The English page is the source of truth. Change it first, then update the Chinese page
  in the same change so the two never describe different behavior.
- Both trees hold the same pages at the same paths, and both configurations declare the
  same navigation. Code samples are identical; only prose, headings, and navigation
  titles are translated.
- The API reference renders English docstrings on both sites. Chinese reference pages
  translate only the prose around the generated signatures.
- `make docs-build` runs `.github/scripts/check-docs-i18n.py` before the strict builds.
  It fails when a page lacks its counterpart, when the navigation of the two languages
  diverges, or when the two configurations differ outside their language-specific keys.

### English style

Write in American English: "behavior", "color", "initialize", "license" as a noun and
a verb. Use the second person and the present tense, and name the API a sentence is
about.

### Chinese terminology

Keep API names, parameters, and literals in code font and untranslated. Translate the
recurring concepts consistently:

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

## Information architecture

Each language tree is divided by audience and task:

```text
docs/en/ and docs/zh/
├── getting-started/  # Shortest path to a successful render
├── guides/           # Task-oriented explanations and composition
├── reference/        # Exact contracts, support matrix, generated API
├── migration/        # Behavioral and required changes across core upgrades
└── maintainers/      # Repository workflows and release operations
```

Before adding a page, decide whether it answers **how to complete a task**, **what the
exact contract is**, **what changed during an upgrade**, or **how to maintain the
repository**. A page that fits none of these categories probably mixes responsibilities
and should be split first.

## Content ownership

- `README.md` and its Chinese counterpart `README.zh-CN.md` provide the project
  overview, installation, a minimal example, and links into the documentation. They do
  not repeat guide content.
- `docs/*/guides/` owns usage behavior. Each topic has one home; other pages link to it
  instead of restating it.
- `docs/*/reference/api/` renders source signatures with mkdocstrings and does not copy
  parameter tables by hand.
- Runnable examples live in `examples/`, where `tests/test_examples.py` executes them.
  Guides link to them rather than embedding complete scripts.
- `CHANGELOG.md` records release facts in English; migration pages explain cross-version
  decisions and required changes.
- Release operations, including versioned documentation deployment, live only in
  `maintainers/releasing.md`.

## Authoring locally

Preview one language at a time:

```bash
make docs-serve
make docs-serve-zh
```

The language switcher links to the published layout, the site root and `zh/`, so it
only works on the deployed site. Run the same checks and strict builds used by CI
before submitting a change:

```bash
make docs-build
```

`zensical.toml` and `zensical.zh.toml` live at the repository root. Explicit `nav` is
part of the public information architecture: update it in both files whenever a page
is added, moved, or removed.

### Available authoring components

Use framework components when they improve comprehension:

| Need | Component |
| --- | --- |
| Compare alternative inputs or commands | Linked content tabs |
| Surface a warning without breaking the main flow | Admonition or collapsible detail |
| Present peer destinations on an index page | Card grid |
| Explain a pipeline or state transition | Mermaid diagram |
| Explain one line without interrupting a runnable example | Code annotation |

Avoid decorative components that add no information hierarchy.

## Versioning

The site uses the Zensical-compatible mike fork. Version preparation runs from the
verified release tag at the end of the
[automatic release pipeline](releasing.md#automatic-release-pipeline). The generated
`gh-pages` branch is persistent version state rather than the Pages publishing source;
the release workflow exports it as a Pages artifact and deploys it through the
`github-pages` environment. English versions live at the branch root and Chinese
versions under `zh/`, each with its own `versions.json`, so each site's version
selector lists its own deployments. Ordinary documentation builds validate the site
without updating either destination.
