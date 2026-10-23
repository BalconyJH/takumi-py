from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / ".github" / "scripts"


def load_script(name: str) -> Any:
    module_name = f"_repository_script_{name.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS / f"{name}.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Dataclasses resolve their string annotations through the module's entry.
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def validate_release() -> ModuleType:
    return load_script("validate-release")


@pytest.fixture(scope="module")
def set_version() -> ModuleType:
    return load_script("set-version")


@pytest.fixture(scope="module")
def deploy_docs() -> ModuleType:
    return load_script("deploy-docs")


@pytest.fixture(scope="module")
def changelog() -> ModuleType:
    return load_script("changelog")


@pytest.fixture(scope="module")
def docs_i18n() -> ModuleType:
    return load_script("check-docs-i18n")


RELEASE_SECTION = """\
## [Unreleased]

## [0.4.0] - 2026-11-01

### Added

- Something.

### Commits

#### Features

- A feature ([abc1234](https://example.invalid/abc1234))

## [0.3.0] - 2026-08-02

### Added

- Older.
"""


@pytest.mark.parametrize(
    ("version", "cargo", "prerelease"),
    [
        ("0.4.0", "0.4.0", False),
        ("0.4.0a1", "0.4.0-alpha.1", True),
        ("0.4.0b2", "0.4.0-beta.2", True),
        ("1.10.0rc3", "1.10.0-rc.3", True),
    ],
)
def test_release_versions_map_to_cargo_semver(
    validate_release: Any, version: str, cargo: str, *, prerelease: bool
) -> None:
    assert validate_release.cargo_spelling(version) == cargo
    assert validate_release.is_prerelease(version) is prerelease


@pytest.mark.parametrize(
    "version",
    ["0.4", "v0.4.0", "0.4.0-rc.1", "0.04.0", "0.4.0rc01", "0.4.0.post1", "0.4.0.dev1"],
)
def test_release_versions_reject_other_spellings(
    validate_release: Any, version: str
) -> None:
    with pytest.raises(SystemExit, match="release version must be"):
        validate_release.parse_version(version)


def test_release_changelog_requires_the_generated_commits(
    validate_release: Any,
) -> None:
    validate_release.validate_changelog(RELEASE_SECTION, "0.4.0")

    with pytest.raises(SystemExit, match=re.escape("no dated 0.5.0 release heading")):
        validate_release.validate_changelog(RELEASE_SECTION, "0.5.0")
    # The 0.3.0 section has no list of its own; the 0.4.0 one must not lend it one.
    with pytest.raises(SystemExit, match="no generated `### Commits` list"):
        validate_release.validate_changelog(RELEASE_SECTION, "0.3.0")


def test_set_version_rewrites_only_the_package_version(set_version: Any) -> None:
    manifest = (
        '[package]\nname = "takumi_py"\nversion = "0.3.0"\nedition = "2024"\n\n'
        '[dependencies]\nserde = { version = "1.0.228" }\n'
    )

    updated = set_version.set_cargo_version(manifest, "0.4.0-rc.1")

    assert updated == manifest.replace('"0.3.0"', '"0.4.0-rc.1"')
    with pytest.raises(SystemExit, match="no \\[package\\] version"):
        set_version.set_cargo_version('[dependencies]\nversion = "1"\n', "0.4.0")


@pytest.mark.parametrize(
    ("version", "deployed", "moves"),
    [
        ("0.4.0", [], True),
        ("0.4.0", ["dev", "0.3.0"], True),
        ("0.4.0", ["0.4.0", "0.3.0"], True),
        ("0.4.0", ["0.4.0rc1", "0.3.0"], True),
        ("0.4.0", ["0.5.0a1", "0.3.0"], True),
        ("0.3.1", ["0.4.0", "0.3.0"], False),
        ("0.4.0rc1", ["0.3.0"], False),
        ("0.4.0rc1", [], False),
    ],
)
def test_only_the_newest_final_release_moves_latest(
    deploy_docs: Any, version: str, deployed: list[str], *, moves: bool
) -> None:
    assert deploy_docs.moves_latest(version, deployed) is moves


def test_changelog_notes_take_one_released_section(changelog: Any) -> None:
    notes = changelog.released_section(RELEASE_SECTION, "0.4.0")

    assert notes.startswith("### Added\n\n- Something.")
    assert notes.endswith("([abc1234](https://example.invalid/abc1234))")
    assert "Older" not in notes
    with pytest.raises(changelog.ChangelogError, match=re.escape("no dated 0.5.0")):
        changelog.released_section(RELEASE_SECTION, "0.5.0")


