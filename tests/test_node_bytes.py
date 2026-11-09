from __future__ import annotations

from collections.abc import Callable

import pytest

from takumi_py import NodeDecodeError, Renderer, _core

SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2">'
    b'<rect width="2" height="2" fill="red"/></svg>'
)
RGBA = bytes((255, 0, 0, 255, 0, 255, 0, 255, 0, 0, 255, 255, 255, 255, 255, 255))


@pytest.mark.parametrize(
    "as_buffer",
    [
        pytest.param(bytes, id="bytes"),
        pytest.param(bytearray, id="bytearray"),
        pytest.param(memoryview, id="memoryview"),
    ],
)
def test_inline_encoded_image_accepts_python_buffers(
    as_buffer: Callable[[bytes], object],
) -> None:
    compiled = _core.NativeRenderer(load_default_fonts=False).compile_node(
        {"type": "image", "src": as_buffer(SVG)}
    )
    raw = Renderer(cache_max_bytes=0).render_compiled(
        compiled,
        width=2,
        height=2,
        format="raw",
    )

    assert raw == bytes((255, 0, 0, 255)) * 4


@pytest.mark.parametrize(
    "as_buffer",
    [
        pytest.param(bytes, id="bytes"),
        pytest.param(bytearray, id="bytearray"),
        pytest.param(memoryview, id="memoryview"),
    ],
)
def test_raw_rgba_node_data_accepts_python_buffers(
    as_buffer: Callable[[bytes], object],
) -> None:
    compiled = _core.NativeRenderer(load_default_fonts=False).compile_node(
        {
            "type": "image",
            "src": {
                "width": 2,
                "height": 2,
                "data": as_buffer(RGBA),
                "premultiplied": False,
            },
            "width": 2,
            "height": 2,
        }
    )
    raw = Renderer(cache_max_bytes=0).render_compiled(
        compiled,
        width=2,
        height=2,
        format="raw",
    )

    assert raw == RGBA


def test_compiled_node_snapshots_mutable_buffers() -> None:
    pixels = bytearray(RGBA)
    compiled = _core.NativeRenderer(load_default_fonts=False).compile_node(
        {
            "type": "image",
            "src": {"width": 2, "height": 2, "data": pixels},
            "width": 2,
            "height": 2,
        }
    )
    pixels[:] = b"\0" * len(pixels)

    raw = Renderer(cache_max_bytes=0).render_compiled(
        compiled,
        width=2,
        height=2,
        format="raw",
    )

    assert raw[:4] == RGBA[:4]


def test_json_like_scalars_sequences_and_optional_none_compile() -> None:
    compiled = _core.NativeRenderer(load_default_fonts=False).compile_node(
        {
            "type": "container",
            "children": None,
            "style": {"width": 3, "height": 2.5, "display": "block"},
        }
    )
    measured = Renderer().measure_compiled(compiled, width=None, height=None)

    assert (measured.width, measured.height) == (3, 2.5)

    tuple_compiled = _core.NativeRenderer(load_default_fonts=False).compile_node(
        {
            "type": "container",
            "children": (
                {"type": "text", "text": "A"},
                {"type": "text", "text": "B"},
            ),
        }
    )
    assert isinstance(tuple_compiled, type(compiled))


def test_unsupported_values_raise_node_decode_error_instead_of_panicking() -> None:
    with pytest.raises(NodeDecodeError, match=r"unsupported node input type ['\"]set"):
        _core.NativeRenderer(load_default_fonts=False).compile_node(
            {"type": "container", "future": {1, 2}}
        )


def test_supported_unknown_fields_are_left_to_the_core_schema() -> None:
    compiled = _core.NativeRenderer(load_default_fonts=False).compile_node(
        {
            "type": "container",
            "children": [],
            "future": {"nested": [1, None, True]},
        }
    )

    assert isinstance(
        compiled,
        type(
            _core.NativeRenderer(load_default_fonts=False).compile_node(
                {"type": "container"}
            )
        ),
    )


def test_unknown_nested_values_are_snapshotted_independently() -> None:
    buffer = bytearray((1, 2, 3, 4))
    compiled = _core.NativeRenderer(load_default_fonts=False).compile_node(
        {
            "type": "container",
            "future": {
                "buffer": buffer,
                "values": [None, True, 1, -2, 2.5, "text"],
            },
        }
    )
    buffer[:] = b"\0" * len(buffer)

    assert compiled.resource_urls() == []


