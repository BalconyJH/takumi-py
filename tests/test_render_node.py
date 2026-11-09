import pytest

from takumi_py import NodeValidationError, Renderer, validate_node


def test_render_node_returns_png_bytes() -> None:
    png = Renderer().render_node(
        {"type": "text", "text": "hello"},
        stylesheets=["span { font-size: 32px; color: black; }"],
        width=240,
        height=120,
    )

    assert png.startswith(b"\x89PNG")


def test_compiled_node_can_render_repeatedly() -> None:
    renderer = Renderer()
    node = renderer.compile_node({"type": "text", "text": "hello"}, validate=True)
    stylesheet = renderer.compile_stylesheet("span { font-size: 32px; }")

    first = renderer.render_compiled(
        node, stylesheets=[stylesheet], width=240, height=120
    )
    second = renderer.render_compiled(
        node, stylesheets=[stylesheet], width=240, height=120
    )

    assert first.startswith(b"\x89PNG")
    assert second.startswith(b"\x89PNG")


def test_validate_node_accepts_nested_container() -> None:
    node = validate_node(
        {
            "type": "container",
            "children": [{"type": "text", "text": "hello"}],
        }
    )

    assert node["type"] == "container"
    assert node["children"][0]["type"] == "text"


def test_validate_node_preserves_msgspec_sequence_normalization() -> None:
    node = validate_node(
        {
            "type": "container",
            "children": ({"type": "text", "text": "hello"},),
        }
    )

    assert node["type"] == "container"
    assert isinstance(node["children"], list)


def test_validate_node_rejects_invalid_child() -> None:
    with pytest.raises(NodeValidationError):
        validate_node({"type": "container", "children": [{"type": "text"}]})


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


def test_validate_node_supports_the_full_native_node_depth() -> None:
    validated = validate_node(_nested_containers(512))

    assert validated["type"] == "container"


def test_validate_node_rejects_excessive_node_depth() -> None:
    with pytest.raises(NodeValidationError, match="deeper than 512"):
        validate_node(_nested_containers(513))


def test_validate_node_rejects_cycles_with_the_public_error() -> None:
    node: dict[str, object] = {"type": "container", "children": []}
    children = node["children"]
    assert isinstance(children, list)
    children.append(node)

    with pytest.raises(NodeValidationError, match="cycle"):
        validate_node(node)

    with pytest.raises(NodeValidationError, match="cycle"):
        Renderer().render_node(node, width=1, height=1, validate=True)


def test_measure_supports_a_document_at_the_full_node_depth() -> None:
    node: dict[str, object] = {"type": "text", "text": "deep"}
    for _ in range(511):
        node = {"type": "container", "children": [node]}

    measured = Renderer().measure_node(node, width=None, height=None)

    assert measured.width > 0
    assert measured.height > 0
