from __future__ import annotations

import importlib.util
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


@pytest.fixture(scope="module")
def wheel_tester() -> ModuleType:
    return load_script("test-wheel")


def test_test_wheel_arguments_accept_artifact_directory_and_report(
    wheel_tester: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "test-wheel.py",
            str(tmp_path),
            "--junit-xml",
            "reports/regressions.xml",
            "--python",
            "3.13",
            "--uv",
            "custom-uv",
        ],
    )

    args = wheel_tester.parse_args()

    assert args.wheel_or_directory == tmp_path
    assert args.junit_xml == Path("reports/regressions.xml")
    assert args.python == "3.13"
    assert args.uv == "custom-uv"


def test_test_wheel_resolves_one_wheel_from_a_file_or_directory(
    wheel_tester: ModuleType,
    tmp_path: Path,
) -> None:
    wheel = tmp_path / "takumi_py-0.4.0-cp311-abi3-test.whl"
    wheel.touch()

    assert wheel_tester.resolve_wheel(wheel) == wheel.resolve()
    assert wheel_tester.resolve_wheel(tmp_path) == wheel.resolve()

    (tmp_path / "takumi_py-0.4.1-cp311-abi3-test.whl").touch()
    with pytest.raises(wheel_tester.WheelTestError, match="exactly one wheel"):
        wheel_tester.resolve_wheel(tmp_path)


def test_test_wheel_uses_the_explicit_regression_suite(
    wheel_tester: ModuleType,
) -> None:
    assert wheel_tester.REGRESSION_TESTS == (
        "test_native_stack.py",
        "test_node_bytes.py",
        "test_render_node.py",
        "test_keyframe_options.py",
        "test_stylesheet_composition.py",
    )


