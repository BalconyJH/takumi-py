from __future__ import annotations

from typing import Literal, TypeAlias
from typing_extensions import NotRequired, TypedDict

import msgpack  # type: ignore[import-untyped]
from pydantic import TypeAdapter, ValidationError

from takumi_py import _core
from takumi_py.exceptions import NodeValidationError

CompiledNode: TypeAlias = _core.CompiledNode
CompiledStyleSheet: TypeAlias = _core.CompiledStyleSheet


class NodeBase(TypedDict, total=False):
    tagName: str
    className: str
    id: str
    attributes: dict[str, str]
    style: dict[str, object]
    tw: str
    dir: Literal["ltr", "rtl"]


class TextNode(NodeBase):
    type: Literal["text"]
    text: str


class ImageNode(NodeBase):
    type: Literal["image"]
    src: str | bytes
    width: NotRequired[float]
    height: NotRequired[float]


class ContainerNode(NodeBase):
    type: Literal["container"]
    children: NotRequired[list[Node]]


Node: TypeAlias = TextNode | ImageNode | ContainerNode

_NODE_ADAPTER: TypeAdapter[Node] = TypeAdapter(Node)


def validate_node(node: object) -> Node:
    try:
        return _NODE_ADAPTER.validate_python(node)
    except ValidationError as error:
        raise NodeValidationError(str(error)) from error


def pack_node(node: Node | dict[str, object], *, validate: bool = False) -> bytes:
    if validate:
        node = validate_node(node)
    return msgpack.packb(node, use_bin_type=True)
