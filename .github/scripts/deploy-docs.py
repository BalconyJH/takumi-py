#!/usr/bin/env python3
"""Deploy one documentation version to the gh-pages branch with mike.

Each language the checkout ships deploys with its own configuration: English at the
branch root and Simplified Chinese under ``zh/``, each with its own ``versions.json``.
A release (``--release``) also moves the ``latest`` alias and the site default when
it is not older than the newest released version. Pushes that lose a race with
another deployment fetch gh-pages again and retry.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from packaging.version import InvalidVersion, Version

ATTEMPTS = 3
LANGUAGES = (("zensical.toml", None), ("zensical.zh.toml", "zh"))


class DeployError(RuntimeError):
    """A mike or git command failed."""


def log(message: str) -> None:
    sys.stdout.write(f"{message}\n")
    sys.stdout.flush()
    if log_file := os.environ.get("DEPLOY_LOG"):
        with Path(log_file).open("a", encoding="utf-8") as file:
            file.write(f"{message}\n")


def run(*command: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    log(f"$ {' '.join(command)}")
    result = subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603
    for line in (result.stdout + result.stderr).splitlines():
        log(f"  {line}")
    if check and result.returncode != 0:
        raise DeployError(f"{command[0]} {command[1]} exited with {result.returncode}")
    return result


def reset_gh_pages() -> None:
    """Point the local gh-pages branch at the remote one, if the remote has it."""
    local = run(
        "git", "rev-parse", "--verify", "--quiet", "refs/heads/gh-pages", check=False
    )
    if local.returncode == 0:
        run("git", "branch", "--delete", "--force", "gh-pages")
    remote = run(
        "git", "ls-remote", "--exit-code", "--heads", "origin", "gh-pages", check=False
    )
    if remote.returncode == 0:
        run("git", "fetch", "--force", "origin", "gh-pages:gh-pages")


def newest_release() -> Version | None:
    """The newest PEP 440 version in the English versions.json; `dev` is not one."""
    shown = run("git", "show", "gh-pages:versions.json", check=False)
    if shown.returncode != 0:
        return None
    releases = []
    for entry in json.loads(shown.stdout):
        try:
            releases.append(Version(entry["version"]))
        except InvalidVersion:
            continue
    return max(releases, default=None)


def deploy_once(version: str, title: str | None, *, release: bool) -> None:
    reset_gh_pages()
    move_latest = False
    if release:
        newest = newest_release()
        move_latest = newest is None or Version(version) >= newest
        log(
            f"Docs version {version}; newest release {newest}; move latest: {move_latest}."
        )

    for config, prefix in LANGUAGES:
        if not Path(config).is_file():
            continue
        options = ["--config-file", config]
        if prefix:
            options += ["--deploy-prefix", prefix]
        deploy = ["mike", "deploy", *options]
        if title:
            deploy += ["--title", title]
        if move_latest:
            run(*deploy, "--update-aliases", version, "latest")
            run("mike", "set-default", *options, "latest")
        else:
            run(*deploy, version)
            # A language with no release yet opens this version until a release does.
            default = f"{prefix}/index.html" if prefix else "index.html"
            if run(
                "git", "cat-file", "-e", f"gh-pages:{default}", check=False
            ).returncode:
                run("mike", "set-default", *options, version)
        manifest = f"{prefix}/versions.json" if prefix else "versions.json"
        run("git", "cat-file", "-e", f"gh-pages:{manifest}")

    run("git", "push", "origin", "gh-pages:gh-pages")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deploy a documentation version to gh-pages with mike."
    )
    parser.add_argument("version", help="version to deploy, such as 0.4.0 or dev")
    parser.add_argument("--title", help="title shown in the version selector")
    parser.add_argument(
        "--release",
        action="store_true",
        help="move `latest` and the default here when this is the newest release",
    )
    args = parser.parse_args()

    for attempt in range(1, ATTEMPTS + 1):
        log(f"Deployment attempt {attempt}/{ATTEMPTS}")
        try:
            deploy_once(args.version, args.title, release=args.release)
        except DeployError as error:
            log(f"Attempt {attempt} failed: {error}")
            if attempt < ATTEMPTS:
                time.sleep(attempt * 2)
            continue
        log(f"Deployed docs version {args.version}.")
        return 0

    sys.stderr.write(
        f"::error::Failed to deploy docs version {args.version} after {ATTEMPTS} attempts.\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
