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
    AnimationScene,
    HtmlOptions,
    HtmlParseError,
    ImageResource,
    NodeDecodeError,
    Renderer,
    parse_html,
    _core,
)

STACK_SIZE = int(sys.argv[1])
MODE = sys.argv[2]
IMAGE_URL = "https://example.com/deep-stack.png"
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
        {"type": "container", "style": {"width": width, "height": "1px"}}
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
    compiled = _core.NativeRenderer(
        load_default_fonts=False
    ).compile_node(payload)

    mark("resources")
    assert compiled.resource_urls() == [IMAGE_URL]

    mark("measure")
    renderer = Renderer(load_default_fonts=False)
    measured = renderer.measure_compiled(compiled, width=1, height=1)
    assert measured.width == 1
    assert len(measured.children) == 1

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
    svg = renderer.render_svg_compiled(
        compiled,
        width=1,
        height=1,
        images=[ImageResource(IMAGE_URL, SVG)],
    )
    assert "<svg" in svg

    mark("sequence")
    sequence = renderer.render_sequence_at_time(
        [AnimationScene(compiled, 100)],
        0,
        width=1,
        height=1,
        format="raw",
        images=[ImageResource(IMAGE_URL, SVG)],
    )
    assert len(sequence) == 4
    assert sequence[-1] == 255

    mark("animation")
    animation = renderer.render_animation(
        [AnimationScene(compiled, 100)],
        width=1,
        height=1,
        fps=10,
        encode_options=AnimationEncodeOptions(format="gif"),
        images=[ImageResource(IMAGE_URL, SVG)],
    )
    assert animation.startswith(b"GIF")

    mark("compile-too-deep")
    try:
        renderer.compile_node(nested_node(513))
    except NodeDecodeError as error:
        assert "nodes nest deeper than 512 levels" in str(error)
    else:
        raise AssertionError("deep node past Takumi's limit unexpectedly compiled")

    mark("drop")
    del (
        payload,
        measured,
        raw,
        svg,
        sequence,
        animation,
        renderer,
        compiled,
    )
    gc.collect()
    mark("complete")


def exercise_threshold_workflow() -> None:
    native = _core.NativeRenderer(load_default_fonts=False)
    renderer = Renderer(load_default_fonts=False)

    for depth in (15, 16, 17, 32, 63):
        prefix = f"threshold-{depth}"
        mark(f"{prefix}-build")
        payload = nested_node(depth)

        mark(f"{prefix}-compile")
        compiled = native.compile_node(payload)

        mark(f"{prefix}-resources")
        assert compiled.resource_urls() == [IMAGE_URL]

        mark(f"{prefix}-measure")
        measured = renderer.measure_compiled(compiled, width=1, height=1)
        assert measured.width == 1
        assert len(measured.children) == 1

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
        del payload, compiled, measured, raw
        gc.collect()

    del native, renderer
    gc.collect()
    mark("complete")


def exercise_structured_values() -> None:
    renderer = Renderer(load_default_fonts=False)
    accepted = nested_calc(21)

    mark("inline-21")
    renderer.compile_node(
        {"type": "container", "style": {"width": accepted, "height": "1px"}}
    )

    mark("keyframes-21")
    renderer.compile_keyframes(
        {
            "same": {
                "from": {"width": accepted},
                "to": {"width": accepted},
            }
        }
    )

    deep_calc = nested_calc(60)

    mark("inline-60")
    renderer.compile_node(
        {"type": "container", "style": {"width": deep_calc}}
    )

    mark("keyframes-60")
    renderer.compile_keyframes(
        {
            "same": {
                "from": {"width": deep_calc},
                "to": {"width": deep_calc},
            }
        }
    )

    mark("deep-loop-input")
    nested: list[object] = []
    current = nested
    for _ in range(1100):
        child: list[object] = []
        current.append(child)
        current = child
    try:
        renderer.compile_node({"type": "container", "future": nested})
    except NodeDecodeError as error:
        assert "nests deeper" in str(error)
    else:
        raise AssertionError("over-deep snapshot unexpectedly compiled")

    mark("structured-drop")
    del renderer, accepted, deep_calc, nested, current
    gc.collect()
    mark("complete")


