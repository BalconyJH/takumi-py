from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, NotRequired, TypeAlias, TypedDict, cast

import msgspec

from takumi_py import _core
from takumi_py.exceptions import NodeDecodeError, NodeValidationError
from takumi_py.options import StyleMap

CompiledNode: TypeAlias = _core.CompiledNode
CompiledStyleSheet: TypeAlias = _core.CompiledStyleSheet
_MAX_NODE_DEPTH = 512

if TYPE_CHECKING:
    from takumi_py._core import _MeasuredNodeOutput


class NodeBase(TypedDict, total=False):
    """Fields shared by every node type.

    Attributes:
        tagName: Element name used by type, class, and attribute selectors.
        className: Class attribute used by class selectors.
        id: Identifier used by ID selectors.
        attributes: Additional HTML attributes exposed to selectors.
        style: Inline CSS declarations with camel-cased property names.
        tw: Tailwind classes attached to the node.
        dir: Text direction for this subtree.
        lang: BCP-47 language tag for this subtree.
    """

    tagName: str
    className: str
    id: str
    attributes: dict[str, str]
    style: StyleMap
    tw: str
    dir: Literal["ltr", "rtl"]
    lang: str


class TextNode(NodeBase):
    """A text leaf node.

    Attributes:
        text: Text content to lay out and paint.
    """

    type: Literal["text"]
    text: str


class RawRgbaImage(TypedDict):
    """Raw row-major RGBA pixels used directly as an image node source.

    Attributes:
        width: Image width in pixels.
        height: Image height in pixels.
        data: Exactly ``width * height * 4`` bytes in RGBA channel order.
        premultiplied: Whether RGB channels already include alpha
            multiplication. Defaults to ``False``.
    """

    width: int
    height: int
    data: bytes
    premultiplied: NotRequired[bool]


class ImageNode(NodeBase):
    """An image leaf node.

    Attributes:
        src: Image identifier, encoded image bytes, or raw RGBA pixels.
        width: Rendered width in CSS pixels.
        height: Rendered height in CSS pixels.
    """

    type: Literal["image"]
    src: str | bytes | RawRgbaImage
    width: NotRequired[float]
    height: NotRequired[float]


class ContainerNode(NodeBase):
    """A container that lays out child nodes.

    Attributes:
        children: Child nodes in document order.
    """

    type: Literal["container"]
    children: NotRequired[list[Node]]


Node: TypeAlias = TextNode | ImageNode | ContainerNode
NodeInput: TypeAlias = Node | dict[str, object]


class _NodeKind(TypedDict):
    type: Literal["text", "image", "container"]


class _ContainerNodeInput(NodeBase):
    type: Literal["container"]
    children: NotRequired[list[object]]


class _ImageNodeInput(NodeBase):
    type: Literal["image"]
    src: object
    width: NotRequired[float]
    height: NotRequired[float]


@dataclass(frozen=True, slots=True)
class MeasuredTextRun:
    """One shaped text run from a layout measurement.

    Attributes:
        text: Text covered by the run.
        x: Left edge in layout coordinates.
        y: Top edge in layout coordinates.
        width: Run width in layout units.
        height: Run height in layout units.
    """

    text: str
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True, slots=True)
class MeasuredNode:
    """An immutable node in a measured layout tree.

    Attributes:
        width: Box width in layout units.
        height: Box height in layout units.
        transform: Six values for the node's 2D affine transform.
        children: Measured child nodes.
        runs: Text runs laid out directly on this node.
    """

    width: float
    height: float
    transform: tuple[float, float, float, float, float, float]
    children: tuple[MeasuredNode, ...]
    runs: tuple[MeasuredTextRun, ...]


@dataclass(frozen=True, slots=True)
class AnimationScene:
    """One timed scene in a rendered animation sequence.

    Attributes:
        node: A Python node mapping or an already compiled node.
        duration_ms: Positive scene duration in milliseconds.
    """

    node: NodeInput | CompiledNode
    duration_ms: int


@dataclass(frozen=True, slots=True)
class RawAnimationFrame:
    """A pre-rendered RGBA frame for ``Renderer.encode_frames``.

    Attributes:
        data: Exactly ``width * height * 4`` row-major RGBA bytes.
        width: Frame width in pixels.
        height: Frame height in pixels.
        duration_ms: Positive frame duration in milliseconds.
    """

    data: bytes
    width: int
    height: int
    duration_ms: int


