from typing import Any, cast

import pytest

from takumi_py import (
    CompiledDocument,
    ImageResource,
    NodeValidationError,
    Renderer,
    ResourceError,
    StyleSheetError,
)
from takumi_py.document import (
    Document,
    Fragment,
    ResourceSet,
    compile_document,
)

SVG_1X1 = (
    b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1">'
    b'<rect width="1" height="1" fill="red"/></svg>'
)


def test_resource_set_snapshots_and_deduplicates_identical_images() -> None:
    provided = [ImageResource("memory://logo", b"same")]
    resources = ResourceSet(provided)
    provided.append(ImageResource("memory://logo", b"same"))
    provided.append(ImageResource("memory://other", b"other"))

    assert resources.images == (ImageResource("memory://logo", b"same"),)
    assert (
        ResourceSet(
            [
                ("memory://logo", b"same"),
                ImageResource("memory://logo", b"same"),
            ]
        )
        == resources
    )


@pytest.mark.parametrize(
    "duplicate",
    [
        ImageResource("memory://logo", b"different"),
        ImageResource("memory://logo", b"same", cache="none"),
    ],
)
def test_resource_set_rejects_conflicts_for_one_source(
    duplicate: ImageResource,
) -> None:
    with pytest.raises(ResourceError, match="conflicting image resources"):
        ResourceSet([ImageResource("memory://logo", b"same"), duplicate])


@pytest.mark.parametrize("src", [None, 1, b"memory://logo"])
def test_resource_set_requires_string_sources(src: object) -> None:
    with pytest.raises(TypeError, match="src must be a string"):
        ResourceSet([ImageResource(cast(Any, src), b"data")])


def test_resource_set_requires_bytes_like_data() -> None:
    with pytest.raises(TypeError, match="bytes-like"):
        ResourceSet([ImageResource("memory://logo", cast(Any, 1024))])


def test_resource_set_rejects_unknown_cache_modes() -> None:
    with pytest.raises(ValueError, match="cache"):
        ResourceSet(
            [
                ImageResource(
                    "memory://logo",
                    b"data",
                    cast(Any, "sometimes"),
                )
            ]
        )


def test_resource_set_copies_bytes_like_data() -> None:
    data = memoryview(bytearray(b"mutable"))

    resources = ResourceSet([ImageResource("memory://logo", cast(Any, data))])
    data[0] = ord("M")

    assert resources.images[0].data == b"mutable"


def test_fragment_snapshots_source_before_document_creation() -> None:
    nested_node: dict[str, Any] = {
        "type": "image",
        "src": "memory://formula",
        "width": 8,
        "height": 4,
    }
    nested = Fragment(
        nested_node,
        ResourceSet([ImageResource("memory://formula", SVG_1X1)]),
    )
    source: dict[str, Any] = {
        "type": "container",
        "style": {"width": "16px"},
        "children": [nested],
    }

    fragment = Fragment(source)
    source["style"] = {"width": "999px"}
    source["children"].clear()
    nested_node["width"] = 100

    snapshot = fragment.node
    assert snapshot["style"] == {"width": "16px"}
    children = cast(list[Fragment[dict[str, Any]]], snapshot["children"])
    assert children[0].node["width"] == 8
    assert children[0].resources.images == (ImageResource("memory://formula", SVG_1X1),)

    document = Document.from_node(fragment)
    document_node = document.node
    assert document_node is not None
    document_children = cast(list[dict[str, Any]], document_node["children"])
    assert document_children[0]["width"] == 8
    assert document.resources.images == (ImageResource("memory://formula", SVG_1X1),)


def test_fragment_preserves_native_opaque_node_identity() -> None:
    compiled = compile_document(Document.from_node({"type": "text", "text": "hello"}))
    fragment = Fragment(compiled.node)

    assert fragment.node is compiled.node


