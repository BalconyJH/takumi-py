from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from importlib.metadata import version
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from typing import Any, cast

import takumi_py
from takumi_py import (
    Document,
    Fragment,
    ImageResource,
    LayoutOptions,
    RasterOptions,
    Renderer,
    ResourceSet,
    compile_document,
)

if "py_mini_racer" in sys.modules:
    raise SystemExit("importing takumi_py core loaded mini_racer eagerly")

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
SVG_1X1 = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1">'
    b'<path fill="currentColor" d="M0 0H1V1H0Z"/></svg>'
)


@contextmanager
def restrict_runtime_launches() -> Iterator[None]:
    """Deny every process launch except the supervised math worker."""

    original_popen = subprocess.Popen
    original_system = os.system

    def denied(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("math runtime attempted an unauthorized process launch")

    def replace(module: object, name: str, value: object) -> None:
        setattr(module, name, value)

    def restricted_popen(arguments: Any, *args: Any, **kwargs: Any) -> Any:
        executable = kwargs.get("executable")
        if (
            not _is_authorized_math_worker(arguments)
            or kwargs.get("shell", False)
            or kwargs.get("preexec_fn") is not None
            or (
                executable is not None
                and not _is_authorized_math_worker(
                    [
                        executable,
                        "-I",
                        "-u",
                        "-m",
                        "takumi_py.math._worker",
                    ]
                )
            )
        ):
            denied()
        return cast(Any, original_popen)(arguments, *args, **kwargs)

    replace(subprocess, "Popen", restricted_popen)
    replace(os, "system", denied)
    try:
        yield
    finally:
        replace(subprocess, "Popen", original_popen)
        replace(os, "system", original_system)


def _is_authorized_math_worker(arguments: object) -> bool:
    """Return whether arguments are exactly the packaged math worker command."""
    expected_arguments = (
        "-I",
        "-u",
        "-m",
        "takumi_py.math._worker",
    )
    if (
        not isinstance(arguments, (list, tuple))
        or len(arguments) != len(expected_arguments) + 1
    ):
        return False
    try:
        executable = os.path.normcase(str(Path(os.fspath(arguments[0])).resolve()))
    except TypeError:
        return False
    expected = os.path.normcase(str(Path(sys.executable).resolve()))
    return executable == expected and tuple(arguments[1:]) == expected_arguments


def smoke_core_math_optionality() -> None:
    """Prove math import is lazy and core-only installs report a clear failure."""
    import takumi_py.math as math_api

    if "py_mini_racer" in sys.modules:
        raise SystemExit("importing takumi_py.math loaded mini_racer eagerly")
    if os.environ.get("TAKUMI_PY_MATH_SMOKE") == "1":
        return

    with restrict_runtime_launches():
        try:
            with math_api.MathTypesetter() as typesetter:
                typesetter.typeset(
                    "x",
                    options=math_api.MathOptions(),
                )
        except math_api.MathRuntimeUnavailableError:
            return
        raise SystemExit(
            "core-only math runtime did not raise MathRuntimeUnavailableError"
        )


def smoke_document_resources(renderer: Renderer) -> None:
    logo = Fragment(
        {
            "type": "image",
            "src": "memory://wheel-smoke",
            "width": 2,
            "height": 2,
        },
        ResourceSet([ImageResource("memory://wheel-smoke", SVG_1X1)]),
    )
    compiled = compile_document(
        Document.from_node(
            {
                "type": "container",
                "style": {
                    "width": "4px",
                    "height": "4px",
                    "color": "#2563eb",
                },
                "children": [logo, logo],
            }
        )
    )
    layout = LayoutOptions(width=4, height=4)
    raw = renderer.render(
        compiled,
        layout=layout,
        output=RasterOptions(format="raw"),
    )
    if len(raw) != 4 * 4 * 4:
        raise SystemExit(
            f"compiled document resource render has unexpected size: {len(raw)}"
        )
    if len(compiled.resources.images) != 1:
        raise SystemExit("compiled document did not deduplicate fragment resources")

    document_svg = renderer.render_svg(compiled, layout=layout)
    if "data:image/svg+xml" not in document_svg:
        raise SystemExit("compiled document SVG did not reuse its image resource")


def smoke_math(renderer: Renderer) -> None:
    if shutil.which("node") is not None or shutil.which("nodejs") is not None:
        raise SystemExit("math smoke requires Node to be absent from PATH")

    import takumi_py.math as math_api

    if "py_mini_racer" in sys.modules:
        raise SystemExit("importing takumi_py.math loaded mini_racer eagerly")

    options = math_api.MathOptions(
        display=False,
        font_size_px=20,
        ex_ratio=0.5,
    )
    expression = (
        r"\begin{pmatrix}\frac{a}{b}&1\\0&\binom{n}{k}\end{pmatrix}"
        r"+\ce{2H2 -> 2H2O}"
    )
    with (
        restrict_runtime_launches(),
        math_api.MathTypesetter(extensions=("mhchem",)) as typesetter,
    ):
        result = typesetter.typeset(expression, options=options)
        second = typesetter.typeset(
            r"\ce{CO2 + H2O -> H2CO3}",
            options=options,
        )

    if not isinstance(result.data, bytes) or not result.data.startswith(b"<svg"):
        raise SystemExit("math smoke did not receive an inline SVG document")
    lowered = result.data.lower()
    if b"<path" not in lowered:
        raise SystemExit("math smoke SVG did not contain path glyphs")
    if b"<text" in lowered:
        raise SystemExit("math smoke SVG unexpectedly contains text elements")
    if b"currentcolor" not in lowered:
        raise SystemExit("math smoke SVG did not preserve currentColor")
    if not all(
        math.isfinite(value)
        for value in (result.width_px, result.height_px, result.depth_px)
    ):
        raise SystemExit("math smoke received non-finite geometry")
    if result.width_px <= 0 or result.height_px <= 0:
        raise SystemExit("math smoke received non-positive geometry")
    if result.display is not False:
        raise SystemExit("math smoke did not preserve display=False")
    if not isinstance(result.resource_id, str) or not result.resource_id:
        raise SystemExit("math smoke did not receive a stable-looking resource id")
    if not isinstance(second.data, bytes) or b"<path" not in second.data.lower():
        raise SystemExit("second mhchem formula did not produce path SVG")

    width = max(1, math.ceil(result.width_px))
    height = max(1, math.ceil(result.height_px))
    compiled = compile_document(
        Document.from_node(
            {
                "type": "container",
                "style": {
                    "display": "block",
                    "color": "red",
                },
                "children": [result.to_fragment()],
            }
        )
    )
    layout = LayoutOptions(width=width, height=height)
    raw = renderer.render(
        compiled,
        layout=layout,
        output=RasterOptions(format="raw"),
    )
    if not any(
        raw[index : index + 4] == b"\xff\x00\x00\xff" for index in range(0, len(raw), 4)
    ):
        raise SystemExit("math Fragment did not rasterize currentColor pixels")
    vector = renderer.render_svg(compiled, layout=layout)
    if "data:image/svg+xml" not in vector:
        raise SystemExit("math Fragment did not render into vector output")


def main() -> None:
    expected_version = os.environ.get("TAKUMI_PY_EXPECTED_VERSION")
    installed_version = version("takumi-py")
    if expected_version is not None and installed_version != expected_version:
        raise SystemExit(
            f"installed version {installed_version!r} != expected {expected_version!r}"
        )

    repository_root_value = os.environ.get("TAKUMI_PY_REPOSITORY_ROOT")
    if repository_root_value is not None:
        repository_root = Path(repository_root_value).resolve()
        module_path = Path(takumi_py.__file__).resolve()
        if module_path.is_relative_to(repository_root):
            raise SystemExit(
                "smoke imported the source checkout instead of the installed wheel: "
                f"{module_path}"
            )

    renderer = Renderer()
    smoke_core_math_optionality()

    png = renderer.render_html(
        '<div class="card">wheel smoke</div>',
        stylesheets=[
            """
            .card {
              width: 160px;
              height: 80px;
              display: flex;
              align-items: center;
              justify-content: center;
              color: white;
              background: #111827;
              font-size: 20px;
            }
            """
        ],
        width=160,
        height=80,
    )
    if not png.startswith(PNG_SIGNATURE):
        raise SystemExit("render_html did not return PNG bytes")

    raw = renderer.render_node(
        {
            "type": "container",
            "style": {"width": "2px", "height": "2px", "backgroundColor": "black"},
        },
        width=2,
        height=2,
        format="raw",
    )
    if len(raw) != 2 * 2 * 4:
        raise SystemExit(f"raw output has unexpected size: {len(raw)}")

    svg = renderer.render_svg_html(
        '<div class="card">svg smoke</div>',
        stylesheets=[".card { width: 64px; height: 32px; color: black; }"],
        width=64,
        height=32,
    )
    if not svg.startswith("<svg") or 'width="64"' not in svg:
        raise SystemExit("render_svg_html did not return the expected SVG document")

    measured = renderer.measure_node(
        {
            "type": "container",
            "style": {"width": "48px", "height": "24px"},
            "children": [{"type": "text", "text": "measure"}],
        },
        width=None,
        height=None,
    )
    if measured.width != 48 or measured.height != 24:
        raise SystemExit(f"measure_node returned {measured.width}x{measured.height}")

    smoke_document_resources(renderer)
    if os.environ.get("TAKUMI_PY_MATH_SMOKE") == "1":
        smoke_math(renderer)

    sys.stdout.write(
        f"takumi-py {installed_version} wheel smoke passed on {platform.platform()}\n"
    )


if __name__ == "__main__":
    main()
