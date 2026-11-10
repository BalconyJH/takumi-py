from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MATHJAX_BUILD_INPUTS = (
    "tools/mathjax/build.mjs",
    "tools/mathjax/bun.lock",
    "tools/mathjax/mathjax-entry.mjs",
    "tools/mathjax/package.json",
)
MATHJAX_BUNDLE = "python/takumi_py/math/assets/mathjax.bundle.js"
MATHJAX_MANIFEST = "python/takumi_py/math/assets/manifest.json"


def _git_blob(path: str, *, apply_checkout_filters: bool = False) -> bytes:
    command = ["git"]
    if apply_checkout_filters:
        command.extend(("-c", "core.autocrlf=true", "cat-file", "--filters"))
    else:
        command.extend(("cat-file", "blob"))
    command.append(f"HEAD:{path}")
    completed = subprocess.run(  # noqa: S603 - fixed Git command and repository paths.
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return completed.stdout


def test_mathjax_checkout_preserves_manifest_bytes() -> None:
    for path in (*MATHJAX_BUILD_INPUTS, MATHJAX_BUNDLE):
        stored = _git_blob(path)
        checked_out = _git_blob(path, apply_checkout_filters=True)
        assert checked_out == stored, f"{path} changed during checkout"

    manifest = json.loads(_git_blob(MATHJAX_MANIFEST))
    bundle = _git_blob(MATHJAX_BUNDLE, apply_checkout_filters=True)
    assert len(bundle) == manifest["bundle"]["bytes"]
    assert hashlib.sha256(bundle).hexdigest() == manifest["bundle"]["sha256"]
    assert (
        hashlib.sha256(_git_blob("tools/mathjax/mathjax-entry.mjs")).hexdigest()
        == manifest["build"]["entry_sha256"]
    )
    assert (
        hashlib.sha256(_git_blob("tools/mathjax/bun.lock")).hexdigest()
        == manifest["build"]["lock_sha256"]
    )
