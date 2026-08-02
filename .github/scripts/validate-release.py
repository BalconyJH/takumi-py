from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

TAG_PATTERN = re.compile(r"v(?P<version>[0-9]+[.][0-9]+[.][0-9]+)")


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


def validate_changelog(version: str) -> None:
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    pattern = re.compile(
        rf"^## \[{re.escape(version)}\] - [0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}$",
        re.MULTILINE,
    )
    if pattern.search(changelog) is None:
        raise SystemExit(f"CHANGELOG.md has no dated {version} release heading")


def write_outputs(tag: str, commit: str, version: str, *, publish: bool) -> None:
    lines = (
        f"tag={tag}\nsha={commit}\nversion={version}\npublish={str(publish).lower()}\n"
    )
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path is None:
        sys.stdout.write(lines)
        return
    with Path(output_path).open("a", encoding="utf-8") as output:
        output.write(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--main-ref", default="origin/main")
    args = parser.parse_args()

    match = TAG_PATTERN.fullmatch(args.tag)
    if match is None:
        raise SystemExit(f"release tag must match vX.Y.Z, got {args.tag}")
    version = match.group("version")

    commit = run("git", "rev-parse", f"{args.tag}^{{commit}}")
    head = run("git", "rev-parse", "HEAD")
    if head != commit:
        raise SystemExit(f"HEAD {head} does not match release tag commit {commit}")
    run("git", "rev-parse", "--verify", args.main_ref)

    python_version = run("uv", "version", "--short")
    rust_version = cargo_version()
    if python_version != version:
        raise SystemExit(
            f"release tag version {version} does not match pyproject version {python_version}"
        )
    if rust_version != version:
        raise SystemExit(
            f"release tag version {version} does not match Cargo version {rust_version}"
        )

    if not is_ancestor(commit, args.main_ref):
        sys.stderr.write(
            f"::notice::Skipping release because {args.tag} points to {commit}, "
            f"which is not on {args.main_ref}\n"
        )
        write_outputs(args.tag, commit, version, publish=False)
        return

    run("uv", "lock", "--check")
    validate_changelog(version)
    write_outputs(args.tag, commit, version, publish=True)


if __name__ == "__main__":
    main()