def test_changelog_release_dates_unreleased_and_keeps_a_new_one(
    changelog: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = tmp_path / "CHANGELOG.md"
    path.write_text(
        "# Changelog\n\n## [Unreleased]\n\n### Fixed\n\n- A fix.\n\n"
        "## [0.3.0] - 2026-08-02\n\n- Older.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(changelog, "CHANGELOG", path)
    monkeypatch.setattr(
        changelog, "render_release", lambda version, **_: f"### Commits {version}"
    )

    changelog.release("0.4.0", "2026-11-01", offline=True, dry_run=False)

    assert path.read_text(encoding="utf-8") == (
        "# Changelog\n\n## [Unreleased]\n\n## [0.4.0] - 2026-11-01\n\n"
        "### Fixed\n\n- A fix.\n\n### Commits 0.4.0\n\n"
        "## [0.3.0] - 2026-08-02\n\n- Older.\n"
    )
    with pytest.raises(
        changelog.ChangelogError, match=re.escape("already has a 0.4.0 section")
    ):
        changelog.release("0.4.0", "2026-11-01", offline=True, dry_run=False)


def fake_commit(
    subject: str, convention: dict[str, Any], *, merge: bool = False
) -> Any:
    return SimpleNamespace(
        subject=subject,
        convention=convention,
        parent_hashes=["a", "b"] if merge else ["a"],
    )


def test_changelog_groups_commits_breaking_first_oldest_first(changelog: Any) -> None:
    commits = [
        fake_commit("feat: second", {"type": "Features", "subject": "second"}),
        fake_commit("Merge pull request #1", {}, merge=True),
        fake_commit(
            "refactor(api)!: drop shims",
            {"type": "Code Refactoring", "subject": "drop shims", "is_major": True},
        ),
        fake_commit("typing: tighten stubs", {"type": "", "subject": ""}),
        fake_commit(
            "feat(fonts): first",
            {"type": "Features", "scope": "fonts", "subject": "first"},
        ),
    ]

    groups = changelog.group_commits(SimpleNamespace(commits=commits))

    assert [
        (group.title, [(entry.label, entry.subject) for entry in group.entries])
        for group in groups
    ] == [
        ("Breaking changes", [("refactor(api)", "drop shims")]),
        ("Features", [("fonts", "first"), (None, "second")]),
        ("Other", [("typing", "tighten stubs")]),
    ]


def test_changelog_mentions_noreply_logins_without_network(changelog: Any) -> None:
    resolver = changelog.LoginResolver("owner/repo", offline=True)

    assert (
        resolver.resolve("Jane", "12345+jane@users.noreply.github.com", "abc", "author")
        == "@jane"
    )
    assert resolver.resolve("Bot", "bot@users.noreply.github.com", "abc", None) == (
        "@bot"
    )
    assert resolver.resolve("Sam", "sam@example.com", "abc", "author") == "Sam"
    assert resolver.unresolved == {"Sam <sam@example.com>"}
    assert changelog.mention("dependabot[bot]") == "@dependabot"


@pytest.mark.parametrize(
    ("heading", "slug"),
    [
        ("Prepare the release commit", "prepare-the-release-commit"),
        ("`render_html` and `Renderer`", "render_html-and-renderer"),
        ("**Fonts**: subsets & ranges", "fonts-subsets-ranges"),
    ],
)
def test_docs_i18n_slugs_match_python_markdown(
    docs_i18n: Any, heading: str, slug: str
) -> None:
    assert docs_i18n.slugify(heading) == slug


def test_docs_i18n_reports_drifted_anchors_and_code(
    docs_i18n: Any, tmp_path: Path
) -> None:
    english = tmp_path / "en"
    chinese = tmp_path / "zh"
    for directory in (english, chinese):
        (directory / "guides").mkdir(parents=True)
    (english / "guides" / "page.md").write_text(
        "# Page\n\n## First step\n\n```python\nrender()\n```\n\n## Second\n",
        encoding="utf-8",
    )
    (english / "only-english.md").write_text("# Only\n", encoding="utf-8")
    (chinese / "guides" / "page.md").write_text(
        "# 页面\n\n## 第一步 { #first-step }\n\n```python\nrender(1)\n```\n\n"
        "## 第二 { #second-step }\n",
        encoding="utf-8",
    )

    errors = docs_i18n.check_pages(english, chinese)

    assert errors == [
        "zh/only-english.md is missing",
        (
            "zh/guides/page.md: heading anchors ['first-step', 'second-step'] "
            "do not match English ['first-step', 'second']"
        ),
        "zh/guides/page.md: code blocks or API directives differ from the English page",
    ]