def validate_node(node: object) -> Node:
    """Validate and normalize a node mapping in Python.

    Args:
        node: A mapping with a ``type`` of ``"text"``, ``"image"``, or
            ``"container"``.

    Returns:
        A typed node mapping normalized through msgspec.

    Raises:
        NodeValidationError: If the mapping does not match a supported node
            shape.
    """
    try:
        normalized: dict[int, Node] = {}
        subtree_heights: dict[int, int] = {}
        containers: dict[int, _ContainerNodeInput] = {}
        child_ids: dict[int, list[int]] = {}
        active: set[int] = set()
        stack: list[tuple[object, int, bool]] = [(node, 1, False)]

        while stack:
            current, depth, expanded = stack.pop()
            identity = id(current)

            if expanded:
                container = containers.pop(identity)
                identities = child_ids.pop(identity)
                children = [normalized[child_identity] for child_identity in identities]
                container["children"] = cast(list[object], children)
                active.remove(identity)
                height = 1 + max(
                    (subtree_heights[child_identity] for child_identity in identities),
                    default=0,
                )
                if depth + height - 1 > _MAX_NODE_DEPTH:
                    raise NodeValidationError(
                        f"nodes nest deeper than {_MAX_NODE_DEPTH} levels"
                    )
                normalized[identity] = cast(ContainerNode, container)
                subtree_heights[identity] = height
                continue

            if identity in active:
                raise NodeValidationError("node contains a cycle")
            if depth > _MAX_NODE_DEPTH:
                raise NodeValidationError(
                    f"nodes nest deeper than {_MAX_NODE_DEPTH} levels"
                )
            if identity in normalized:
                height = subtree_heights[identity]
                if depth + height - 1 > _MAX_NODE_DEPTH:
                    raise NodeValidationError(
                        f"nodes nest deeper than {_MAX_NODE_DEPTH} levels"
                    )
                continue

            kind = msgspec.convert(current, type=_NodeKind)["type"]
            if kind == "text":
                normalized[identity] = msgspec.convert(current, type=TextNode)
                subtree_heights[identity] = 1
                continue
            if kind == "image":
                image = msgspec.convert(current, type=_ImageNodeInput)
                source = image["src"]
                if isinstance(source, dict):
                    image["src"] = msgspec.convert(source, type=RawRgbaImage)
                elif not isinstance(source, (str, bytes)):
                    raise NodeValidationError(
                        "image src must be a string, bytes, or raw RGBA mapping"
                    )
                normalized[identity] = cast(ImageNode, image)
                subtree_heights[identity] = 1
                continue

            source = cast(Mapping[str, object], current)
            raw_children = source.get("children")
            if raw_children is None:
                container = msgspec.convert(source, type=_ContainerNodeInput)
                normalized[identity] = cast(ContainerNode, container)
                subtree_heights[identity] = 1
                continue
            if not isinstance(raw_children, Sequence) or isinstance(
                raw_children, (str, bytes, bytearray, memoryview)
            ):
                msgspec.convert(source, type=_ContainerNodeInput)
                raise NodeValidationError("children must be an array")

            identities = [id(child) for child in raw_children]
            active.add(identity)
            container_source = dict(source)
            container_source["children"] = []
            containers[identity] = msgspec.convert(
                container_source,
                type=_ContainerNodeInput,
            )
            child_ids[identity] = identities
            stack.append((current, depth, True))
            stack.extend((child, depth + 1, False) for child in reversed(raw_children))

        return normalized[id(node)]
    except msgspec.ValidationError as error:
        raise NodeValidationError(str(error)) from error
    except RecursionError as error:
        raise NodeValidationError(
            f"nodes exceed the supported nesting depth of {_MAX_NODE_DEPTH}"
        ) from error


def measured_node_from_mapping(data: _MeasuredNodeOutput) -> MeasuredNode:
    measured: dict[int, MeasuredNode] = {}
    stack: list[tuple[_MeasuredNodeOutput, bool]] = [(data, False)]

    while stack:
        current, expanded = stack.pop()
        identity = id(current)
        if not expanded:
            stack.append((current, True))
            stack.extend((child, False) for child in reversed(current["children"]))
            continue

        transform = tuple(current["transform"])
        if len(transform) != 6:
            raise NodeDecodeError("measured node transform must contain six values")
        measured[identity] = MeasuredNode(
            width=float(current["width"]),
            height=float(current["height"]),
            transform=transform,
            children=tuple(measured[id(child)] for child in current["children"]),
            runs=tuple(
                MeasuredTextRun(
                    text=run["text"],
                    x=run["x"],
                    y=run["y"],
                    width=run["width"],
                    height=run["height"],
                )
                for run in current["runs"]
            ),
        )

    return measured[id(data)]
