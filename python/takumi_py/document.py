from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Generic, TypeVar, cast

from takumi_py import _core
from takumi_py.exceptions import NodeValidationError, ResourceError
from takumi_py.options import (
    HtmlOptions,
    ImageResource,
    ImageResourceInput,
    KeyframesInput,
    normalize_image_resource,
)
from takumi_py.types import CompiledNode, CompiledStyleSheet

__all__ = [
    "CompiledDocument",
    "Document",
    "Fragment",
    "ResourceSet",
    "compile_document",
]

NodeT = TypeVar("NodeT")
_MAX_SNAPSHOT_DEPTH = 512
_OPAQUE_TYPES = (_core.CompiledNode, _core.CompiledStyleSheet)


@dataclass(frozen=True, slots=True, init=False)
class ResourceSet:
    """An immutable, ordered snapshot of image resources.

    Exact duplicate resources are collapsed. A source may appear only once
    unless every duplicate has identical bytes and cache policy.

    Attributes:
        images: Image resources in first-seen order.
    """

    images: tuple[ImageResource, ...]

    def __init__(self, images: Iterable[ImageResourceInput] = ()) -> None:
        """Create a snapshot, copying resource bytes and validating conflicts.

        Args:
            images: Image resources or ``(src, bytes)`` pairs.

        Raises:
            ResourceError: If one source names different bytes or cache modes.
        """
        unique: dict[str, ImageResource] = {}
        for image in images:
            normalized = normalize_image_resource(image)
            if not isinstance(normalized.src, str):
                raise TypeError("image resource src must be a string")
            if normalized.cache not in ("auto", "none"):
                raise ValueError("image resource cache must be 'auto' or 'none'")
            snapshot = ImageResource(
                src=normalized.src,
                data=_snapshot_image_data(normalized.data),
                cache=normalized.cache,
            )
            previous = unique.get(snapshot.src)
            if previous is None:
                unique[snapshot.src] = snapshot
                continue
            if previous != snapshot:
                raise ResourceError(
                    f"conflicting image resources for src {snapshot.src!r}: "
                    "bytes and cache must match"
                )
        object.__setattr__(self, "images", tuple(unique.values()))

    def __iter__(self) -> Iterator[ImageResource]:
        return iter(self.images)

    def __len__(self) -> int:
        return len(self.images)


_EMPTY_RESOURCES = ResourceSet()


@dataclass(frozen=True, slots=True, init=False)
class Fragment(Generic[NodeT]):
    """A node fragment that carries image resources for composition.

    A ``Document`` expands fragments wherever they occur and merges their
    resource snapshots into the document.

    Attributes:
        node: Generic node value associated with the fragment.
        resources: Image resources owned by the fragment.
    """

    _node: NodeT
    resources: ResourceSet

    def __init__(
        self,
        node: NodeT,
        resources: ResourceSet | Iterable[ImageResourceInput] = _EMPTY_RESOURCES,
    ) -> None:
        object.__setattr__(self, "_node", cast(NodeT, _snapshot_value(node)))
        object.__setattr__(self, "resources", _resource_set(resources))

    @property
    def node(self) -> NodeT:
        """Return a defensive copy of the fragment node."""
        return cast(NodeT, _snapshot_value(self._node))


