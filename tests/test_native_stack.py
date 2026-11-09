from __future__ import annotations

import subprocess
import sys

import pytest

SMALL_STACK_SCRIPT = r"""
import gc
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

from takumi_py import (
    AnimationEncodeOptions,
    HtmlParseError,
    ImageResource,
    NodeDecodeError,
    RenderOptions,
    Renderer,
    StyleSheetError,
    _core,
)
from takumi_py.options import native_render_settings

STACK_SIZE = int(sys.argv[1])
MODE = sys.argv[2]
IMAGE_URL = "memory://deep-stack.png"
SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1">'
    b'<rect width="1" height="1" fill="red"/></svg>'
)


def mark(stage: str) -> None:
    os.write(2, f"{stage}\n".encode())


def nested_node(depth: int) -> dict[str, object]:
    root: dict[str, object] = {"type": "container", "children": []}
    current = root
    for _ in range(depth - 2):
        child: dict[str, object] = {"type": "container", "children": []}
        children = current["children"]
        assert isinstance(children, list)
        children.append(child)
        current = child
    children = current["children"]
    assert isinstance(children, list)
    children.append(
        {"type": "image", "src": IMAGE_URL, "width": 1, "height": 1}
    )
    return root


def nested_cycle(depth: int) -> dict[str, object]:
    root: dict[str, object] = {"type": "container", "children": []}
    current = root
    for _ in range(depth - 1):
        child: dict[str, object] = {"type": "container", "children": []}
        children = current["children"]
        assert isinstance(children, list)
        children.append(child)
        current = child
    children = current["children"]
    assert isinstance(children, list)
    children.append(root)
    return root


def nested_styled_node(depth: int, width: str) -> dict[str, object]:
    root: dict[str, object] = {"type": "container", "children": []}
    current = root
    for _ in range(depth - 2):
        child: dict[str, object] = {"type": "container", "children": []}
        children = current["children"]
        assert isinstance(children, list)
        children.append(child)
        current = child
    children = current["children"]
    assert isinstance(children, list)
    children.append(
        {
            "type": "container",
            "style": {
                "width": width,
                "height": "1px",
            },
        }
    )
    return root


def nested_html(depth: int) -> str:
    return (
        "<div>" * (depth - 1)
        + f'<img src="{IMAGE_URL}" width="1" height="1">'
        + "</div>" * (depth - 1)
    )


def nested_calc(depth: int) -> str:
    return "calc(0px + " * depth + "0px" + ")" * depth


def exercise_workflow() -> None:
    mark("build")
    payload = nested_node(512)

    mark("compile")
    compiled = _core.compile_node(payload)

    mark("resources")
    assert compiled.resource_urls() == [IMAGE_URL]

    mark("needs")
    native = _core.NativeRenderer(load_default_fonts=False)
    options = RenderOptions(
        width=1,
        height=1,
        format="raw",
        images=[ImageResource(IMAGE_URL, SVG)],
    )
    needs = native.needs_compiled(
        compiled,
        (),
        native_render_settings(options),
    )
    assert needs == ([IMAGE_URL], [], [])

    mark("measure")
    renderer = Renderer(load_default_fonts=False)
    measured = renderer.measure_compiled(compiled, width=1, height=1)
    assert (measured.width, measured.height) == (1, 1)

    mark("render")
    raw = renderer.render_compiled(
        compiled,
        width=1,
        height=1,
        format="raw",
        images=[ImageResource(IMAGE_URL, SVG)],
    )
    assert len(raw) == 4
    assert raw[0] > 0
    assert raw[-1] == 255

    mark("svg")
    svg = native.render_svg_compiled(
        compiled,
        (),
        native_render_settings(options, raster=False),
    )
    assert "<svg" in svg

    mark("rasterize")
    raster = native.rasterize_compiled(
        compiled,
        (),
        native_render_settings(options),
    )
    assert (raster.width, raster.height) == (1, 1)
    assert raster.tobytes()[-1] == 255

    mark("sequence")
    sequence = native.render_sequence_at_time_compiled(
        [(compiled, 100)],
        0,
        (),
        native_render_settings(options, time_ms=0),
        options,
    )
    assert len(sequence) == 4
    assert sequence[-1] == 255

    mark("animation")
    animation = native.render_animation_compiled(
        [(compiled, 100)],
        (),
        native_render_settings(options, time_ms=0),
        10,
        AnimationEncodeOptions(format="gif"),
    )
    assert animation.startswith(b"GIF")

    mark("compile-too-deep")
    try:
        _core.compile_node(nested_node(513))
    except NodeDecodeError as error:
        assert "nodes nest deeper than 512 levels" in str(error)
    else:
        raise AssertionError("deep node past Takumi's limit unexpectedly compiled")

    mark("drop")
    del (
        payload,
        needs,
        measured,
        raw,
        svg,
        raster,
        sequence,
        animation,
        renderer,
        native,
        compiled,
    )
    gc.collect()
    mark("complete")


def exercise_threshold_workflow() -> None:
    native = _core.NativeRenderer(load_default_fonts=False)
    renderer = Renderer(load_default_fonts=False)
    options = RenderOptions(
        width=1,
        height=1,
        images=[ImageResource(IMAGE_URL, SVG)],
    )

    for depth in (16, 32, 63, 64):
        prefix = f"threshold-{depth}"
        mark(f"{prefix}-build")
        payload = nested_node(depth)

        mark(f"{prefix}-compile")
        compiled = _core.compile_node(payload)

        mark(f"{prefix}-resources")
        assert compiled.resource_urls() == [IMAGE_URL]

        mark(f"{prefix}-needs")
        needs = native.needs_compiled(
            compiled,
            (),
            native_render_settings(options),
        )
        assert needs == ([IMAGE_URL], [], [])

        mark(f"{prefix}-measure")
        measured = renderer.measure_compiled(compiled, width=1, height=1)
        assert (measured.width, measured.height) == (1, 1)

        mark(f"{prefix}-render")
        raw = renderer.render_compiled(
            compiled,
            width=1,
            height=1,
            format="raw",
            images=[ImageResource(IMAGE_URL, SVG)],
        )
        assert len(raw) == 4
        assert raw[0] > 0
        assert raw[-1] == 255

        mark(f"{prefix}-drop")
        del payload, compiled, needs, measured, raw
        gc.collect()

    del native, renderer, options
    gc.collect()
    mark("complete")


def exercise_html_workflow() -> None:
    mark("html-build")
    html = nested_html(512)

    mark("html-parse")
    parsed, stylesheets = _core.parse_html(
        html,
        presets="none",
        max_depth=None,
    )
    assert stylesheets == []

    mark("html-resources")
    assert parsed.resource_urls() == [IMAGE_URL]

    mark("html-needs")
    native = _core.NativeRenderer(load_default_fonts=False)
    options = RenderOptions(
        width=1,
        height=1,
        images=[ImageResource(IMAGE_URL, SVG)],
    )
    needs = native.needs_compiled(
        parsed,
        (),
        native_render_settings(options),
    )
    assert needs == ([IMAGE_URL], [], [])

    mark("html-measure")
    renderer = Renderer(load_default_fonts=False)
    measured = renderer.measure_compiled(parsed, width=1, height=1)
    assert (measured.width, measured.height) == (1, 1)

    mark("html-render")
    raw = renderer.render_compiled(
        parsed,
        width=1,
        height=1,
        format="raw",
        images=[ImageResource(IMAGE_URL, SVG)],
    )
    assert len(raw) == 4
    assert raw[0] > 0
    assert raw[-1] == 255

    mark("html-compile")
    legacy = _core.compile_html(
        html,
        presets="none",
        max_depth=None,
    )
    assert legacy.resource_urls() == [IMAGE_URL]

    mark("html-drop")
    del (
        html,
        parsed,
        stylesheets,
        native,
        options,
        needs,
        renderer,
        measured,
        raw,
        legacy,
    )
    gc.collect()
    mark("complete")


def exercise_html_limits() -> None:
    too_deep = nested_html(513)

    mark("html-default-limit")
    for parse in (_core.parse_html, _core.compile_html):
        try:
            parse(too_deep, presets="none", max_depth=None)
        except HtmlParseError:
            pass
        else:
            raise AssertionError(f"{parse.__name__} accepted depth 513")

    mark("html-custom-limit")
    for parse in (_core.parse_html, _core.compile_html):
        try:
            parse(too_deep, presets="none", max_depth=513)
        except ValueError as error:
            assert "max_depth cannot exceed 512" in str(error)
        else:
            raise AssertionError(f"{parse.__name__} accepted max_depth=513")

    mark("complete")


def exercise_cycle_cleanup() -> None:
    mark("build-cycle")
    payload = nested_cycle(512)
    mark("compile-cycle")
    try:
        _core.compile_node(payload)
    except NodeDecodeError as error:
        assert "cycle" in str(error)
    else:
        raise AssertionError("deep cycle unexpectedly compiled")
    mark("drop-cycle")
    del payload
    gc.collect()
    mark("complete")


def exercise_structured_values() -> None:
    accepted = nested_calc(21)

    mark("inline-21")
    _core.compile_node({"type": "container", "style": {"width": accepted}})

    mark("keyframes-21")
    _core.compile_keyframes(
        {
            "same": {
                "from": {"width": accepted},
                "to": {"width": accepted},
            }
        }
    )

    too_deep = nested_calc(60)

    mark("inline-60")
    try:
        _core.compile_node({"type": "container", "style": {"width": too_deep}})
    except NodeDecodeError:
        pass
    else:
        raise AssertionError("over-deep inline calc unexpectedly compiled")

    mark("keyframes-60")
    try:
        _core.compile_keyframes(
            {
                "same": {
                    "from": {"width": too_deep},
                    "to": {"width": too_deep},
                }
            }
        )
    except StyleSheetError:
        pass
    else:
        raise AssertionError("over-deep keyframe calc unexpectedly compiled")

    mark("complete")


def exercise_combined_boundary(node_depth: int, calc_depth: int) -> None:
    mark("combined-build")
    node = nested_styled_node(node_depth, nested_calc(calc_depth))

    mark("combined-compile")
    compiled = _core.compile_node(node)

    mark("combined-resources")
    assert compiled.resource_urls() == []

    mark("combined-measure")
    renderer = Renderer(load_default_fonts=False)
    measured = renderer.measure_compiled(compiled, width=1, height=1)

    mark("combined-render")
    raw = renderer.render_compiled(
        compiled,
        width=1,
        height=1,
        format="raw",
    )
    assert len(raw) == 4

    mark("combined-drop")
    del node, compiled, renderer, measured, raw
    gc.collect()
    mark("complete")


def exercise_nested_css() -> None:
    mark("css-build")
    css = ".root{" * 75 + "color:red;" + "}" * 75

    mark("css-compile")
    stylesheet = _core.compile_stylesheet(css)

    mark("css-merge")
    merged = _core.merge_stylesheets((stylesheet, stylesheet))
    assert merged.resource_urls() == []

    mark("css-render-shallow")
    resource_url = "memory://deep-css.png"
    styled = _core.compile_stylesheet(
        "@media all{" * 32
        + f".root{{width:1px;height:1px;background-image:url({resource_url});}}"
        + "}" * 32
    )
    assert styled.resource_urls() == [resource_url]

    node = _core.compile_node({"type": "container", "className": "root"})
    assert node.resource_urls() == []
    native = _core.NativeRenderer(load_default_fonts=False)
    render_options = RenderOptions(
        width=1,
        height=1,
        format="raw",
        images=[ImageResource(resource_url, SVG)],
    )
    rendered = native.render_compiled(
        node,
        (styled,),
        native_render_settings(render_options),
        render_options,
    )
    assert len(rendered) == 4
    assert rendered[:3] == b"\xff\x00\x00"

    mark("css-lossy")
    lossy = _core.compile_stylesheet(css, strict=False)

    mark("css-limit")
    too_deep = ".root{" * 76 + "color:red;" + "}" * 76
    try:
        _core.compile_stylesheet(too_deep)
    except StyleSheetError as error:
        assert "TooManyNestedBlocks" in str(error)
    else:
        raise AssertionError("CSS beyond cssparser's nesting limit unexpectedly parsed")

    mark("css-drop")
    del (
        css,
        stylesheet,
        merged,
        resource_url,
        styled,
        node,
        native,
        render_options,
        rendered,
        lossy,
        too_deep,
    )
    gc.collect()
    mark("complete")


threading.stack_size(STACK_SIZE)
with ThreadPoolExecutor(max_workers=1) as executor:
    if MODE == "workflow":
        executor.submit(exercise_workflow).result()
    elif MODE == "threshold-workflow":
        executor.submit(exercise_threshold_workflow).result()
    elif MODE == "html-workflow":
        executor.submit(exercise_html_workflow).result()
    elif MODE == "html-limits":
        executor.submit(exercise_html_limits).result()
    elif MODE == "cycle":
        executor.submit(exercise_cycle_cleanup).result()
    elif MODE == "nested-css":
        executor.submit(exercise_nested_css).result()
    elif MODE == "structured-values":
        executor.submit(exercise_structured_values).result()
    elif MODE.startswith("combined-"):
        node_depth, calc_depth = map(int, MODE.removeprefix("combined-").split("-"))
        executor.submit(exercise_combined_boundary, node_depth, calc_depth).result()
    else:
        raise AssertionError(f"unknown mode: {MODE}")
"""


