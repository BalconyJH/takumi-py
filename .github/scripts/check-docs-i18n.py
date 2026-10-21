#!/usr/bin/env python3
"""Check that the Simplified Chinese documentation mirrors the English source."""

from __future__ import annotations

import copy
from pathlib import Path
import re
import sys
import tomllib
from typing import Any
import unicodedata

ROOT = Path(__file__).resolve().parents[2]
ENGLISH_CONFIG = ROOT / "zensical.toml"
CHINESE_CONFIG = ROOT / "zensical.zh.toml"
ENGLISH_README = ROOT / "README.md"
CHINESE_README = ROOT / "README.zh-CN.md"

# Keys that legitimately differ between the two languages. Navigation is compared
# separately by structure, because only its titles are translated.
LANGUAGE_KEYS = (
    ("project", "site_description"),
    ("project", "site_url"),
    ("project", "edit_uri"),
    ("project", "docs_dir"),
    ("project", "site_dir"),
    ("project", "nav"),
    ("project", "theme", "language"),
    ("project", "extra", "alternate"),
)
COMPARED_FENCES = frozenset({"python", "bash"})

HEADING = re.compile(r"^(#{2,6})\s+(?P<text>.*?)\s*(?:\{\s*#(?P<id>[\w-]+)\s*\})?\s*$")
FENCE = re.compile(r"^(?P<indent>\s*)(?P<fence>```+|~~~+)(?P<info>[\w-]*)")


def load_config(path: Path) -> dict[str, Any]:
    with path.open("rb") as file:
        return tomllib.load(file)


def without_language_keys(config: dict[str, Any]) -> dict[str, Any]:
    stripped = copy.deepcopy(config)
    for key_path in LANGUAGE_KEYS:
        parent = stripped
        for key in key_path[:-1]:
            parent = parent.get(key, {})
        parent.pop(key_path[-1], None)
    for palette in stripped.get("project", {}).get("theme", {}).get("palette", []):
        palette.get("toggle", {}).pop("name", None)
    return stripped


def nav_structure(nav: Any) -> Any:
    """Drop navigation titles, keeping the nesting and page paths."""
    if isinstance(nav, list):
        return [nav_structure(item) for item in nav]
    if isinstance(nav, dict):
        return [nav_structure(value) for value in nav.values()]
    return nav


def slugify(text: str) -> str:
    """Python-Markdown's default `toc` slug for a heading's visible text."""
    text = re.sub(r"[`*]", "", text)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", text)


def scan_page(path: Path) -> tuple[list[tuple[str | None, str]], list[tuple[str, str]]]:
    """Return the page's (explicit id, text) headings and its compared blocks.

    Compared blocks are Python and Bash fences plus mkdocstrings `:::` directives, which
    both languages must share verbatim.
    """
    headings: list[tuple[str | None, str]] = []
    blocks: list[tuple[str, str]] = []
    fence: str | None = None
    indent = ""
    info = ""
    body: list[str] = []

    for line in path.read_text(encoding="utf-8").splitlines():
        if fence is None:
            opening = FENCE.match(line)
            if opening:
                fence = opening["fence"]
                indent = opening["indent"]
                info = opening["info"]
                body = []
                continue
            heading = HEADING.match(line)
            if heading:
                headings.append((heading["id"], heading["text"]))
            elif line.startswith(":::"):
                blocks.append(("mkdocstrings", line.strip()))
            continue

        if line.strip() == fence:
            if info in COMPARED_FENCES:
                blocks.append((info, "\n".join(body)))
            fence = None
            continue
        body.append(line.removeprefix(indent))

    return headings, blocks


def check_pages(english_dir: Path, chinese_dir: Path) -> list[str]:
    errors: list[str] = []
    english = {path.relative_to(english_dir) for path in english_dir.rglob("*.md")}
    chinese = {path.relative_to(chinese_dir) for path in chinese_dir.rglob("*.md")}

    errors.extend(
        f"{chinese_dir.name}/{page} is missing" for page in sorted(english - chinese)
    )
    errors.extend(
        f"{chinese_dir.name}/{page} has no English source"
        for page in sorted(chinese - english)
    )

    for page in sorted(english & chinese):
        english_headings, english_blocks = scan_page(english_dir / page)
        chinese_headings, chinese_blocks = scan_page(chinese_dir / page)
        english_ids = [explicit or slugify(text) for explicit, text in english_headings]
        chinese_ids = [explicit for explicit, _ in chinese_headings]

        if None in chinese_ids:
            errors.append(
                f"{chinese_dir.name}/{page}: every heading needs an explicit "
                "{ #id } matching the English anchor"
            )
        elif chinese_ids != english_ids:
            errors.append(
                f"{chinese_dir.name}/{page}: heading anchors {chinese_ids} "
                f"do not match English {english_ids}"
            )
        if chinese_blocks != english_blocks:
            errors.append(
                f"{chinese_dir.name}/{page}: code blocks or API directives differ "
                "from the English page"
            )

    return errors


def check_configs(english: dict[str, Any], chinese: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if without_language_keys(english) != without_language_keys(chinese):
        errors.append(
            f"{CHINESE_CONFIG.name} differs from {ENGLISH_CONFIG.name} outside "
            "its language-specific keys"
        )
    if nav_structure(english["project"]["nav"]) != nav_structure(
        chinese["project"]["nav"]
    ):
        errors.append("the two configurations declare different navigation")
    return errors


def main() -> int:
    english = load_config(ENGLISH_CONFIG)
    chinese = load_config(CHINESE_CONFIG)
    errors = check_configs(english, chinese)
    errors.extend(
        check_pages(
            ROOT / english["project"]["docs_dir"],
            ROOT / chinese["project"]["docs_dir"],
        )
    )
    if scan_page(ENGLISH_README)[1] != scan_page(CHINESE_README)[1]:
        errors.append(
            f"{CHINESE_README.name}: code blocks differ from {ENGLISH_README.name}"
        )

    for error in errors:
        sys.stderr.write(f"error: {error}\n")
    if errors:
        return 1
    sys.stdout.write("The Chinese documentation mirrors the English source.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