@dataclass(frozen=True, slots=True, init=False)
class Document:
    """An immutable snapshot of node or HTML input and its document resources.

    Node documents are compiled with strict CSS parsing. HTML documents use the
    lossy CSS parser appropriate for browser-authored stylesheets.

    Attributes:
        resources: Image resources available while rendering the document.
        stylesheets: CSS source strings in cascade order.
    """

    _node: dict[str, object] | None
    _html: str | None
    resources: ResourceSet
    stylesheets: tuple[str, ...]
    _keyframes: KeyframesInput | None
    _html_options: HtmlOptions | None

    def __init__(
        self,
        *,
        _node: dict[str, object] | None,
        _html: str | None,
        resources: ResourceSet | Iterable[ImageResourceInput],
        stylesheets: Iterable[str],
        _keyframes: KeyframesInput | None,
        _html_options: HtmlOptions | None,
    ) -> None:
        if _html is not None and not isinstance(_html, str):
            raise TypeError("html must be a string")
        object.__setattr__(self, "_node", _node)
        object.__setattr__(self, "_html", _html)
        object.__setattr__(self, "resources", _resource_set(resources))
        object.__setattr__(self, "stylesheets", _snapshot_stylesheets(stylesheets))
        object.__setattr__(self, "_keyframes", _snapshot_keyframes(_keyframes))
        object.__setattr__(
            self,
            "_html_options",
            None if _html_options is None else deepcopy(_html_options),
        )

    @classmethod
    def from_node(
        cls,
        node: Fragment[NodeT] | Mapping[str, object],
        *,
        resources: ResourceSet | Iterable[ImageResourceInput] = _EMPTY_RESOURCES,
        stylesheets: Iterable[str] = (),
        keyframes: KeyframesInput | None = None,
    ) -> Document:
        """Snapshot a node tree, expanding fragments and collecting resources.

        Args:
            node: Node mapping or a fragment containing one.
            resources: Document-level image resources.
            stylesheets: CSS source strings in cascade order.
            keyframes: Structured animation rules appended after stylesheets.

        Returns:
            An immutable document snapshot.

        Raises:
            ResourceError: If resources for one source conflict.
            TypeError: If fragment expansion does not produce a node mapping.
        """
        base_resources = _resource_set(resources)
        resource_images = list(base_resources.images)
        snapshot = _snapshot_value(node, resource_images=resource_images)
        if not isinstance(snapshot, dict):
            raise TypeError("node must resolve to a mapping")
        return cls(
            _node=snapshot,
            _html=None,
            resources=ResourceSet(resource_images),
            stylesheets=stylesheets,
            _keyframes=keyframes,
            _html_options=None,
        )

    @classmethod
    def from_html(
        cls,
        html: str,
        *,
        resources: ResourceSet | Iterable[ImageResourceInput] = _EMPTY_RESOURCES,
        stylesheets: Iterable[str] = (),
        keyframes: KeyframesInput | None = None,
        html_options: HtmlOptions | None = None,
    ) -> Document:
        """Snapshot HTML and the explicitly supplied document resources.

        The HTML is not scanned for formulas, Markdown, image bytes, or resource
        declarations. Images must be supplied through ``resources``.

        Args:
            html: HTML fragment or document source.
            resources: Image resources explicitly made available to the HTML.
            stylesheets: CSS source strings in cascade order.
            keyframes: Structured animation rules appended after stylesheets.
            html_options: HTML parsing configuration.

        Returns:
            An immutable document snapshot.
        """
        if not isinstance(html, str):
            raise TypeError("html must be a string")
        return cls(
            _node=None,
            _html=html,
            resources=_resource_set(resources),
            stylesheets=stylesheets,
            _keyframes=keyframes,
            _html_options=html_options,
        )

    @property
    def node(self) -> dict[str, object] | None:
        """Return a defensive node copy, or ``None`` for an HTML document."""
        return None if self._node is None else _copy_node(self._node)

    @property
    def html(self) -> str | None:
        """Return the HTML source, or ``None`` for a node document."""
        return self._html

    @property
    def keyframes(self) -> KeyframesInput | None:
        """Return a defensive copy of structured keyframes."""
        return _snapshot_keyframes(self._keyframes)

    @property
    def html_options(self) -> HtmlOptions | None:
        """Return a defensive copy of HTML parser options."""
        if self._html_options is None:
            return None
        return deepcopy(self._html_options)


@dataclass(frozen=True, slots=True, init=False)
class CompiledDocument:
    """Native nodes and merged styles ready for rendering.

    Attributes:
        node: Compiled native root node.
        stylesheets: Zero or one merged native stylesheet.
        resources: Immutable image-resource snapshot.
    """

    node: CompiledNode
    stylesheets: tuple[CompiledStyleSheet, ...]
    resources: ResourceSet

    def __init__(
        self,
        node: CompiledNode,
        stylesheets: Iterable[CompiledStyleSheet],
        resources: ResourceSet | Iterable[ImageResourceInput],
    ) -> None:
        if not isinstance(node, _core.CompiledNode):
            raise TypeError("node must be a CompiledNode")
        if isinstance(stylesheets, str):
            raise TypeError("stylesheets must be an iterable of CompiledStyleSheet")
        snapshot = tuple(stylesheets)
        if any(
            not isinstance(stylesheet, _core.CompiledStyleSheet)
            for stylesheet in snapshot
        ):
            raise TypeError("stylesheets must contain only CompiledStyleSheet values")
        if len(snapshot) > 1:
            raise ValueError("stylesheets must contain at most one merged stylesheet")
        object.__setattr__(self, "node", node)
        object.__setattr__(self, "stylesheets", snapshot)
        object.__setattr__(self, "resources", _resource_set(resources))


def compile_document(document: Document) -> CompiledDocument:
    """Compile a document without creating or depending on a ``Renderer``.

    Args:
        document: Immutable document snapshot.

    Returns:
        Compiled node, merged stylesheet, and resource snapshot.

    Raises:
        HtmlParseError: If HTML parsing fails.
        NodeDecodeError: If a node mapping is invalid.
        StyleSheetError: If strict node CSS or structured keyframes are invalid.
    """
    if not isinstance(document, Document):
        raise TypeError("document must be a Document")

    strict_stylesheet = True
    if document._html is None:
        if document._node is None:
            raise RuntimeError("document has neither node nor HTML source")
        node = _core.compile_node(_copy_node(document._node))
    else:
        html_options = document._html_options or HtmlOptions()
        node = _core.compile_html(
            document._html,
            presets=html_options.presets,
            tailwind_property=html_options.tailwind_property,
            max_depth=html_options.max_depth,
        )
        strict_stylesheet = False

    compiled_stylesheets = [
        _core.compile_stylesheet(css, strict=strict_stylesheet)
        for css in document.stylesheets
    ]
    if document._keyframes is not None:
        compiled_stylesheets.append(_core.compile_keyframes(document.keyframes))

    stylesheets = (
        ()
        if not compiled_stylesheets
        else (_core.merge_stylesheets(compiled_stylesheets),)
    )
    return CompiledDocument(
        node=node,
        stylesheets=stylesheets,
        resources=document.resources,
    )


