# Documentation

## Information architecture

Documentation is divided by audience and task:

```text
docs/
├── getting-started/  # Shortest path to a successful render
├── guides/           # Task-oriented explanations and composition
├── reference/        # Exact contracts, support matrix, generated API
├── migration/        # Behavioral changes across core generations
└── maintainers/      # Repository workflows and release operations
```

Before adding a page, decide whether it answers **how to complete a task**, **what the
exact contract is**, **what changed during an upgrade**, or **how to maintain the
repository**. A page that fits none of these categories probably mixes responsibilities
and should be split first.

## Content ownership

- `README.md` provides the project overview, minimal example, and documentation entry.
- `docs/guides/` provides normative explanations of usage behavior.
- `docs/reference/api/` renders source signatures with mkdocstrings and does not copy
  parameter tables by hand.
- `CHANGELOG.md` records release facts; migration pages explain cross-version decisions
  and required changes.
- Release operations, including versioned documentation deployment, live only in
  `maintainers/releasing.md`.

## Authoring locally

```bash
make docs-serve
```

Run the same strict build used by CI before submitting a change:

```bash
make docs-build
```

The Zensical configuration lives in `zensical.toml` at the repository root. Explicit
`nav` is part of the public information architecture and must be updated whenever a
page is added, moved, or removed.

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

The site uses the Zensical-compatible mike fork. Version deployment runs from the
verified release tag at the end of the
[automatic release pipeline](releasing.md#automatic-release-pipeline). Ordinary
documentation builds validate the site but never update `gh-pages`.
