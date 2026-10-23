#!/usr/bin/env python3
"""Set the project version in pyproject.toml, Cargo.toml, and both lock files.

Cargo.toml takes the SemVer spelling of the version, such as 0.4.0-rc.1 for 0.4.0rc1.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
CARGO_MANIFEST = ROOT / "Cargo.toml"
# The version line of the leading [package] table, before any other table starts.
PACKAGE_VERSION = re.compile(r'\A(\[package\]\n(?:[^\[\n].*\n|\n)*?)version = "[^"]*"')


def set_cargo_version(manifest: str, version: str) -> str:
    updated, count = PACKAGE_VERSION.subn(rf'\g<1>version = "{version}"', manifest)
    if count != 1:
        raise SystemExit("Cargo.toml has no [package] version to update")
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Set the project version in pyproject.toml, Cargo.toml, and locks."
    )
    parser.add_argument("version", help="release version, such as 0.4.0 or 0.4.0rc1")
    args = parser.parse_args()

    contract = runpy.run_path(str(Path(__file__).with_name("validate-release.py")))
    cargo_version = contract["cargo_spelling"](args.version)

    subprocess.run(  # noqa: S603
        ["uv", "version", "--no-sync", args.version],  # noqa: S607
        cwd=ROOT,
        check=True,
    )
    CARGO_MANIFEST.write_text(
        set_cargo_version(CARGO_MANIFEST.read_text(encoding="utf-8"), cargo_version),
        encoding="utf-8",
    )
    subprocess.run(
        ["cargo", "update", "--workspace", "--offline"],  # noqa: S607
        cwd=ROOT,
        check=True,
    )
    sys.stdout.write(f"Set the version to {args.version} (Cargo {cargo_version}).\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