def test_from_node_snapshots_nodes_and_expands_reused_fragments() -> None:
    fragment_resources = [ImageResource("memory://formula", SVG_1X1)]
    formula = Fragment(
        {
            "type": "image",
            "src": "memory://formula",
            "width": 8,
            "height": 4,
        },
        fragment_resources,
    )
    fragment_resources.append(ImageResource("memory://fragment-later", b"later"))
    provided_resources = [ImageResource("memory://page", b"page")]
    provided_styles = [".formula { color: black; }"]
    provided_keyframes = {
        "fade": {
            "from": {"opacity": 0},
            "to": {"opacity": 1},
        }
    }
    node: dict[str, object] = {
        "type": "container",
        "style": {"width": "16px"},
        "children": [
            formula,
            {
                "type": "container",
                "children": [formula],
            },
        ],
    }

    document = Document.from_node(
        node,
        resources=provided_resources,
        stylesheets=provided_styles,
        keyframes=provided_keyframes,
    )
    node["style"] = {"width": "999px"}
    provided_children = cast(list[object], node["children"])
    provided_children.clear()
    formula.node["width"] = 100
    provided_resources.append(ImageResource("memory://later", b"later"))
    provided_styles.append(".formula { color: red; }")
    provided_keyframes["fade"]["from"]["opacity"] = 1

    snapshot = document.node
    assert snapshot is not None
    assert snapshot["style"] == {"width": "16px"}
    children = cast(list[dict[str, object]], snapshot["children"])
    assert children[0]["width"] == 8
    nested = cast(list[dict[str, object]], children[1]["children"])
    assert nested[0]["width"] == 8
    assert document.resources.images == (
        ImageResource("memory://page", b"page"),
        ImageResource("memory://formula", SVG_1X1),
    )
    assert document.stylesheets == (".formula { color: black; }",)
    assert document.keyframes == {
        "fade": {
            "from": {"opacity": 0},
            "to": {"opacity": 1},
        }
    }

    exposed = document.node
    assert exposed is not None
    exposed["style"] = {"width": "1px"}
    reloaded = document.node
    assert reloaded is not None
    assert reloaded["style"] == {"width": "16px"}
    exposed_keyframes = document.keyframes
    assert isinstance(exposed_keyframes, dict)
    exposed_keyframes.clear()
    reloaded_keyframes = document.keyframes
    assert isinstance(reloaded_keyframes, dict)
    assert reloaded_keyframes["fade"]["from"]["opacity"] == 0


def test_from_node_rejects_resource_conflicts_across_fragments() -> None:
    fragment = Fragment(
        {"type": "image", "src": "memory://formula"},
        ResourceSet([ImageResource("memory://formula", b"fragment")]),
    )

    with pytest.raises(ResourceError, match="conflicting image resources"):
        Document.from_node(
            {"type": "container", "children": [fragment]},
            resources=[ImageResource("memory://formula", b"document")],
        )


@pytest.mark.parametrize("constructor", ["node", "html"])
def test_document_rejects_string_stylesheets(constructor: str) -> None:
    with pytest.raises(TypeError, match="not a string"):
        if constructor == "node":
            Document.from_node(
                {"type": "container", "children": []},
                stylesheets=cast(Any, ".card { color: red; }"),
            )
        else:
            Document.from_html(
                "<div>hello</div>",
                stylesheets=cast(Any, ".card { color: red; }"),
            )


@pytest.mark.parametrize("constructor", ["node", "html"])
def test_document_rejects_non_string_stylesheet_values(constructor: str) -> None:
    with pytest.raises(TypeError, match=r"stylesheets\[1\]"):
        if constructor == "node":
            Document.from_node(
                {"type": "container", "children": []},
                stylesheets=cast(Any, [".card { color: red; }", 42]),
            )
        else:
            Document.from_html(
                "<div>hello</div>",
                stylesheets=cast(Any, [".card { color: red; }", 42]),
            )


def test_from_html_requires_string_source() -> None:
    with pytest.raises(TypeError, match="html must be a string"):
        Document.from_html(cast(Any, 42))


def test_from_html_keeps_only_explicit_resources() -> None:
    explicit = ImageResource("memory://explicit", SVG_1X1)
    html = '<div><img src="memory://implicit"><span>$x$ and **markdown**</span></div>'

    document = Document.from_html(
        html,
        resources=[explicit],
        stylesheets=[".inline { color: black; }"],
    )

    assert document.html == html
    assert document.node is None
    assert document.resources.images == (explicit,)
    assert document.stylesheets == (".inline { color: black; }",)


def test_document_rejects_cyclic_node_trees() -> None:
    node: dict[str, Any] = {"type": "container", "children": []}
    node["children"].append(node)

    with pytest.raises(NodeValidationError, match="cycle"):
        Document.from_node(node)


