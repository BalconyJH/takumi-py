from __future__ import annotations

from email.message import EmailMessage
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
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


@pytest.mark.parametrize("channel", ["latest", "dev"])
def test_docs_i18n_resolves_readme_links_to_pages(
    docs_i18n: Any, tmp_path: Path, channel: str
) -> None:
    site = "https://example.invalid/project/zh/"
    text = (
        f"[home]({site}{channel}/) [guides]({site}{channel}/guides/) "
        f"[quickstart]({site}{channel}/getting-started/quickstart/#install) "
        f"[gone]({site}{channel}/reference/gone/) [older]({site}0.3.0/guides/)"
    )
    (tmp_path / "guides").mkdir()
    (tmp_path / "getting-started").mkdir()
    (tmp_path / "index.md").write_text("# Home\n", encoding="utf-8")
    (tmp_path / "guides" / "index.md").write_text("# Guides\n", encoding="utf-8")
    (tmp_path / "getting-started" / "quickstart.md").write_text(
        "# Quickstart\n", encoding="utf-8"
    )

    pages = docs_i18n.readme_pages(text, site)

    assert pages == ["", "guides/", "getting-started/quickstart/", "reference/gone/"]
    assert [page for page in pages if not docs_i18n.page_exists(tmp_path, page)] == [
        "reference/gone/"
    ]


@pytest.fixture(scope="module")
def check_distributions() -> ModuleType:
    return load_script("check-distributions")


@pytest.mark.parametrize(
    ("tag", "platform"),
    [
        ("cp311-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64", "linux-x86_64"),
        ("cp311-abi3-manylinux_2_17_aarch64.manylinux2014_aarch64", "linux-aarch64"),
        ("cp311-abi3-musllinux_1_2_x86_64", "musllinux-x86_64"),
        ("cp311-abi3-musllinux_1_2_aarch64", "musllinux-aarch64"),
        ("cp311-abi3-macosx_11_0_arm64", "macos-aarch64"),
        ("cp311-abi3-macosx_10_12_x86_64", "macos-x86_64"),
        ("cp311-abi3-win_amd64", "windows-x64"),
        ("cp311-abi3-win_arm64", "windows-arm64"),
    ],
)
def test_wheel_tags_map_to_release_platforms(
    check_distributions: Any, tag: str, platform: str
) -> None:
    assert check_distributions.wheel_platform(tag) == platform
    assert platform in check_distributions.EXPECTED_PLATFORMS


def test_wheel_tags_outside_the_release_matrix_are_rejected(
    check_distributions: Any,
) -> None:
    with pytest.raises(SystemExit, match="unsupported wheel platform tag"):
        check_distributions.wheel_platform("cp311-abi3-linux_riscv64")
    assert (
        check_distributions.wheel_platform(
            "cp311-abi3-linux_riscv64", allow_native=True
        )
        == "native:linux_riscv64"
    )


def test_distribution_licenses_include_bundled_engine_terms(
    check_distributions: Any,
) -> None:
    assert {
        "LICENSES/MathJax-Apache-2.0.txt",
        "LICENSES/mhchemparser-Apache-2.0.txt",
        "takumilib/takumi-core/LICENSE-CHROMIUM",
        "takumilib/takumi-core/LICENSE-EMOJI-SEGMENTER",
        "takumilib/takumi-core/LICENSE-ICU",
    } <= check_distributions.EXPECTED_LICENSES


def math_manifest(check_distributions: Any, bundle: bytes) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "bundle": {
            "file": check_distributions.MATH_BUNDLE,
            "bytes": len(bundle),
            "sha256": hashlib.sha256(bundle).hexdigest(),
        },
        "build": {
            field: f"{field}-value" for field in check_distributions.MATH_BUILD_FIELDS
        },
        "packages": [
            {
                "name": name,
                "version": package_version,
                "license": check_distributions.MATH_PACKAGE_LICENSES[name],
            }
            for name, package_version in check_distributions.MATH_PACKAGE_VERSIONS.items()
        ],
        "runtime": {
            "package": check_distributions.MATH_RUNTIME_PACKAGE,
            "version": check_distributions.MATH_RUNTIME_VERSION,
            "tested_platforms": ["macos-arm64"],
        },
        "licenses": ["test-license"],
    }


