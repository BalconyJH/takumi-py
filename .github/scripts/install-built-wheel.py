from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def main() -> None:
    wheel_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("dist")
    wheels = sorted(wheel_dir.glob("*.whl"))
    if len(wheels) != 1:
        wheel_list = ", ".join(str(path) for path in wheels) or "<none>"
        raise SystemExit(
            f"expected exactly one wheel in {wheel_dir}, found {wheel_list}"
        )

    subprocess.check_call(  # noqa: S603
        [sys.executable, "-m", "pip", "install", "--force-reinstall", str(wheels[0])]
    )


if __name__ == "__main__":
    main()