def _run_small_stack_script(stack_size: int, mode: str) -> None:
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and literal script.
        [
            sys.executable,
            "-I",
            "-u",
            "-c",
            SMALL_STACK_SCRIPT,
            str(stack_size),
            mode,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    stages = completed.stderr.splitlines()
    detail = (
        "small-stack subprocess did not complete successfully\n"
        f"mode={mode}\n"
        f"stack_size={stack_size}\n"
        f"platform={sys.platform}\n"
        f"returncode={completed.returncode} "
        f"(0x{completed.returncode & 0xFFFFFFFF:08x})\n"
        f"stages={stages!r}\n"
        f"stdout={completed.stdout!r}"
    )

    assert completed.returncode == 0, detail
    assert "complete" in stages, detail


@pytest.mark.parametrize(
    "stack_size",
    [
        pytest.param(512 * 1024, id="512KiB"),
        pytest.param(1024 * 1024, id="1MiB"),
    ],
)
def test_deep_native_pipeline_fits_small_worker_stack(stack_size: int) -> None:
    _run_small_stack_script(stack_size, "workflow")


@pytest.mark.parametrize(
    "stack_size",
    [
        pytest.param(512 * 1024, id="512KiB"),
        pytest.param(1024 * 1024, id="1MiB"),
    ],
)
def test_node_threshold_pipeline_fits_small_worker_stack(stack_size: int) -> None:
    _run_small_stack_script(stack_size, "threshold-workflow")


@pytest.mark.parametrize(
    "stack_size",
    [
        pytest.param(512 * 1024, id="512KiB"),
        pytest.param(1024 * 1024, id="1MiB"),
    ],
)
def test_deep_html_pipeline_fits_small_worker_stack(stack_size: int) -> None:
    _run_small_stack_script(stack_size, "html-workflow")


@pytest.mark.parametrize(
    "stack_size",
    [
        pytest.param(512 * 1024, id="512KiB"),
        pytest.param(1024 * 1024, id="1MiB"),
    ],
)
def test_html_depth_limit_errors_fit_small_worker_stack(stack_size: int) -> None:
    _run_small_stack_script(stack_size, "html-limits")


@pytest.mark.parametrize(
    "stack_size",
    [
        pytest.param(512 * 1024, id="512KiB"),
        pytest.param(1024 * 1024, id="1MiB"),
    ],
)
def test_deep_cycle_snapshot_cleanup_fits_small_worker_stack(stack_size: int) -> None:
    _run_small_stack_script(stack_size, "cycle")


@pytest.mark.parametrize(
    "stack_size",
    [
        pytest.param(512 * 1024, id="512KiB"),
        pytest.param(1024 * 1024, id="1MiB"),
    ],
)
def test_deep_css_compile_and_merge_fit_small_worker_stack(stack_size: int) -> None:
    _run_small_stack_script(stack_size, "nested-css")


@pytest.mark.parametrize(
    "stack_size",
    [
        pytest.param(512 * 1024, id="512KiB"),
        pytest.param(1024 * 1024, id="1MiB"),
    ],
)
def test_structured_css_values_fit_small_worker_stack(stack_size: int) -> None:
    _run_small_stack_script(stack_size, "structured-values")


@pytest.mark.parametrize(
    ("node_depth", "calc_depth"),
    [
        pytest.param(8, 15, id="node8-calc15"),
        pytest.param(15, 7, id="node15-calc7"),
        pytest.param(16, 15, id="node16-calc15"),
        pytest.param(17, 15, id="node17-calc15"),
        pytest.param(24, 15, id="node24-calc15"),
        pytest.param(31, 15, id="node31-calc15"),
        pytest.param(48, 15, id="node48-calc15"),
        pytest.param(60, 15, id="node60-calc15"),
        pytest.param(63, 15, id="node63-calc15"),
    ],
)
def test_combined_node_and_inline_css_depth_fit_512k_stack(
    node_depth: int,
    calc_depth: int,
) -> None:
    _run_small_stack_script(512 * 1024, f"combined-{node_depth}-{calc_depth}")