def _resource_set(
    resources: ResourceSet | Iterable[ImageResourceInput],
) -> ResourceSet:
    if isinstance(resources, ResourceSet):
        return resources
    return ResourceSet(resources)


def _snapshot_image_data(data: object) -> bytes:
    if isinstance(data, bytes):
        return data
    if isinstance(data, int):
        raise TypeError("image resource data must be bytes-like, not an integer")
    try:
        return memoryview(cast(Any, data)).tobytes()
    except (TypeError, ValueError) as error:
        raise TypeError("image resource data must be bytes-like") from error


def _snapshot_stylesheets(stylesheets: Iterable[str]) -> tuple[str, ...]:
    if isinstance(stylesheets, str):
        raise TypeError("stylesheets must be an iterable of CSS strings, not a string")
    snapshot: list[str] = []
    for index, css in enumerate(stylesheets):
        if not isinstance(css, str):
            raise TypeError(f"stylesheets[{index}] must be a string")
        snapshot.append(css)
    return tuple(snapshot)


def _snapshot_keyframes(keyframes: KeyframesInput | None) -> KeyframesInput | None:
    if keyframes is None:
        return None
    return cast(KeyframesInput, _snapshot_value(keyframes))


def _snapshot_value(
    value: object,
    *,
    resource_images: list[ImageResource] | None = None,
    depth: int = 0,
    active: set[int] | None = None,
) -> object:
    if depth > _MAX_SNAPSHOT_DEPTH:
        raise NodeValidationError(f"node nesting exceeds {_MAX_SNAPSHOT_DEPTH} levels")
    if isinstance(value, _OPAQUE_TYPES):
        return value
    active = set() if active is None else active
    if isinstance(value, Fragment):
        identity = id(value)
        _enter_snapshot_container(identity, active)
        if resource_images is not None:
            resource_images.extend(value.resources.images)
        try:
            node = _snapshot_value(
                value._node,
                resource_images=resource_images,
                depth=depth + 1,
                active=active,
            )
        finally:
            active.remove(identity)
        if resource_images is None:
            return _fragment_from_snapshot(node, value.resources)
        return node
    if isinstance(value, Mapping):
        identity = id(value)
        _enter_snapshot_container(identity, active)
        try:
            mapping_snapshot: dict[object, object] = {}
            for key, item in value.items():
                snapshot_key = _snapshot_value(
                    key,
                    resource_images=None,
                    depth=depth + 1,
                    active=active,
                )
                mapping_snapshot[snapshot_key] = (
                    [
                        _snapshot_value(
                            child,
                            resource_images=resource_images,
                            depth=depth + 2,
                            active=active,
                        )
                        for child in item
                    ]
                    if key == "children"
                    and isinstance(item, Sequence)
                    and not isinstance(item, (str, bytes, bytearray))
                    else _snapshot_value(
                        item,
                        resource_images=resource_images,
                        depth=depth + 1,
                        active=active,
                    )
                )
            return mapping_snapshot
        finally:
            active.remove(identity)
    if isinstance(value, list):
        identity = id(value)
        _enter_snapshot_container(identity, active)
        try:
            return [
                _snapshot_value(
                    item,
                    resource_images=resource_images,
                    depth=depth + 1,
                    active=active,
                )
                for item in value
            ]
        finally:
            active.remove(identity)
    if isinstance(value, tuple):
        identity = id(value)
        _enter_snapshot_container(identity, active)
        try:
            return tuple(
                _snapshot_value(
                    item,
                    resource_images=resource_images,
                    depth=depth + 1,
                    active=active,
                )
                for item in value
            )
        finally:
            active.remove(identity)
    if isinstance(value, (set, frozenset)):
        identity = id(value)
        _enter_snapshot_container(identity, active)
        try:
            items = set()
            for item in value:
                items.add(
                    _snapshot_value(
                        item,
                        resource_images=resource_images,
                        depth=depth + 1,
                        active=active,
                    )
                )
        finally:
            active.remove(identity)
        return frozenset(items) if isinstance(value, frozenset) else items
    if isinstance(value, (bytearray, memoryview)):
        return bytes(value)
    return value


def _enter_snapshot_container(identity: int, active: set[int]) -> None:
    if identity in active:
        raise NodeValidationError("node contains a cycle")
    active.add(identity)


def _fragment_from_snapshot(node: object, resources: ResourceSet) -> Fragment[object]:
    fragment = object.__new__(Fragment)
    object.__setattr__(fragment, "_node", node)
    object.__setattr__(fragment, "resources", resources)
    return cast(Fragment[object], fragment)


def _copy_node(node: Mapping[str, object]) -> dict[str, object]:
    return cast(dict[str, object], _snapshot_value(node))
