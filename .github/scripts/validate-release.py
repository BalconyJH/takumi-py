"""Check that the checkout satisfies the release contract for a version or a tag.

``--version`` checks the source before ``Release · Tag`` creates a tag; ``--tag``
also checks that the tag points at the checkout and lies on ``main``, and writes the
release outputs ``Release · Publish`` uses.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

# A final release, or an alpha, beta, or release candidate of one. Cargo spells the
# same versions as SemVer prereleases: 0.4.0a1, 0.4.0b1, 0.4.0rc1 are 0.4.0-alpha.1,
# 0.4.0-beta.1, 0.4.0-rc.1.
VERSION_PATTERN = re.compile(
    r"(?P<release>[0-9]+[.][0-9]+[.][0-9]+)(?:(?P<phase>a|b|rc)(?P<number>[0-9]+))?"
)
CARGO_PHASES = {"a": "alpha", "b": "beta", "rc": "rc"}


def parse_version(version: str) -> re.Match[str]:
    match = VERSION_PATTERN.fullmatch(version)
    if match is None or re.search(r"(?:^|[.a-z])0[0-9]", version):
        raise SystemExit(
            f"release version must be X.Y.Z, X.Y.ZaN, X.Y.ZbN, or X.Y.ZrcN, got {version}"
        )
    return match


def cargo_spelling(version: str) -> str:
    """The SemVer version Cargo.toml uses for a release version."""
    match = parse_version(version)
    if match["phase"] is None:
        return match["release"]
    return f"{match['release']}-{CARGO_PHASES[match['phase']]}.{match['number']}"


def is_prerelease(version: str) -> bool:
    return parse_version(version)["phase"] is not None


def run(*command: str) -> str:
    try:
        result = subprocess.run(  # noqa: S603
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout).strip()
        message = f"command failed: {' '.join(command)}"
        if detail:
            message = f"{message}\n{detail}"
        raise SystemExit(message) from error
    return result.stdout.strip()


def is_ancestor(commit: str, main_ref: str) -> bool:
    result = subprocess.run(  # noqa: S603
        ("git", "merge-base", "--is-ancestor", commit, main_ref),  # noqa: S607
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode not in {0, 1}:
        detail = (result.stderr or result.stdout).strip()
        raise SystemExit(f"failed to compare {commit} with {main_ref}: {detail}")
    return result.returncode == 0


def cargo_version() -> str:
    metadata = json.loads(
        run("cargo", "metadata", "--locked", "--no-deps", "--format-version", "1")
    )
    workspace_root = Path(metadata["workspace_root"]).resolve()
    manifest_path = workspace_root / "Cargo.toml"
    packages = [
        package
        for package in metadata["packages"]
        if Path(package["manifest_path"]).resolve() == manifest_path
    ]
    if len(packages) != 1:
        raise SystemExit(
            f"expected one root Cargo package at {manifest_path}, found {len(packages)}"
        )
    return str(packages[0]["version"])


def validate_changelog(text: str, version: str) -> None:
    """Require the dated section `make changelog` writes, with its commit list."""
    heading = re.search(
        rf"^## \[{re.escape(version)}\] - [0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}$",
        text,
        re.MULTILINE,
    )
    if heading is None:
        raise SystemExit(f"CHANGELOG.md has no dated {version} release heading")
    following = re.compile(r"^## ", re.MULTILINE).search(text, heading.end())
    section = text[heading.end() : following.start() if following else len(text)]
    if re.search(r"^### Commits$", section, re.MULTILINE) is None:
        raise SystemExit(
            f"CHANGELOG.md {version} section has no generated `### Commits` list; "
            "write the entry with `make changelog`"
        )


def validate_source(version: str) -> None:
    """Check the versions, lock files, and changelog of the checkout."""
    python_version = run("uv", "version", "--short")
    if python_version != version:
        raise SystemExit(
            f"release version {version} does not match pyproject version {python_version}"
        )
    rust_version = cargo_version()
    if rust_version != cargo_spelling(version):
        raise SystemExit(
            f"Cargo version {rust_version} does not spell release version {version}; "
            f"expected {cargo_spelling(version)}"
        )
    run("uv", "lock", "--check")
    validate_changelog(Path("CHANGELOG.md").read_text(encoding="utf-8"), version)


def write_outputs(tag: str, commit: str, version: str, *, publish: bool) -> None:
    lines = (
        f"tag={tag}\nsha={commit}\nversion={version}\npublish={str(publish).lower()}\n"
        f"prerelease={str(is_prerelease(version)).lower()}\n"
    )
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path is None:
        sys.stdout.write(lines)
        return
    with Path(output_path).open("a", encoding="utf-8") as output:
        output.write(lines)


def validate_tag(tag: str, main_ref: str) -> None:
    if not tag.startswith("v"):
        raise SystemExit(f"release tag must be v followed by the version, got {tag}")
    version = tag.removeprefix("v")
    parse_version(version)

    commit = run("git", "rev-parse", f"{tag}^{{commit}}")
    head = run("git", "rev-parse", "HEAD")
    if head != commit:
        raise SystemExit(f"HEAD {head} does not match release tag commit {commit}")
    run("git", "rev-parse", "--verify", main_ref)

    if not is_ancestor(commit, main_ref):
        sys.stderr.write(
            f"::notice::Skipping release because {tag} points to {commit}, "
            f"which is not on {main_ref}\n"
        )
        write_outputs(tag, commit, version, publish=False)
        return

    validate_source(version)
    write_outputs(tag, commit, version, publish=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check the release contract for a version or a release tag."
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--tag", help="release tag to publish, such as v0.4.0")
    target.add_argument("--version", help="version to check before it is tagged")
    parser.add_argument("--main-ref", default="origin/main")
    args = parser.parse_args()

    if args.tag is not None:
        validate_tag(args.tag, args.main_ref)
        return
    parse_version(args.version)
    validate_source(args.version)
    sys.stdout.write(f"Source satisfies the release contract for {args.version}.\n")


if __name__ == "__main__":
    try:
        main()
    except SystemExit as error:
        # Surface contract violations as annotations on the workflow run.
        if isinstance(error.code, str) and os.environ.get("GITHUB_ACTIONS") == "true":
            raise SystemExit(f"::error::{error.code}") from None
        raise
