#!/usr/bin/env python3
"""Verify built distributions and exercise them outside the source checkout."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import NoReturn


class DistributionVerificationError(RuntimeError):
    """A built artifact does not satisfy the release contract."""


def fail(message: str) -> NoReturn:
    raise DistributionVerificationError(message)


def log(message: str) -> None:
    sys.stdout.write(f"{message}\n")
    sys.stdout.flush()


def only_artifact(paths: list[Path], kind: str) -> Path:
    if len(paths) != 1:
        found = ", ".join(sorted(path.name for path in paths)) or "none"
        fail(f"expected exactly one {kind}, found {len(paths)}: {found}")
    return paths[0]


def run(command: list[str], *, cwd: Path, env: dict[str, str], label: str) -> None:
    log(f"==> {label}")
    try:
        subprocess.run(command, cwd=cwd, env=env, check=True)  # noqa: S603
    except subprocess.CalledProcessError as error:
        fail(f"{label} failed with exit code {error.returncode}")


def venv_python(venv: Path) -> Path:
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def check_archives(
    paths: list[Path],
    *,
    expected_version: str,
    allow_native_wheel_tag: bool = False,
    repository_root: Path,
    env: dict[str, str],
) -> None:
    run(
        [
            sys.executable,
            str(repository_root / ".github/scripts/check-distributions.py"),
            "--version",
            expected_version,
            *(["--allow-native-wheel-tag"] if allow_native_wheel_tag else []),
            *(str(path) for path in paths),
        ],
        cwd=repository_root,
        env=env,
        label="Validate distribution metadata and archive contents",
    )


def smoke_wheel(
    wheel: Path,
    *,
    name: str,
    python_version: str,
    uv: str,
    root: Path,
    repository_root: Path,
    env: dict[str, str],
) -> None:
    venv = root / name
    run_dir = root / f"{name}-run"
    run_dir.mkdir()
    run(
        [uv, "venv", "--no-project", "--python", python_version, str(venv)],
        cwd=run_dir,
        env=env,
        label=f"Create isolated {name} environment",
    )
    python = venv_python(venv)
    run(
        [uv, "pip", "install", "--python", str(python), str(wheel.resolve())],
        cwd=run_dir,
        env=env,
        label=f"Install {wheel.name} in isolation",
    )
    smoke_env = env | {"TAKUMI_PY_REPOSITORY_ROOT": str(repository_root)}
    run(
        [str(python), str(repository_root / ".github/scripts/smoke-wheel.py")],
        cwd=run_dir,
        env=smoke_env,
        label=f"Smoke {wheel.name} outside the source checkout",
    )


def rebuild_and_smoke_sdist(
    sdist: Path,
    *,
    expected_version: str,
    python_version: str,
    uv: str,
    root: Path,
    repository_root: Path,
    env: dict[str, str],
) -> None:
    wheel_dir = root / "from-sdist"
    run_dir = root / "sdist-build"
    run_dir.mkdir()
    run(
        [
            uv,
            "build",
            "--wheel",
            str(sdist.resolve()),
            "--out-dir",
            str(wheel_dir),
        ],
        cwd=run_dir,
        env=env,
        label=f"Build a wheel from {sdist.name}",
    )
    wheel = only_artifact(list(wheel_dir.glob("*.whl")), "sdist-built wheel")
    check_archives(
        [wheel],
        expected_version=expected_version,
        allow_native_wheel_tag=True,
        repository_root=repository_root,
        env=env,
    )
    smoke_wheel(
        wheel,
        name="sdist-wheel",
        python_version=python_version,
        uv=uv,
        root=root,
        repository_root=repository_root,
        env=env,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dist_dir", nargs="?", default=Path("dist"), type=Path)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--python", default="3.10")
    parser.add_argument("--uv", default=os.environ.get("UV", "uv"))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--wheel-only", action="store_true")
    mode.add_argument("--sdist-only", action="store_true")
    parser.add_argument("--sdist-built-wheel", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.sdist_built_wheel and not args.wheel_only:
        fail("--sdist-built-wheel requires --wheel-only")
    dist_dir = args.dist_dir.expanduser().resolve()
    if not dist_dir.is_dir():
        fail(f"distribution directory does not exist: {dist_dir}")

    wheels = list(dist_dir.glob("*.whl"))
    sdists = list(dist_dir.glob("*.tar.gz"))
    wheel = None if args.sdist_only else only_artifact(wheels, "wheel")
    sdist = None if args.wheel_only else only_artifact(sdists, "source distribution")
    selected = [path for path in (wheel, sdist) if path is not None]

    repository_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    for inherited_name in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"):
        env.pop(inherited_name, None)
    env.update(
        {
            "PYTHONNOUSERSITE": "1",
            "TAKUMI_PY_EXPECTED_VERSION": args.expected_version,
            "UV_NO_PROGRESS": "1",
        }
    )
    check_archives(
        selected,
        expected_version=args.expected_version,
        allow_native_wheel_tag=args.sdist_built_wheel,
        repository_root=repository_root,
        env=env,
    )

    with TemporaryDirectory(prefix="takumi-py-dist-smoke-") as temporary:
        root = Path(temporary).resolve()
        if wheel is not None:
            smoke_wheel(
                wheel,
                name="wheel",
                python_version=args.python,
                uv=args.uv,
                root=root,
                repository_root=repository_root,
                env=env,
            )
        if sdist is not None:
            rebuild_and_smoke_sdist(
                sdist,
                expected_version=args.expected_version,
                python_version=args.python,
                uv=args.uv,
                root=root,
                repository_root=repository_root,
                env=env,
            )
    log("Distribution verification passed.")


if __name__ == "__main__":
    try:
        main()
    except DistributionVerificationError as error:
        sys.stderr.write(f"Distribution verification failed: {error}\n")
        raise SystemExit(1) from None