def exercise_combined_boundary(node_depth: int, calc_depth: int) -> None:
    mark("combined-build")
    node = nested_styled_node(node_depth, nested_calc(calc_depth))
    renderer = Renderer(load_default_fonts=False)

    mark("combined-compile")
    compiled = renderer.compile_node(node)

    mark("combined-resources")
    assert compiled.resource_urls() == []

    mark("combined-measure")
    measured = renderer.measure_compiled(compiled, width=1, height=1)
    assert measured.width == 1
    assert isinstance(measured.height, float)

    mark("combined-render")
    raw = renderer.render_compiled(
        compiled,
        width=1,
        height=1,
        format="raw",
    )
    assert len(raw) == 4

    mark("combined-drop")
    del node, renderer, compiled, measured, raw
    gc.collect()
    mark("complete")


def exercise_html_workflow() -> None:
    mark("html-build")
    html = nested_html(512)
    renderer = Renderer(load_default_fonts=False)

    mark("html-compile")
    compiled = renderer.compile_html(html)
    assert compiled.node.resource_urls() == [IMAGE_URL]

    mark("html-module-parse")
    parsed = parse_html(html)
    assert parsed.node.resource_urls() == [IMAGE_URL]

    mark("html-measure")
    measured = renderer.measure_compiled(compiled.node, width=1, height=1)
    assert measured.width == 1
    assert len(measured.children) == 1

    mark("html-render")
    raw = renderer.render_compiled(
        compiled.node,
        width=1,
        height=1,
        format="raw",
        images=[ImageResource(IMAGE_URL, SVG)],
    )
    assert len(raw) == 4

    mark("html-limits")
    too_deep = nested_html(513)
    for parse in (
        lambda source: renderer.compile_html(source),
        lambda source: parse_html(source),
    ):
        try:
            parse(too_deep)
        except HtmlParseError:
            pass
        else:
            raise AssertionError("HTML depth 513 unexpectedly compiled")
    for parse in (
        lambda source: renderer.compile_html(
            source, html_options=HtmlOptions(max_depth=513)
        ),
        lambda source: parse_html(
            source, options=HtmlOptions(max_depth=513)
        ),
    ):
        try:
            parse("<div></div>")
        except ValueError as error:
            assert "max_depth cannot exceed 512" in str(error)
        else:
            raise AssertionError("max_depth 513 unexpectedly compiled")

    mark("html-drop")
    del html, renderer, compiled, parsed, measured, raw, too_deep
    gc.collect()
    mark("complete")


def exercise_cycle_cleanup() -> None:
    mark("build-cycle")
    payload = nested_cycle(512)
    mark("compile-cycle")
    try:
        _core.NativeRenderer(
            load_default_fonts=False
        ).compile_node(payload)
    except NodeDecodeError as error:
        assert "cycle" in str(error)
    else:
        raise AssertionError("deep cycle unexpectedly compiled")
    mark("drop-cycle")
    del payload
    gc.collect()
    mark("complete")


def exercise_invalid_input_cleanup() -> None:
    native = _core.NativeRenderer(load_default_fonts=False)

    mark("too-deep-build")
    too_deep = nested_node(513)
    mark("too-deep-compile")
    try:
        native.compile_node(too_deep)
    except NodeDecodeError as error:
        assert "nodes nest deeper than 512 levels" in str(error)
    else:
        raise AssertionError("node at depth 513 unexpectedly compiled")
    mark("too-deep-drop")
    del too_deep
    gc.collect()

    mark("partial-snapshot-build")
    deep_prefix: list[object] = []
    current_prefix = deep_prefix
    for _ in range(512):
        child_prefix: list[object] = []
        current_prefix.append(child_prefix)
        current_prefix = child_prefix
    partial_snapshot = {"type": "container", "future": [deep_prefix, object()]}
    mark("partial-snapshot-compile")
    for _ in range(3):
        try:
            native.compile_node(partial_snapshot)
        except NodeDecodeError as error:
            assert "unsupported node input type" in str(error)
        else:
            raise AssertionError("unsupported nested value unexpectedly compiled")
    mark("partial-snapshot-drop")
    del deep_prefix, current_prefix, partial_snapshot
    gc.collect()

    mark("invalid-subtree-build")
    invalid: dict[str, object] = {"type": "container", "children": []}
    current_node = invalid
    for _ in range(511):
        child_node: dict[str, object] = {"type": "container", "children": []}
        children = current_node["children"]
        assert isinstance(children, list)
        children.append(child_node)
        current_node = child_node
    leaf_children = current_node["children"]
    assert isinstance(leaf_children, list)
    leaf_children.append({"type": "not-a-node"})
    mark("invalid-subtree-compile")
    try:
        native.compile_node(invalid)
    except NodeDecodeError:
        pass
    else:
        raise AssertionError("invalid subtree unexpectedly compiled")
    mark("invalid-subtree-drop")
    del invalid, current_node, leaf_children
    gc.collect()

    mark("recovery")
    recovered = native.compile_node({"type": "container"})
    assert recovered.resource_urls() == []
    del recovered, native
    gc.collect()
    mark("complete")


