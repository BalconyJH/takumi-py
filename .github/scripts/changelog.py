#!/usr/bin/env python3
"""Generate CHANGELOG.md release entries and the GitHub Release notes taken from them.

``release`` dates the curated ``[Unreleased]`` section as the project version and
appends the release's commits, grouped by type with hash links, and its contributors,
using git-changelog to parse the conventional commit history. ``notes`` prints a
released section, which the release workflow publishes as the GitHub Release body.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import datetime as dt
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from git_changelog import Changelog, Commit, Version

ROOT = Path(__file__).resolve().parents[2]
CHANGELOG = ROOT / "CHANGELOG.md"
TEMPLATE = ROOT / ".github" / "changelog" / "commits.md.jinja"
UNRELEASED_HEADING = "## [Unreleased]"
VERSION_HEADING = re.compile(
    r"^## \[(?P<version>[^\]]+)\](?: - \d{4}-\d{2}-\d{2})?$", re.MULTILINE
)
NOREPLY_EMAIL = re.compile(r"^(?:\d+\+)?(?P<login>[^@]+)@users\.noreply\.github\.com$")
CO_AUTHOR = re.compile(r"^(?P<name>.+?)\s*<(?P<email>[^>]+)>$")
# GitHub commits merges and web edits as `web-flow`; it is not a contributor.
GITHUB_COMMITTER_EMAIL = "noreply@github.com"

# git-changelog section titles, in release-note order, with the heading each gets.
GROUPS = (
    ("Features", "Features"),
    ("Bug Fixes", "Bug fixes"),
    ("Performance Improvements", "Performance"),
    ("Reverts", "Reverts"),
    ("Code Refactoring", "Refactoring"),
    ("Docs", "Documentation"),
    ("Tests", "Tests"),
    ("Build", "Build"),
    ("Dependencies", "Dependencies"),
    ("Continuous Integration", "Continuous integration"),
    ("Chore", "Chores"),
    ("Style", "Style"),
    ("", "Other"),
)


class ChangelogError(RuntimeError):
    """The changelog or history does not allow the requested operation."""


@dataclass(frozen=True)
class Entry:
    label: str | None
    subject: str
    commit: Commit


@dataclass
class Group:
    title: str
    entries: list[Entry] = field(default_factory=list)


def project_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as file:
        return str(tomllib.load(file)["project"]["version"])


def section_bounds(text: str, heading: str) -> tuple[int, int]:
    """Return where the section under ``heading`` starts and where the next one does."""
    start = text.find(f"\n{heading}\n")
    if start == -1:
        raise ChangelogError(f"{CHANGELOG.name} has no {heading!r} section")
    body = start + len(heading) + 2
    following = VERSION_HEADING.search(text, body)
    return body, following.start() if following else len(text)


def released_section(text: str, version: str) -> str:
    match = re.search(
        rf"^## \[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}$", text, re.MULTILINE
    )
    if match is None:
        raise ChangelogError(f"{CHANGELOG.name} has no dated {version} release heading")
    following = VERSION_HEADING.search(text, match.end())
    end = following.start() if following else len(text)
    return text[match.end() : end].strip()


def subject_prefix(commit: Commit) -> str:
    """The `type(scope)` before a conventional subject, without its breaking `!`."""
    prefix, _, _ = commit.subject.partition(":")
    return prefix.rstrip("!")


def group_commits(version: Version) -> list[Group]:
    """Group a release's non-merge commits, breaking changes first, oldest first."""
    breaking = Group("Breaking changes")
    groups = {title: Group(heading) for title, heading in GROUPS}
    for commit in reversed(version.commits):
        if len(commit.parent_hashes) > 1:
            continue
        convention = commit.convention
        title = convention.get("type") or ""
        if convention.get("is_major"):
            breaking.entries.append(
                Entry(subject_prefix(commit), convention["subject"], commit)
            )
        elif title:
            groups[title].entries.append(
                Entry(convention.get("scope"), convention["subject"], commit)
            )
        else:
            prefix, separator, rest = commit.subject.partition(": ")
            groups[""].entries.append(
                Entry(
                    prefix if separator else None,
                    rest if separator else commit.subject,
                    commit,
                )
            )
    return [group for group in (breaking, *groups.values()) if group.entries]