def test_math_assets_validate_manifest_and_installed_hash(
    check_distributions: Any, tmp_path: Path
) -> None:
    bundle = b"globalThis.TakumiMathJax = Object.freeze({});"
    manifest = math_manifest(check_distributions, bundle)
    assets = {
        check_distributions.MATH_BUNDLE: bundle,
        check_distributions.MATH_MANIFEST: json.dumps(manifest).encode(),
    }

    check_distributions.check_math_assets(
        assets,
        source=tmp_path / "takumi_py.whl",
        archive_path="takumi_py/math/assets",
    )

    manifest["bundle"]["sha256"] = "0" * 64
    assets[check_distributions.MATH_MANIFEST] = json.dumps(manifest).encode()
    with pytest.raises(SystemExit, match=r"bundle\.sha256"):
        check_distributions.check_math_assets(
            assets,
            source=tmp_path / "takumi_py.whl",
            archive_path="takumi_py/math/assets",
        )


def test_math_assets_reject_extra_notice_files(
    check_distributions: Any, tmp_path: Path
) -> None:
    bundle = b"globalThis.TakumiMathJax = Object.freeze({});"
    manifest = math_manifest(check_distributions, bundle)

    with pytest.raises(SystemExit, match="expected math assets"):
        check_distributions.check_math_assets(
            {
                check_distributions.MATH_BUNDLE: bundle,
                check_distributions.MATH_MANIFEST: json.dumps(manifest).encode(),
                "MathJax-NOTICE.txt": b"notice",
            },
            source=tmp_path / "takumi_py.whl",
            archive_path="takumi_py/math/assets",
        )


def test_math_assets_reject_unknown_platform_claims(
    check_distributions: Any, tmp_path: Path
) -> None:
    bundle = b"globalThis.TakumiMathJax = Object.freeze({});"
    manifest = math_manifest(check_distributions, bundle)
    manifest["runtime"]["tested_platforms"].append("plan9-mips")

    with pytest.raises(SystemExit, match="unsupported platforms"):
        check_distributions.check_math_assets(
            {
                check_distributions.MATH_BUNDLE: bundle,
                check_distributions.MATH_MANIFEST: json.dumps(manifest).encode(),
            },
            source=tmp_path / "takumi_py.whl",
            archive_path="takumi_py/math/assets",
        )


def test_math_assets_accept_any_supported_platform_subset(
    check_distributions: Any, tmp_path: Path
) -> None:
    bundle = b"globalThis.TakumiMathJax = Object.freeze({});"
    manifest = math_manifest(check_distributions, bundle)
    manifest["runtime"]["tested_platforms"] = ["linux-x86_64", "macos-arm64"]

    check_distributions.check_math_assets(
        {
            check_distributions.MATH_BUNDLE: bundle,
            check_distributions.MATH_MANIFEST: json.dumps(manifest).encode(),
        },
        source=tmp_path / "takumi_py.whl",
        archive_path="takumi_py/math/assets",
    )


def test_sdist_math_build_sources_are_exact(
    check_distributions: Any, tmp_path: Path
) -> None:
    root = "takumi_py-0.4.0"
    expected = {
        f"{root}/tools/mathjax/{name}"
        for name in check_distributions.MATH_SDIST_BUILD_FILES
    }

    check_distributions.check_math_build_sources(
        expected,
        source=tmp_path / "takumi_py-0.4.0.tar.gz",
        expected_root=root,
    )

    with pytest.raises(SystemExit, match="only reproducible MathJax build sources"):
        check_distributions.check_math_build_sources(
            {*expected, f"{root}/tools/mathjax/node_modules/pkg/index.js"},
            source=tmp_path / "takumi_py-0.4.0.tar.gz",
            expected_root=root,
        )


def test_math_runtime_dependency_is_an_optional_extra(
    check_distributions: Any, tmp_path: Path
) -> None:
    metadata = EmailMessage()
    metadata["Name"] = check_distributions.PROJECT_NAME
    metadata["Version"] = "0.4.0"
    metadata["Requires-Python"] = ">=3.11"
    metadata["License-Expression"] = "GPL-3.0-or-later"
    for license_file in check_distributions.EXPECTED_LICENSES:
        metadata["License-File"] = license_file
    metadata["Provides-Extra"] = "math"
    metadata["Requires-Dist"] = 'mini-racer==0.14.1; extra == "math"'

    check_distributions.check_metadata(
        metadata,
        "0.4.0",
        tmp_path / "takumi_py.whl",
    )

    metadata.replace_header("Requires-Dist", "mini-racer==0.14.1")
    with pytest.raises(SystemExit, match="restricted to the math extra"):
        check_distributions.check_metadata(
            metadata,
            "0.4.0",
            tmp_path / "takumi_py.whl",
        )


@pytest.fixture(scope="module")
def verify_distributions() -> ModuleType:
    return load_script("verify-distributions")


