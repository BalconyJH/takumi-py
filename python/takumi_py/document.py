from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
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
_DEFAULT_NODE_DEPTH_LIMIT = 512
# A node level is two structural levels in the snapshot: its mapping and its
# children sequence. Keep enough headroom for nested style metadata while
# preserving Takumi's node-specific depth limit.
_MAX_SNAPSHOT_DEPTH = 2 * _DEFAULT_NODE_DEPTH_LIMIT + 32
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

    def merged(
        self,
        *others: ResourceSet | Iterable[ImageResourceInput],
    ) -> ResourceSet:
        """Return a snapshot with these resources followed by ``others``.

        Existing resources keep their first-seen order. A later resource with
        the same ``src`` must be identical or construction raises
        ``ResourceError``.
        """
        images = list(self.images)
        for other in others:
            images.extend(_resource_set(other).images)
        return ResourceSet(images)


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
        object.__setattr__(
            self,
            "_node",
            cast(NodeT, _snapshot_value_checked(node, allow_opaque=True)),
        )
        object.__setattr__(self, "resources", _resource_set(resources))

    @property
    def node(self) -> NodeT:
        """Return a defensive copy of the fragment node."""
        return cast(NodeT, _snapshot_value_checked(self._node, allow_opaque=True))


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
        if (_node is None) == (_html is None):
            raise ValueError("exactly one of node or html must be provided")
        if _html is not None and not isinstance(_html, str):
            raise TypeError("html must be a string")

        if _node is not None:
            if not isinstance(_node, Mapping):
                raise TypeError("node must be a mapping")
            node_snapshot = _snapshot_value_checked(_node)
            if not isinstance(node_snapshot, dict):
                raise TypeError("node must be a mapping")
        else:
            node_snapshot = None

        self._set_snapshot_state(
            node=node_snapshot,
            html=_html,
            resources=_resource_set(resources),
            stylesheets=_snapshot_stylesheets(stylesheets),
            keyframes=_snapshot_keyframes(_keyframes),
            html_options=_html_options,
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
        snapshot = _snapshot_value_checked(node, resource_images=resource_images)
        if not isinstance(snapshot, dict):
            raise TypeError("node must resolve to a mapping")
        document = cast(Document, object.__new__(cls))
        document._set_snapshot_state(
            node=snapshot,
            html=None,
            resources=ResourceSet(resource_images),
            stylesheets=_snapshot_stylesheets(stylesheets),
            keyframes=_snapshot_keyframes(keyframes),
            html_options=None,
        )
        return document

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

    def _set_snapshot_state(
        self,
        *,
        node: dict[str, object] | None,
        html: str | None,
        resources: ResourceSet,
        stylesheets: tuple[str, ...],
        keyframes: KeyframesInput | None,
        html_options: HtmlOptions | None,
    ) -> None:
        object.__setattr__(self, "_node", node)
        object.__setattr__(self, "_html", html)
        object.__setattr__(self, "resources", resources)
        object.__setattr__(self, "stylesheets", stylesheets)
        object.__setattr__(self, "_keyframes", keyframes)
        object.__setattr__(
            self,
            "_html_options",
            None if html_options is None else deepcopy(html_options),
        )


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
    _native_resources: _core.CompiledResources = field(repr=False, compare=False)

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
        resource_snapshot = _resource_set(resources)
        self._set_compiled_state(
            node=node,
            stylesheets=snapshot,
            resources=resource_snapshot,
            native_resources=_core.compile_resources(resource_snapshot.images),
        )

    def _set_compiled_state(
        self,
        *,
        node: CompiledNode,
        stylesheets: tuple[CompiledStyleSheet, ...],
        resources: ResourceSet,
        native_resources: _core.CompiledResources,
    ) -> None:
        object.__setattr__(self, "node", node)
        object.__setattr__(self, "stylesheets", stylesheets)
        object.__setattr__(self, "resources", resources)
        object.__setattr__(self, "_native_resources", native_resources)

    def resource_urls(self) -> tuple[str, ...]:
        """Return known image references discovered by the native compiler.

        URLs are deduplicated and sorted so callers receive a stable discovery
        result. Upstream reports references in parsed node metadata, inline
        styles, and compiled declaration blocks; unresolved constructs such as
        values reached only through CSS variables are outside this guarantee.
        Embedded image bytes are not URLs and therefore do not appear.
        """
        urls = set(self.node.resource_urls())
        for stylesheet in self.stylesheets:
            urls.update(stylesheet.resource_urls())
        return tuple(sorted(urls))

    def missing_resources(self) -> tuple[str, ...]:
        """Return referenced external image URLs absent from ``resources``.

        Discovery is conservative. It reports URLs that are not supplied by an
        ``ImageResource`` with the same ``src``, while ignoring data URLs and
        inline SVG markup, which are self-contained. A missing URL is diagnostic
        information; rendering remains responsible for resolving or skipping it.
        """
        supplied = {resource.src for resource in self.resources.images}
        return tuple(
            url
            for url in self.resource_urls()
            if not _is_embedded_image_reference(url) and url not in supplied
        )

    def with_resources(
        self,
        resources: ResourceSet | Iterable[ImageResourceInput],
    ) -> CompiledDocument:
        """Return a compiled document with additional image resources attached.

        The original value is unchanged. Node and stylesheet handles are shared
        with the returned document, so compilation is not repeated. Resources
        already present keep their order; conflicting definitions raise
        ``ResourceError``.
        """
        merged = self.resources.merged(resources)
        if merged == self.resources:
            return self
        existing_sources = {resource.src for resource in self.resources.images}
        additions = tuple(
            resource
            for resource in merged.images
            if resource.src not in existing_sources
        )
        compiled = object.__new__(CompiledDocument)
        compiled._set_compiled_state(
            node=self.node,
            stylesheets=self.stylesheets,
            resources=merged,
            native_resources=self._native_resources.merged(additions),
        )
        return compiled


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

    stylesheet_sources = list(document.stylesheets)
    strict_stylesheet = True
    if document._html is None:
        if document._node is None:
            raise RuntimeError("document has neither node nor HTML source")
        node = _core.compile_node(document._node)
    else:
        html_options = document._html_options or HtmlOptions()
        node, embedded_stylesheets = _core.parse_html(
            document._html,
            presets=html_options.presets,
            tailwind_property=html_options.tailwind_property,
            max_depth=html_options.max_depth,
        )
        stylesheet_sources.extend(embedded_stylesheets)
        strict_stylesheet = False

    compiled_stylesheets = [
        _core.compile_stylesheet(css, strict=strict_stylesheet)
        for css in stylesheet_sources
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
    return cast(KeyframesInput, _snapshot_value_checked(keyframes))


def _snapshot_value_checked(
    value: object,
    *,
    resource_images: list[ImageResource] | None = None,
    depth: int = 0,
    active: set[int] | None = None,
    allow_opaque: bool = False,
) -> object:
    try:
        return _snapshot_value(
            value,
            resource_images=resource_images,
            depth=depth,
            active=active,
            allow_opaque=allow_opaque,
        )
    except RecursionError as error:
        raise NodeValidationError("node exceeds the supported nesting depth") from error


def _snapshot_value(
    value: object,
    *,
    resource_images: list[ImageResource] | None = None,
    depth: int = 0,
    active: set[int] | None = None,
    allow_opaque: bool = False,
) -> object:
    if depth > _MAX_SNAPSHOT_DEPTH:
        raise NodeValidationError(
            f"node exceeds the {_MAX_SNAPSHOT_DEPTH}-level structural depth limit"
        )
    if isinstance(value, _OPAQUE_TYPES):
        if allow_opaque:
            return value
        raise NodeValidationError(
            "compiled native values cannot be embedded in a document node"
        )
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
                allow_opaque=allow_opaque,
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
                    allow_opaque=allow_opaque,
                )
                if (
                    key == "children"
                    and isinstance(item, Sequence)
                    and not isinstance(item, (str, bytes, bytearray))
                ):
                    children: list[object] = []
                    for child in item:
                        # Keep this loop in the mapping frame so a tree at
                        # Takumi's 512-node limit does not exhaust Python's
                        # recursion budget with one list-comprehension frame
                        # per node.
                        children.append(  # noqa: PERF401
                            _snapshot_value(
                                child,
                                resource_images=resource_images,
                                depth=depth + 2,
                                active=active,
                                allow_opaque=allow_opaque,
                            )
                        )
                    mapping_snapshot[snapshot_key] = children
                else:
                    mapping_snapshot[snapshot_key] = _snapshot_value(
                        item,
                        resource_images=resource_images,
                        depth=depth + 1,
                        active=active,
                        allow_opaque=allow_opaque,
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
                    allow_opaque=allow_opaque,
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
                    allow_opaque=allow_opaque,
                )
                for item in value
            )
        finally:
            active.remove(identity)
    if isinstance(value, (bytearray, memoryview)):
        return bytes(value)
    if isinstance(value, bytes):
        return value
    if isinstance(value, Sequence) and not isinstance(value, str):
        identity = id(value)
        _enter_snapshot_container(identity, active)
        try:
            return tuple(
                _snapshot_value(
                    item,
                    resource_images=resource_images,
                    depth=depth + 1,
                    active=active,
                    allow_opaque=allow_opaque,
                )
                for item in value
            )
        finally:
            active.remove(identity)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise NodeValidationError(f"unsupported node value type {type(value).__name__!r}")


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
    return cast(dict[str, object], _snapshot_value_checked(node))


def _is_embedded_image_reference(value: str) -> bool:
    return not value or value.startswith("data:") or "<svg" in value
