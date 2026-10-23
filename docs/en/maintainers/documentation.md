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

Give every Chinese heading the English page's anchor, such as
`## 字体子集 { #font-subsets }`, so in-page links match across both languages.

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
- `CHANGELOG.md` records release facts in English: curated notes under `[Unreleased]`,
  which `make changelog` dates and completes with the release's commits and
  contributors. Each released section becomes the GitHub Release notes. Migration pages
  explain cross-version decisions and required changes.
- Release operations, including versioned documentation deployment, live only in
  `maintainers/releasing.md`.

## Authoring locally

Preview one language at a time:

```bash
make docs-serve
make docs-serve-zh
```

The header's language button, next to the light and dark toggle, opens the same page,
version, and anchor in the other language. It is a theme override in
`docs/overrides/partials/alternate.html` that swaps the versionless `site_url` of the
two `extra.alternate` entries, so it follows the published layout, the site root and
`zh/`, and only switches on the deployed site. Run the same checks and strict builds
used by CI before submitting a change:

```bash
make docs-build
```

`zensical.toml` and `zensical.zh.toml` live at the repository root. Explicit `nav` is
part of the public information architecture: update it in both files whenever a page
is added, moved, or removed.

Zensical is pinned to one exact version in the `docs` dependency group, because a
0.0.x release can change the theme templates that the overrides in `docs/overrides/`
build on. To upgrade it, raise the pin, run `uv lock`, rebuild with `make docs-build`,
and check the header's language button and the version banner in both languages
before you commit.

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

### Icons

Icons come from the sets bundled with Zensical: Lucide, Material Design, FontAwesome,
Octicons, and Simple Icons. Both configurations enable them through `attr_list` and
`pymdownx.emoji` with Zensical's `to_svg` generator and `twemoji` index, which inline
each icon as SVG; keep those settings identical in both files. See the Zensical
[icons and emojis guide](https://zensical.org/docs/authoring/icons-emojis/) for the
syntax.

- In front matter and in the configuration, reference an icon by its path under
  `.icons` without the extension, such as `icon: lucide/rocket` or
  `repo = "fontawesome/brands/github"`.
- In Markdown, replace each `/` in that path with `-` and wrap it in colons, such as
  `:material-rocket-launch:`. Add classes with an attribute list.
- Section index pages set a Lucide page icon in front matter. Each card in a card grid
  opens with an icon marked `{ .lg .middle }` and links onward with
  `:octicons-arrow-right-24:`. Brand logos come from Simple Icons, such as
  `:simple-jinja:`.
- A Chinese page uses the same icons, attributes, and page icon as its English source.
- A misspelled shortcode renders as literal text and does not fail the strict build.
  Confirm the icon exists under `zensical/templates/.icons/` in the installed package,
  because the bundled sets can lag behind the icon sites, then check the rendered page.
- The documentation does not use emoji shortcodes such as `:smile:`. Twemoji renders
  them as images loaded from a CDN rather than as inline SVG.

## Versioning

The site uses the Zensical-compatible mike fork. Version preparation runs from the
verified release tag at the end of the
[automatic release pipeline](releasing.md#automatic-release-pipeline). The generated
`gh-pages` branch is persistent version state rather than the Pages publishing source;
the release workflow exports it as a Pages artifact and deploys it through the
`github-pages` environment. English versions live at the branch root and Chinese
versions under `zh/`, each with its own `versions.json`, so each site's version
selector lists its own deployments. Every push to `main` also deploys its docs as the
`dev` version, as the [documentation preview](releasing.md#documentation-preview)
describes; ordinary documentation builds for pull requests validate the site without
updating either destination.

Every version without the `latest` alias opens under a banner, defined in
`docs/overrides/main.html`: on `dev` it says the pages come from `main` and can
describe unreleased changes, and on older releases and prereleases it says they are
not the latest release. It links to the latest release once the language has one.