def test_test_wheel_environment_removes_inherited_import_configuration(
    wheel_tester: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PATH", "/test/bin")
    for name in (
        "PYTHONHOME",
        "PYTHONPATH",
        "PYTEST_ADDOPTS",
        "PYTEST_PLUGINS",
        "UV_PROJECT_ENVIRONMENT",
        "VIRTUAL_ENV",
    ):
        monkeypatch.setenv(name, "/checkout/shadow")

    env = wheel_tester.isolated_environment()

    assert env["PATH"] == "/test/bin"
    assert env["PYTHONNOUSERSITE"] == "1"
    assert env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
    assert env["UV_NO_PROGRESS"] == "1"
    for name in (
        "PYTHONHOME",
        "PYTHONPATH",
        "PYTEST_ADDOPTS",
        "PYTEST_PLUGINS",
        "UV_PROJECT_ENVIRONMENT",
        "VIRTUAL_ENV",
    ):
        assert name not in env


def test_test_wheel_installs_and_runs_only_the_selected_suite(
    wheel_tester: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    wheel = tmp_path / "takumi_py-0.4.0-cp311-abi3-test.whl"
    wheel.touch()
    report = tmp_path / "reports" / "regressions.xml"
    repository_root = tmp_path / "repository"
    source_tests = repository_root / "tests"
    script_path = repository_root / ".github" / "scripts" / "test-wheel.py"
    source_tests.mkdir(parents=True)
    script_path.parent.mkdir(parents=True)
    script_path.touch()
    for name in wheel_tester.REGRESSION_TESTS:
        source_tests.joinpath(name).touch()
    uv_calls: list[tuple[list[str], Path, dict[str, str]]] = []
    probes: list[tuple[list[str], Path, dict[str, str]]] = []
    pytest_calls: list[tuple[Path, Path, Path, dict[str, str]]] = []

    def record_run(
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        label: str,
    ) -> None:
        assert label
        assert cwd.is_dir()
        uv_calls.append((command, cwd, env))

    def record_probe(
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        label: str,
    ) -> None:
        assert label
        assert cwd.is_dir()
        probes.append((command, cwd, env))

    def record_pytest(
        *,
        python: Path,
        suite_dir: Path,
        junit_xml: Path,
        env: dict[str, str],
    ) -> int:
        assert not suite_dir.is_relative_to(tmp_path / "repository")
        assert sorted(path.name for path in suite_dir.iterdir()) == sorted(
            (*wheel_tester.REGRESSION_TESTS, "pytest.ini")
        )
        assert not (suite_dir / "pyproject.toml").exists()
        assert (suite_dir / "pytest.ini").read_text(encoding="utf-8") == "[pytest]\n"
        pytest_calls.append((python, suite_dir, junit_xml, env))
        return 5

    monkeypatch.setattr(wheel_tester, "run", record_run)
    monkeypatch.setattr(wheel_tester, "run_probe", record_probe)
    monkeypatch.setattr(wheel_tester, "run_pytest", record_pytest)
    monkeypatch.setattr(
        wheel_tester,
        "__file__",
        str(script_path),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "test-wheel.py",
            str(wheel),
            "--junit-xml",
            str(report),
            "--python",
            "3.12",
            "--uv",
            "custom-uv",
        ],
    )

    wheel_tester.main()

    assert len(uv_calls) == 2
    venv_command = uv_calls[0][0]
    assert venv_command[:5] == [
        "custom-uv",
        "venv",
        "--no-project",
        "--python",
        "3.12",
    ]
    venv = Path(venv_command[-1])
    install_command = uv_calls[1][0]
    assert install_command == [
        "custom-uv",
        "pip",
        "install",
        "--python",
        str(wheel_tester.venv_python(venv)),
        str(wheel.resolve()),
        "pytest==9.1.1",
    ]
    assert all("pytest-cov" not in argument for argument in install_command)
    assert all("pytest-xdist" not in argument for argument in install_command)

    expected_python = wheel_tester.venv_python(venv)
    (python, suite_dir, junit_xml, env) = pytest_calls[0]
    assert python == expected_python
    assert junit_xml == report.resolve()
    assert env["PYTHONNOUSERSITE"] == "1"
    assert "PYTHONPATH" not in env
    assert probes[0][0] == [
        str(expected_python),
        "-I",
        "-c",
        wheel_tester.WHEEL_PROBE,
    ]
    assert suite_dir.name == "tests"


def test_test_wheel_rejects_skipped_junit_cases(
    wheel_tester: ModuleType,
    tmp_path: Path,
) -> None:
    report = tmp_path / "regressions.xml"
    report.write_text(
        """\
<testsuites>
  <testsuite tests="2" skipped="1">
    <testcase classname="tests.test_render_node" name="test_render" />
    <testcase classname="tests.test_keyframe_options" name="test_keyframes">
      <skipped message="regression unavailable" />
    </testcase>
  </testsuite>
</testsuites>
""",
        encoding="utf-8",
    )

    with pytest.raises(wheel_tester.WheelTestError, match="tests were skipped"):
        wheel_tester.check_junit(report)


def test_test_wheel_preserves_junit_when_pytest_fails(
    wheel_tester: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    python = tmp_path / "venv" / "bin" / "python"
    suite_dir = tmp_path / "tests"
    suite_dir.mkdir()
    report = tmp_path / "regressions.xml"

    def failed_pytest(
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        check: bool,
        stdout: Any,
        stderr: int,
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        assert cwd == suite_dir
        assert check is False
        assert env == {}
        assert stderr == subprocess.STDOUT
        assert timeout == wheel_tester.PYTEST_TIMEOUT_SECONDS
        stdout.write("collected selected regressions\n")
        report.write_text(
            """\
<testsuites>
  <testsuite tests="1" failures="1">
    <testcase classname="tests.test_render_node" name="test_render">
      <failure message="failed" />
    </testcase>
  </testsuite>
</testsuites>
""",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(wheel_tester.subprocess, "run", failed_pytest)

    with pytest.raises(wheel_tester.WheelTestError, match="failed with exit code 1"):
        wheel_tester.run_pytest(
            python=python,
            suite_dir=suite_dir,
            junit_xml=report,
            env={},
        )

    assert report.is_file()
    assert "<failure" in report.read_text(encoding="utf-8")
    log_path = report.with_suffix(".log")
    assert "collected selected regressions" in log_path.read_text(encoding="utf-8")


def test_test_wheel_preserves_log_when_pytest_times_out(
    wheel_tester: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    python = tmp_path / "venv" / "bin" / "python"
    suite_dir = tmp_path / "tests"
    suite_dir.mkdir()
    report = tmp_path / "regressions.xml"

    def timed_out_pytest(
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        check: bool,
        stdout: Any,
        stderr: int,
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        assert cwd == suite_dir
        assert check is False
        assert env == {}
        assert stderr == subprocess.STDOUT
        stdout.write("partial regression output\n")
        raise subprocess.TimeoutExpired(command, timeout)

    monkeypatch.setattr(wheel_tester.subprocess, "run", timed_out_pytest)

    with pytest.raises(wheel_tester.WheelTestError, match="exceeded 900 seconds"):
        wheel_tester.run_pytest(
            python=python,
            suite_dir=suite_dir,
            junit_xml=report,
            env={},
        )

    log = report.with_suffix(".log").read_text(encoding="utf-8")
    assert "partial regression output" in log
    assert "exceeded 900 seconds" in log