class LoginResolver:
    """Map commit identities to GitHub logins through noreply emails or the API."""

    def __init__(self, repository: str, *, offline: bool) -> None:
        self.repository = repository
        self.offline = offline
        self.unresolved: set[str] = set()
        self._commits: dict[str, dict[str, str | None]] = {}

    def resolve(self, name: str, email: str, commit: str, role: str | None) -> str:
        """Return ``@login``, or ``name`` when the identity has no GitHub account."""
        if match := NOREPLY_EMAIL.match(email):
            return mention(match["login"])
        if role is not None and not self.offline:
            login = self._commit_logins(commit).get(role)
            if login:
                return mention(login)
        self.unresolved.add(f"{name} <{email}>")
        return name

    def _commit_logins(self, commit: str) -> dict[str, str | None]:
        if commit not in self._commits:
            try:
                output = subprocess.run(  # noqa: S603
                    [  # noqa: S607
                        "gh",
                        "api",
                        f"repos/{self.repository}/commits/{commit}",
                        "--jq",
                        "{author: .author.login, committer: .committer.login}",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout
            except (OSError, subprocess.CalledProcessError) as error:
                raise ChangelogError(
                    f"could not look up commit {commit[:7]} on GitHub ({error}); "
                    "authenticate with `gh auth login` or pass --offline"
                ) from error
            self._commits[commit] = json.loads(output)
        return self._commits[commit]


def mention(login: str) -> str:
    return f"@{login.removesuffix('[bot]')}"


def contributors(version: Version, resolver: LoginResolver) -> list[str]:
    """Authors, co-authors, and committers of the release, in first-commit order."""
    found: dict[str, None] = {}
    for commit in reversed(version.commits):
        identities = [
            (commit.author_name, commit.author_email, "author"),
            (commit.committer_name, commit.committer_email, "committer"),
        ]
        for trailer, value in commit.trailers:
            if trailer.lower() == "co-authored-by" and (
                match := CO_AUTHOR.match(value)
            ):
                identities.append((match["name"], match["email"], None))
        for name, email, role in identities:
            if email != GITHUB_COMMITTER_EMAIL:
                found[resolver.resolve(name, email, commit.hash, role)] = None
    return list(found)


def build_changelog(version: str) -> Changelog:
    from git_changelog import Changelog, ConventionalCommitConvention

    return Changelog(
        ROOT,
        convention=ConventionalCommitConvention,
        parse_trailers=True,
        bump=f"v{version}",
        include_all=True,
        versioning="pep440",
    )


def render_release(version: str, *, offline: bool) -> str:
    from git_changelog import get_custom_template

    changelog = build_changelog(version)
    unreleased = changelog.versions_list[0]
    if unreleased.tag or not unreleased.commits:
        raise ChangelogError(
            f"no unreleased commits since {unreleased.tag or 'the last tag'}"
        )

    provider = changelog.provider
    if provider is None:
        raise ChangelogError(
            "could not detect the GitHub repository from the git remote"
        )
    resolver = LoginResolver(
        f"{provider.namespace}/{provider.project}", offline=offline
    )
    rendered = get_custom_template(str(TEMPLATE)).render(
        version=unreleased,
        groups=group_commits(unreleased),
        contributors=contributors(unreleased, resolver),
    )
    for identity in sorted(resolver.unresolved):
        sys.stderr.write(f"warning: no GitHub account for {identity}; listed by name\n")
    return rendered.strip()


def release(version: str, date: str, *, offline: bool, dry_run: bool) -> None:
    text = CHANGELOG.read_text(encoding="utf-8")
    if re.search(rf"^## \[{re.escape(version)}\]", text, re.MULTILINE):
        raise ChangelogError(f"{CHANGELOG.name} already has a {version} section")

    start, end = section_bounds(text, UNRELEASED_HEADING)
    curated = text[start:end].strip()
    generated = render_release(version, offline=offline)
    body = f"{curated}\n\n{generated}" if curated else generated
    entry = f"## [{version}] - {date}\n\n{body}\n"

    if dry_run:
        sys.stdout.write(entry)
        return
    # Keep an empty [Unreleased] section above the new entry for the next release.
    head = text[: start - len(UNRELEASED_HEADING) - 1]
    rest = text[end:]
    CHANGELOG.write_text(
        f"{head}{UNRELEASED_HEADING}\n\n{entry}" + (f"\n{rest}" if rest else ""),
        encoding="utf-8",
    )
    sys.stdout.write(f"Dated [Unreleased] as {version} in {CHANGELOG.name}.\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate CHANGELOG.md release entries and GitHub Release notes."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    release_parser = commands.add_parser(
        "release", help="date [Unreleased] and append the release's commits"
    )
    release_parser.add_argument(
        "--version", help="release version (default: the pyproject.toml version)"
    )
    release_parser.add_argument(
        "--date",
        default=dt.datetime.now(dt.UTC).astimezone().date().isoformat(),
        help="release date (YYYY-MM-DD, default: today in the local time zone)",
    )
    release_parser.add_argument(
        "--offline",
        action="store_true",
        help="list contributors without a noreply email by name instead of asking GitHub",
    )
    release_parser.add_argument(
        "--dry-run", action="store_true", help="print the new entry without writing it"
    )

    notes_parser = commands.add_parser("notes", help="print a released section")
    notes_parser.add_argument("version", help="released version, without the v prefix")
    notes_parser.add_argument(
        "--changelog",
        type=Path,
        default=CHANGELOG,
        help="changelog to read, such as a release tag's (default: this checkout's)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "release":
            release(
                args.version or project_version(),
                args.date,
                offline=args.offline,
                dry_run=args.dry_run,
            )
        else:
            text = args.changelog.read_text(encoding="utf-8")
            sys.stdout.write(released_section(text, args.version) + "\n")
    except ChangelogError as error:
        sys.stderr.write(f"error: {error}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