def test_failure_after_partial_snapshot_cleanup() -> None:
    renderer = _core.NativeRenderer(load_default_fonts=False)
    node = {
        "type": "container",
        "future": [
            {"valid": bytearray(64)},
            {"invalid": bytearray(64), "bad": object()},
        ],
    }

    for _ in range(10):
        with pytest.raises(NodeDecodeError, match="unsupported node input type"):
            renderer.compile_node(node)

    assert renderer.compile_node({"type": "container"}).resource_urls() == []


def test_invalid_deep_node_does_not_poison_renderer() -> None:
    renderer = _core.NativeRenderer(load_default_fonts=False)
    invalid = _nested_containers(512)
    leaf = invalid
    for _ in range(511):
        children = leaf.get("children")
        assert isinstance(children, list)
        child = children[0]
        assert isinstance(child, dict)
        leaf = child
    leaf["type"] = "not-a-node"

    with pytest.raises(NodeDecodeError):
        renderer.compile_node(invalid)

    shallow = renderer.compile_node(
        {"type": "image", "src": bytes(SVG), "width": 1, "height": 1}
    )
    assert (
        Renderer(cache_max_bytes=0).render_compiled(
            shallow,
            width=1,
            height=1,
            format="raw",
        )[-1]
        == 255
    )


def test_mapping_order_reaches_the_core_schema() -> None:
    renderer = Renderer(cache_max_bytes=0)
    longhand_last = renderer.compile_node(
        {
            "type": "container",
            "style": {
                "width": "2px",
                "height": "2px",
                "background": "red",
                "backgroundColor": "blue",
            },
        }
    )
    shorthand_last = renderer.compile_node(
        {
            "type": "container",
            "style": {
                "width": "2px",
                "height": "2px",
                "backgroundColor": "blue",
                "background": "red",
            },
        }
    )

    longhand_pixel = renderer.render_compiled(
        longhand_last,
        width=2,
        height=2,
        format="raw",
    )[:4]
    shorthand_pixel = renderer.render_compiled(
        shorthand_last,
        width=2,
        height=2,
        format="raw",
    )[:4]

    assert longhand_pixel == bytes((0, 0, 255, 255))
    assert shorthand_pixel == bytes((255, 0, 0, 255))


def test_cycles_raise_node_decode_error() -> None:
    node: dict[str, object] = {"type": "container", "children": []}
    children = node["children"]
    assert isinstance(children, list)
    children.append(node)

    with pytest.raises(NodeDecodeError, match="cycle"):
        _core.NativeRenderer(load_default_fonts=False).compile_node(node)


def test_shared_sibling_containers_are_not_reported_as_cycles() -> None:
    shared = {"type": "container", "children": []}
    compiled = _core.NativeRenderer(load_default_fonts=False).compile_node(
        {"type": "container", "children": [shared, shared]}
    )

    assert compiled.resource_urls() == []


def test_excessive_container_depth_raises_node_decode_error() -> None:
    nested: list[object] = []
    current = nested
    for _ in range(1100):
        child: list[object] = []
        current.append(child)
        current = child

    with pytest.raises(NodeDecodeError, match="nests deeper than"):
        _core.NativeRenderer(load_default_fonts=False).compile_node(
            {"type": "container", "future": nested}
        )


def _nested_containers(count: int) -> dict[str, object]:
    root: dict[str, object] = {"type": "container", "children": []}
    current = root
    for _ in range(count - 1):
        child: dict[str, object] = {"type": "container", "children": []}
        children = current["children"]
        assert isinstance(children, list)
        children.append(child)
        current = child
    return root


def test_core_maximum_node_depth_is_preserved() -> None:
    renderer = _core.NativeRenderer(load_default_fonts=False)
    compiled = renderer.compile_node(_nested_containers(512))
    assert isinstance(compiled, type(renderer.compile_node({"type": "container"})))

    with pytest.raises(NodeDecodeError, match="nodes nest deeper than 512 levels"):
        renderer.compile_node(_nested_containers(513))


@pytest.mark.parametrize("depth", [15, 16, 17, 63, 64])
def test_small_stack_threshold_boundaries(depth: int) -> None:
    renderer = _core.NativeRenderer(load_default_fonts=False)
    compiled = renderer.compile_node(_nested_containers(depth))

    assert compiled.resource_urls() == []
    assert Renderer().measure_compiled(compiled, width=1, height=1).width == 1
