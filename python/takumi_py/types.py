from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, NotRequired, TypeAlias, TypedDict, cast

import msgspec

from takumi_py import _core
from takumi_py.exceptions import NodeDecodeError, NodeValidationError
from takumi_py.options import StyleMap

CompiledNode: TypeAlias = _core.CompiledNode
CompiledStyleSheet: TypeAlias = _core.CompiledStyleSheet

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
        kind = msgspec.convert(node, type=_NodeKind)["type"]
        if kind == "text":
            return msgspec.convert(node, type=TextNode)
        if kind == "image":
            image = msgspec.convert(node, type=_ImageNodeInput)
            source = image["src"]
            if isinstance(source, dict):
                image["src"] = msgspec.convert(source, type=RawRgbaImage)
            elif not isinstance(source, (str, bytes)):
                raise NodeValidationError(
                    "image src must be a string, bytes, or raw RGBA mapping"
                )
            return cast(ImageNode, image)

        container = msgspec.convert(node, type=_ContainerNodeInput)
        if "children" in container:
            container["children"] = [
                validate_node(child) for child in container["children"]
            ]
        return cast(ContainerNode, container)
    except msgspec.ValidationError as error:
        raise NodeValidationError(str(error)) from error


def measured_node_from_mapping(data: _MeasuredNodeOutput) -> MeasuredNode:
    children = tuple(measured_node_from_mapping(child) for child in data["children"])
    runs = tuple(
        MeasuredTextRun(
            text=run["text"],
            x=run["x"],
            y=run["y"],
            width=run["width"],
            height=run["height"],
        )
        for run in data["runs"]
    )
    transform = tuple(data["transform"])
    if len(transform) != 6:
        raise NodeDecodeError("measured node transform must contain six values")

    return MeasuredNode(
        width=float(data["width"]),
        height=float(data["height"]),
        transform=transform,
        children=children,
        runs=runs,
    )