@pytest.fixture(scope="module")
def smoke_wheel() -> ModuleType:
    return load_script("smoke-wheel")


def test_smoke_import_defers_runtime_check_until_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "py_mini_racer", ModuleType("py_mini_racer"))

    smoke = load_script("smoke-wheel")

    with pytest.raises(SystemExit, match="importing takumi_py core loaded"):
        smoke.main()


def test_math_smoke_only_authorizes_the_isolated_worker_command(
    smoke_wheel: ModuleType,
) -> None:
    worker = [
        sys.executable,
        "-I",
        "-u",
        "-m",
        "takumi_py.math._worker",
    ]

    assert smoke_wheel._is_authorized_math_worker(worker) is True
    assert (
        smoke_wheel._is_authorized_math_worker([sys.executable, "-c", "pass"]) is False
    )
    assert smoke_wheel._is_authorized_math_worker([*worker, "extra"]) is False
    assert smoke_wheel._is_authorized_math_worker(["python", *worker[1:]]) is False


def test_math_smoke_guard_denies_other_process_launches(
    smoke_wheel: ModuleType,
) -> None:
    with (
        smoke_wheel.restrict_runtime_launches(),
        pytest.raises(RuntimeError, match="unauthorized process"),
    ):
        subprocess.Popen([sys.executable, "-c", "pass"])


def test_verify_distribution_arguments_remain_backward_compatible(
    verify_distributions: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "verify-distributions.py",
            str(tmp_path),
            "--expected-version",
            "0.4.0",
            "--wheel-only",
            "--sdist-built-wheel",
            "--python",
            "3.12",
            "--uv",
            "custom-uv",
        ],
    )

    args = verify_distributions.parse_args()

    assert args.dist_dir == tmp_path
    assert args.expected_version == "0.4.0"
    assert args.wheel_only is True
    assert args.sdist_only is False
    assert args.sdist_built_wheel is True
    assert args.python == "3.12"
    assert args.uv == "custom-uv"
    assert args.math is False


def test_verify_distribution_arguments_accept_math_extra(
    verify_distributions: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["verify-distributions.py", "--expected-version", "0.4.0", "--math"],
    )

    assert verify_distributions.parse_args().math is True


def test_math_smoke_removes_node_from_path(
    verify_distributions: Any, tmp_path: Path
) -> None:
    node_dir = tmp_path / "node"
    clean_dir = tmp_path / "clean"
    node_dir.mkdir()
    clean_dir.mkdir()
    (node_dir / "node").touch()
    (node_dir / "nodejs").touch()

    assert verify_distributions.path_without_node(
        f"{node_dir}{os.pathsep}{clean_dir}"
    ) == str(clean_dir)


def test_math_smoke_omits_unreadable_path_entries(
    verify_distributions: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    blocked_dir = tmp_path / "blocked"
    clean_dir = tmp_path / "clean"
    clean_dir.mkdir()
    original_is_file = Path.is_file

    def checked_is_file(path: Path) -> bool:
        if path.parent == blocked_dir:
            raise PermissionError("directory is not readable")
        return original_is_file(path)

    monkeypatch.setattr(Path, "is_file", checked_is_file)

    assert verify_distributions.path_without_node(
        f"{blocked_dir}{os.pathsep}{clean_dir}"
    ) == str(clean_dir)


def test_math_smoke_installs_extra_and_sets_environment(
    verify_distributions: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[list[str], dict[str, str], str]] = []

    def record_run(
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        label: str,
    ) -> None:
        assert cwd.is_dir()
        calls.append((command, env, label))

    monkeypatch.setattr(verify_distributions, "run", record_run)
    wheel = tmp_path / "takumi_py-0.4.0-cp311-abi3-test.whl"
    repository_root = tmp_path / "repository"
    root = tmp_path / "smoke"
    repository_root.mkdir()
    root.mkdir()
    (repository_root / ".github" / "scripts").mkdir(parents=True)
    (repository_root / ".github" / "scripts" / "smoke-wheel.py").touch()

    verify_distributions.smoke_wheel(
        wheel,
        name="wheel",
        python_version="3.11",
        uv="uv",
        root=root,
        repository_root=repository_root,
        env={"PATH": ""},
        math_smoke=True,
    )

    assert calls[1][0][-1] == str(wheel.resolve())
    assert "TAKUMI_PY_MATH_SMOKE" not in calls[2][1]
    assert calls[3][0][-1] == f"{wheel.resolve()}[math]"
    assert calls[4][1]["TAKUMI_PY_MATH_SMOKE"] == "1"
    assert calls[4][1]["PATH"] == ""
