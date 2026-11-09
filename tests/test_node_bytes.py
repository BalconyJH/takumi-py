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
    compiled = _core.compile_node({"type": "image", "src": as_buffer(SVG)})
    raw = Renderer(cache_max_bytes=0).render_compiled(
        compiled,
        width=2,
        height=2,
        format="raw",
    )

    assert len(raw) == 2 * 2 * 4


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
    compiled = _core.compile_node(
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

    assert len(raw) == len(RGBA)


def test_compiled_node_snapshots_mutable_buffers() -> None:
    pixels = bytearray(RGBA)
    compiled = _core.compile_node(
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
    compiled = _core.compile_node(
        {
            "type": "container",
            "children": None,
            "style": {"width": 3, "height": 2.5, "display": "block"},
        }
    )
    measured = Renderer().measure_compiled(compiled, width=None, height=None)

    assert (measured.width, measured.height) == (3, 2.5)

    tuple_compiled = _core.compile_node(
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
        _core.compile_node({"type": "container", "future": {1, 2}})


def test_supported_unknown_fields_are_left_to_the_core_schema() -> None:
    compiled = _core.compile_node(
        {
            "type": "container",
            "children": [],
            "future": {"nested": [1, None, True]},
        }
    )

    assert isinstance(compiled, type(_core.compile_node({"type": "container"})))


def test_mapping_order_reaches_the_core_schema() -> None:
    longhand_last = _core.compile_node(
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
    shorthand_last = _core.compile_node(
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
    renderer = Renderer(cache_max_bytes=0)

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
        _core.compile_node(node)


def test_excessive_container_depth_raises_node_decode_error() -> None:
    nested: list[object] = []
    current = nested
    for _ in range(1100):
        child: list[object] = []
        current.append(child)
        current = child

    with pytest.raises(NodeDecodeError, match="nests deeper than"):
        _core.compile_node({"type": "container", "future": nested})


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
    compiled = _core.compile_node(_nested_containers(512))
    assert isinstance(compiled, type(_core.compile_node({"type": "container"})))

    with pytest.raises(NodeDecodeError, match="nodes nest deeper than 512 levels"):
        _core.compile_node(_nested_containers(513))