def test_fragment_rejects_excessive_node_depth() -> None:
    node: dict[str, Any] = {"type": "text", "text": "deep"}
    for _ in range(520):
        node = {"type": "container", "children": [node]}

    with pytest.raises(NodeValidationError, match="512 levels"):
        Fragment(node)


def test_compile_document_merges_css_in_cascade_order() -> None:
    document = Document.from_node(
        {
            "type": "container",
            "className": "card",
            "children": [],
        },
        stylesheets=[
            ".card { width: 20px; height: 12px; }",
            ".card { width: 40px; }",
        ],
    )

    compiled = compile_document(document)
    measured = Renderer().measure_compiled(
        compiled.node,
        stylesheets=compiled.stylesheets,
        width=None,
        height=None,
    )

    assert len(compiled.stylesheets) == 1
    assert (measured.width, measured.height) == (40.0, 12.0)


def test_compiled_document_freezes_public_constructor_inputs() -> None:
    base = compile_document(
        Document.from_node(
            {"type": "container", "className": "box", "children": []},
            stylesheets=[".box { width: 4px; height: 4px; }"],
        )
    )
    stylesheets = [base.stylesheets[0]]
    image = ImageResource("memory://logo", b"data")
    resources = [image]

    compiled = CompiledDocument(base.node, stylesheets, resources)
    stylesheets.clear()
    resources.append(ImageResource("memory://other", b"other"))

    assert compiled.stylesheets == (base.stylesheets[0],)
    assert compiled.resources.images == (image,)
    with pytest.raises(ValueError, match="at most one"):
        CompiledDocument(base.node, [base.stylesheets[0], base.stylesheets[0]], [])


def test_compile_document_uses_html_lossy_and_node_strict_css() -> None:
    invalid_css = "a { display: weird; }"
    html_document = Document.from_html(
        '<div class="card"></div>',
        stylesheets=[invalid_css, ".card { width: 9px; height: 5px; }"],
    )
    html_compiled = compile_document(html_document)

    measured = Renderer().measure_compiled(
        html_compiled.node,
        stylesheets=html_compiled.stylesheets,
        width=None,
        height=None,
    )
    assert (measured.width, measured.height) == (9.0, 5.0)

    node_document = Document.from_node(
        {"type": "container", "children": []},
        stylesheets=[invalid_css],
    )
    with pytest.raises(StyleSheetError):
        compile_document(node_document)


@pytest.mark.parametrize("source", ["node", "html"])
def test_compiled_document_merges_keyframes_after_css(source: str) -> None:
    stylesheets = [
        """
        .box {
          width: 8px;
          height: 8px;
          background-color: black;
          animation-name: fade;
          animation-duration: 1000ms;
          animation-fill-mode: both;
        }
        """
    ]
    keyframes = {
        "fade": {
            "from": {"opacity": 0},
            "to": {"opacity": 1},
        }
    }
    if source == "node":
        document = Document.from_node(
            {"type": "container", "className": "box", "children": []},
            stylesheets=stylesheets,
            keyframes=keyframes,
        )
    else:
        document = Document.from_html(
            '<div class="box"></div>',
            stylesheets=stylesheets,
            keyframes=keyframes,
        )
    keyframes["fade"]["from"]["opacity"] = 1
    compiled = compile_document(document)
    renderer = Renderer()

    first = renderer.render_compiled(
        compiled.node,
        stylesheets=compiled.stylesheets,
        width=8,
        height=8,
        format="raw",
        time_ms=0,
    )
    last = renderer.render_compiled(
        compiled.node,
        stylesheets=compiled.stylesheets,
        width=8,
        height=8,
        format="raw",
        time_ms=1000,
    )

    assert len(compiled.stylesheets) == 1
    assert first != last


def test_fragment_resources_are_reused_when_rendering() -> None:
    formula = Fragment(
        {
            "type": "image",
            "src": "memory://formula",
            "width": 1,
            "height": 1,
        },
        ResourceSet([ImageResource("memory://formula", SVG_1X1)]),
    )
    document = Document.from_node(
        {
            "type": "container",
            "style": {"width": "4px", "height": "4px"},
            "children": [formula, formula],
        }
    )
    compiled = compile_document(document)

    png = Renderer().render_compiled(
        compiled.node,
        stylesheets=compiled.stylesheets,
        width=4,
        height=4,
        images=compiled.resources.images,
    )

    assert compiled.resources.images == (ImageResource("memory://formula", SVG_1X1),)
    assert png.startswith(b"\x89PNG")
