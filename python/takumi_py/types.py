from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, TypeAlias, cast
from typing_extensions import NotRequired, TypedDict

import msgspec

from takumi_py import _core
from takumi_py.exceptions import NodeDecodeError, NodeValidationError
from takumi_py.options import StyleMap

CompiledNode: TypeAlias = _core.CompiledNode
CompiledStyleSheet: TypeAlias = _core.CompiledStyleSheet

if TYPE_CHECKING:
    from takumi_py._core import _MeasuredNodeOutput


class NodeBase(TypedDict, total=False):
    tagName: str
    className: str
    id: str
    attributes: dict[str, str]
    style: StyleMap
    tw: str
    dir: Literal["ltr", "rtl"]
    lang: str


class TextNode(NodeBase):
    type: Literal["text"]
    text: str


class RawRgbaImage(TypedDict):
    """Raw row-major RGBA pixels used directly as an image node source."""

    width: int
    height: int
    data: bytes
    premultiplied: NotRequired[bool]


class ImageNode(NodeBase):
    type: Literal["image"]
    src: str | bytes | RawRgbaImage
    width: NotRequired[float]
    height: NotRequired[float]


class ContainerNode(NodeBase):
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
    text: str
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True, slots=True)
class MeasuredNode:
    width: float
    height: float
    transform: tuple[float, float, float, float, float, float]
    children: tuple[MeasuredNode, ...]
    runs: tuple[MeasuredTextRun, ...]


@dataclass(frozen=True, slots=True)
class AnimationScene:
    node: NodeInput | CompiledNode
    duration_ms: int


@dataclass(frozen=True, slots=True)
class RawAnimationFrame:
    data: bytes
    width: int
    height: int
    duration_ms: int


def validate_node(node: object) -> Node:
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