def exercise_unknown_values() -> None:
    renderer = Renderer(load_default_fonts=False)
    mark("unknown-nested")
    unknown_deep: dict[str, object] = {}
    current_unknown = unknown_deep
    for index in range(600):
        child_unknown: dict[str, object] = {}
        current_unknown[f"level-{index}"] = child_unknown
        current_unknown = child_unknown
    current_unknown["buffer"] = memoryview(bytes((0, 1, 2, 255)))
    compiled = renderer.compile_node(
        {
            "type": "container",
            "children": [],
            "future": {
                "nested": [
                    None,
                    True,
                    1,
                    2.5,
                    "text",
                    bytes((0, 1, 2, 255)),
                    bytearray((3, 4)),
                    memoryview(bytes((5, 6))),
                    unknown_deep,
                ]
            },
        }
    )
    mark("unknown-compiled")
    assert compiled.resource_urls() == []
    mark("unknown-drop")
    del compiled, renderer, unknown_deep, current_unknown
    gc.collect()
    mark("complete")


def exercise_nested_css() -> None:
    mark("css-build")
    css = ".root{" * 75 + "color:red;" + "}" * 75
    renderer = Renderer(load_default_fonts=False)

    mark("css-compile")
    stylesheet = renderer.compile_stylesheet(css)
    lossy = renderer.compile_stylesheet_lossy(css)
    merged = renderer.compile_stylesheet(
        ".root{width:1px;height:1px;background:red}"
    )

    mark("css-render")
    raw = renderer.render_compiled(
        renderer.compile_node({"type": "container", "className": "root"}),
        stylesheets=[stylesheet, lossy, merged],
        width=1,
        height=1,
        format="raw",
    )
    assert raw[:3] == b"\xff\x00\x00"

    mark("css-keyframes")
    keyframes = renderer.compile_keyframes(
        {
            "same": {
                "from": {"width": "calc(0px + " * 20 + "1px" + ")" * 20},
                "to": {"width": "1px"},
            }
        }
    )

    mark("css-drop")
    del css, renderer, stylesheet, lossy, merged, keyframes, raw
    gc.collect()
    mark("complete")


threading.stack_size(STACK_SIZE)
with ThreadPoolExecutor(max_workers=1) as executor:
    if MODE == "workflow":
        executor.submit(exercise_workflow).result()
    elif MODE == "threshold-workflow":
        executor.submit(exercise_threshold_workflow).result()
    elif MODE == "structured-values":
        executor.submit(exercise_structured_values).result()
    elif MODE == "html-workflow":
        executor.submit(exercise_html_workflow).result()
    elif MODE == "cycle":
        executor.submit(exercise_cycle_cleanup).result()
    elif MODE == "invalid-inputs":
        executor.submit(exercise_invalid_input_cleanup).result()
    elif MODE == "unknown-values":
        executor.submit(exercise_unknown_values).result()
    elif MODE == "nested-css":
        executor.submit(exercise_nested_css).result()
    elif MODE.startswith("combined-"):
        node_depth, calc_depth = map(int, MODE.removeprefix("combined-").split("-"))
        executor.submit(
            exercise_combined_boundary, node_depth, calc_depth
        ).result()
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
@pytest.mark.parametrize("mode", ["workflow", "html-workflow"])
def test_deep_native_pipeline_fits_small_worker_stack(
    stack_size: int,
    mode: str,
) -> None:
    _run_small_stack_script(stack_size, mode)


@pytest.mark.parametrize(
    "stack_size",
    [
        pytest.param(512 * 1024, id="512KiB"),
        pytest.param(1024 * 1024, id="1MiB"),
    ],
)
@pytest.mark.parametrize(
    "mode",
    [
        "threshold-workflow",
        "structured-values",
        "invalid-inputs",
        "unknown-values",
        "cycle",
        "nested-css",
    ],
)
def test_additional_old_api_paths_fit_small_worker_stack(
    stack_size: int,
    mode: str,
) -> None:
    _run_small_stack_script(stack_size, mode)


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
