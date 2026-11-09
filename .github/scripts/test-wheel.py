#!/usr/bin/env python3
"""Run installed-wheel regressions outside the source checkout."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from typing import NoReturn
from xml.etree import ElementTree as ET

PYTEST_REQUIREMENT = "pytest==9.1.1"
PYTEST_TIMEOUT_SECONDS = 900
REGRESSION_TESTS = (
    "test_native_stack.py",
    "test_node_bytes.py",
    "test_render_node.py",
    "test_keyframe_options.py",
    "test_stylesheet_composition.py",
)
WHEEL_PROBE = """\
from importlib.metadata import version
from pathlib import Path
import sys

import takumi_py
from takumi_py import _core

prefix = Path(sys.prefix).resolve()
for module in (takumi_py, _core):
    origin = Path(module.__file__).resolve()
    if not origin.is_relative_to(prefix):
        raise SystemExit(f"{module.__name__} loaded outside the test venv: {origin}")

print(f"takumi-py {version('takumi-py')} from {prefix}")
"""


class WheelTestError(RuntimeError):
    """The installed wheel failed the cross-platform regression contract."""


def fail(message: str) -> NoReturn:
    raise WheelTestError(message)


def log(message: str) -> None:
    sys.stdout.write(f"{message}\n")
    sys.stdout.flush()


def venv_python(venv: Path) -> Path:
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def resolve_wheel(path_or_directory: Path) -> Path:
    path = path_or_directory.expanduser()
    if path.is_dir():
        wheels = sorted(path.glob("*.whl"))
        if len(wheels) != 1:
            found = ", ".join(wheel.name for wheel in wheels) or "none"
            fail(
                "expected exactly one wheel in "
                f"{path.resolve()}, found {len(wheels)}: {found}"
            )
        return wheels[0].resolve()
    if not path.is_file():
        fail(f"wheel path does not exist: {path}")
    if path.suffix.lower() != ".whl":
        fail(f"expected a wheel file, found: {path}")
    return path.resolve()


def isolated_environment() -> dict[str, str]:
    env = os.environ.copy()
    for name in (
        "PYTHONHOME",
        "PYTHONPATH",
        "PYTEST_ADDOPTS",
        "PYTEST_PLUGINS",
        "UV_PROJECT_ENVIRONMENT",
        "VIRTUAL_ENV",
    ):
        env.pop(name, None)
    env.update(
        {
            "PYTHONNOUSERSITE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "UV_NO_PROGRESS": "1",
        }
    )
    return env


def run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    label: str,
) -> None:
    log(f"==> {label}")
    try:
        completed = subprocess.run(command, cwd=cwd, env=env, check=False)  # noqa: S603
    except OSError as error:
        fail(f"{label} could not start: {error}")
    if completed.returncode != 0:
        fail(f"{label} failed with exit code {completed.returncode}")


def run_probe(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    label: str,
) -> None:
    log(f"==> {label}")
    try:
        completed = subprocess.run(  # noqa: S603
            command,
            cwd=cwd,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        fail(f"{label} could not start: {error}")
    if completed.stdout:
        sys.stdout.write(completed.stdout)
    if completed.stderr:
        sys.stderr.write(completed.stderr)
    if completed.returncode != 0:
        fail(f"{label} failed with exit code {completed.returncode}")


def copy_regression_tests(repository_root: Path, destination: Path) -> list[str]:
    source_root = repository_root / "tests"
    missing = [name for name in REGRESSION_TESTS if not (source_root / name).is_file()]
    if missing:
        fail(f"missing selected regression tests: {', '.join(missing)}")
    destination.mkdir()
    (destination / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    for name in REGRESSION_TESTS:
        shutil.copy2(source_root / name, destination / name)
    return list(REGRESSION_TESTS)


def check_junit(report: Path) -> int:
    try:
        root = ET.parse(report).getroot()  # noqa: S314 - pytest wrote this report.
    except (ET.ParseError, OSError) as error:
        fail(f"could not read JUnit report {report}: {error}")

    test_cases = list(root.iter("testcase"))
    if not test_cases:
        fail(f"JUnit report contains no test cases: {report}")
    skipped = [
        test_case for test_case in test_cases if test_case.find("skipped") is not None
    ]
    if skipped:
        names = ", ".join(
            f"{test_case.get('classname', '')}::{test_case.get('name', '?')}"
            for test_case in skipped
        )
        fail(f"{len(skipped)} regression tests were skipped: {names}")
    return len(test_cases)


def run_pytest(
    *,
    python: Path,
    suite_dir: Path,
    junit_xml: Path,
    env: dict[str, str],
) -> int:
    junit_xml.unlink(missing_ok=True)
    log_path = junit_xml.with_suffix(".log")
    log_path.unlink(missing_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(python),
        "-I",
        "-m",
        "pytest",
        "--rootdir",
        str(suite_dir),
        "--config-file",
        str(suite_dir / "pytest.ini"),
        "--import-mode=importlib",
        "--strict-config",
        "--strict-markers",
        "-p",
        "no:cacheprovider",
        f"--junitxml={junit_xml}",
        *(str(suite_dir / name) for name in REGRESSION_TESTS),
    ]
    log("==> Run selected regressions against the installed wheel")
    startup_error: OSError | None = None
    timed_out = False
    with log_path.open("w", encoding="utf-8") as output:
        try:
            completed = subprocess.run(  # noqa: S603
                command,
                cwd=suite_dir,
                env=env,
                check=False,
                stdout=output,
                stderr=subprocess.STDOUT,
                timeout=PYTEST_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            timed_out = True
            output.write(
                f"\nRegression pytest exceeded {PYTEST_TIMEOUT_SECONDS} seconds.\n"
            )
        except OSError as error:
            startup_error = error
            output.write(f"Regression pytest could not start: {error}\n")

    sys.stdout.write(log_path.read_text(encoding="utf-8", errors="replace"))
    sys.stdout.flush()
    if timed_out:
        fail(
            f"regression pytest exceeded {PYTEST_TIMEOUT_SECONDS} seconds; "
            f"log: {log_path}"
        )
    if startup_error is not None:
        fail(f"regression pytest could not start: {startup_error}; log: {log_path}")
    if not junit_xml.is_file():
        fail(
            "regression pytest did not produce the required JUnit report: "
            f"{junit_xml}; log: {log_path}"
        )
    if completed.returncode != 0:
        fail(
            "regression pytest failed with exit code "
            f"{completed.returncode}; JUnit report: {junit_xml}; log: {log_path}"
        )
    return check_junit(junit_xml)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "wheel_or_directory",
        type=Path,
        help="wheel path or artifact directory containing exactly one wheel",
    )
    parser.add_argument("--junit-xml", required=True, type=Path)
    parser.add_argument("--python", default="3.11")
    parser.add_argument("--uv", default=os.environ.get("UV", "uv"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    wheel = resolve_wheel(args.wheel_or_directory)
    junit_xml = args.junit_xml.expanduser().resolve()
    junit_xml.parent.mkdir(parents=True, exist_ok=True)
    repository_root = Path(__file__).resolve().parents[2]
    env = isolated_environment()

    with TemporaryDirectory(prefix="takumi-py-wheel-tests-") as temporary:
        root = Path(temporary).resolve()
        if root.is_relative_to(repository_root):
            fail(f"temporary test root is inside the source checkout: {root}")

        run_dir = root / "run"
        suite_dir = root / "tests"
        venv = root / "venv"
        run_dir.mkdir()
        copied_tests = copy_regression_tests(repository_root, suite_dir)

        run(
            [args.uv, "venv", "--no-project", "--python", args.python, str(venv)],
            cwd=run_dir,
            env=env,
            label=f"Create isolated Python {args.python} environment",
        )
        python = venv_python(venv)
        run(
            [
                args.uv,
                "pip",
                "install",
                "--python",
                str(python),
                str(wheel),
                PYTEST_REQUIREMENT,
            ],
            cwd=run_dir,
            env=env,
            label=f"Install {wheel.name} and {PYTEST_REQUIREMENT}",
        )
        run_probe(
            [str(python), "-I", "-c", WHEEL_PROBE],
            cwd=run_dir,
            env=env,
            label="Prove the wheel loads from the isolated venv",
        )
        test_count = run_pytest(
            python=python,
            suite_dir=suite_dir,
            junit_xml=junit_xml,
            env=env,
        )

    log(
        f"Installed-wheel regressions passed: {test_count} tests from "
        f"{len(copied_tests)} files."
    )


if __name__ == "__main__":
    try:
        main()
    except WheelTestError as error:
        sys.stderr.write(f"Installed-wheel regression verification failed: {error}\n")
        raise SystemExit(1) from None
