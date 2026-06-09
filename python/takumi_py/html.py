from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from math import isfinite
from typing import Any, cast

from selectolax.lexbor import LexborHTMLParser

from takumi_py.exceptions import HtmlParseError
from takumi_py.types import Node


@dataclass(frozen=True, slots=True)
class ParsedHtml:
    node: Node
    stylesheets: tuple[str, ...]


_DROP_TAGS = {"script", "noscript", "template", "meta", "link"}
_DROP_STYLESHEET_AT_RULES = {"font-face", "view-transition", "-webkit-keyframes"}
_SUPPORTED_DISPLAY_VALUES = {
    "none",
    "flex",
    "inline-flex",
    "grid",
    "inline-grid",
    "inline",
    "block",
    "inline-block",
}


def parse_html(markup: str) -> ParsedHtml:
    try:
        parser = LexborHTMLParser(markup, is_fragment=True)
    except Exception as error:
        raise HtmlParseError(f"failed to parse HTML: {error}") from error

    parent = _document_parent(parser)
    if parent is None:
        return ParsedHtml({"type": "container", "children": []}, ())

    stylesheets: list[str] = []
    for style_node in [
        node for node in _walk_nodes(parent) if _tag_name(node) == "style"
    ]:
        css = style_node.text(deep=True, strip=False)
        sanitized_css = _sanitize_stylesheet(css)
        if sanitized_css.strip():
            stylesheets.append(sanitized_css)
        style_node.decompose()

    for node in [node for node in _walk_nodes(parent) if _tag_name(node) in _DROP_TAGS]:
        node.decompose()

    nodes = [
        converted
        for child in _top_level_nodes(parent)
        if _is_renderable_root(child)
        for converted in [_convert_node(child)]
        if converted is not None
    ]

    if not nodes:
        return ParsedHtml({"type": "container", "children": []}, tuple(stylesheets))

    if len(nodes) == 1:
        return ParsedHtml(nodes[0], tuple(stylesheets))

    return ParsedHtml(
        {
            "type": "container",
            "style": {"width": "100%", "height": "100%"},
            "children": nodes,
        },
        tuple(stylesheets),
    )


def _document_parent(parser: LexborHTMLParser) -> Any | None:
    root = parser.root
    if root is None:
        return None
    return root.parent or root


def _top_level_nodes(parent: Any) -> Iterator[Any]:
    child = parent.child
    while child is not None:
        yield child
        child = child.next


def _child_nodes(node: Any) -> Iterator[Any]:
    child = node.child
    while child is not None:
        yield child
        child = child.next


def _walk_nodes(parent: Any) -> Iterator[Any]:
    for child in _child_nodes(parent):
        yield child
        yield from _walk_nodes(child)


def _tag_name(node: Any) -> str:
    if node.is_text_node or node.is_comment_node:
        return ""
    return str(node.tag).lower()


def _is_renderable_root(node) -> bool:
    if node.is_comment_node:
        return False
    if node.is_text_node:
        return bool(node.text(deep=False, strip=False).strip())
    return True


def _convert_node(node) -> Node | None:
    if node.is_comment_node:
        return None

    if node.is_text_node:
        text = node.text(deep=False, strip=False)
        if not text:
            return None
        return {"type": "text", "text": text}

    tag = str(node.tag).lower()
    attrs = dict(node.attributes or {})

    if tag == "br":
        return {"type": "text", "text": "\n"}

    if tag == "img":
        src = attrs.pop("src", None)
        if not src:
            if _is_hidden_element(attrs):
                return None
            raise HtmlParseError("image element requires a src attribute")

        image_node: dict[str, object] = {
            **_metadata(tag, attrs),
            "type": "image",
            "src": src,
        }
        _set_dimension(image_node, attrs, "width")
        _set_dimension(image_node, attrs, "height")
        return cast("Node", image_node)

    if tag == "svg":
        svg_node: dict[str, object] = {
            **_metadata(tag, attrs),
            "type": "image",
            "src": node.html,
        }
        _set_dimension(svg_node, attrs, "width")
        _set_dimension(svg_node, attrs, "height")
        return cast("Node", svg_node)

    children = [
        converted
        for child in _child_nodes(node)
        for converted in [_convert_node(child)]
        if converted is not None
    ]

    container_node = {
        **_metadata(tag, attrs),
        "type": "container",
        "children": children,
    }
    return cast("Node", container_node)


def _metadata(tag: str, attrs: dict[str, str]) -> dict[str, object]:
    class_name = attrs.pop("className", None) or attrs.pop("class", None)
    node_id = attrs.pop("id", None)
    direction = attrs.pop("dir", None)
    tw = attrs.pop("tw", None)
    style_text = attrs.pop("style", None)

    out: dict[str, object] = {"tagName": tag}
    if class_name:
        out["className"] = class_name
    if node_id:
        out["id"] = node_id
    if direction in {"ltr", "rtl"}:
        out["dir"] = direction
    elif direction:
        attrs["dir"] = direction
    if tw:
        out["tw"] = tw

    style = _parse_inline_style(style_text)
    if style:
        out["style"] = style

    if attrs:
        out["attributes"] = attrs

    return out


def _parse_inline_style(style_text: str | None) -> dict[str, str] | None:
    if not style_text:
        return None

    style: dict[str, str] = {}
    for declaration in style_text.split(";"):
        name, separator, value = declaration.partition(":")
        if not separator:
            continue

        property_name = name.strip()
        property_value = value.strip()
        if not property_name or not property_value:
            continue

        normalized_value = _normalize_inline_style_value(property_value)
        if normalized_value is None:
            continue

        js_property_name = _css_property_to_js_property(property_name)
        if not _is_supported_inline_declaration(js_property_name, normalized_value):
            continue

        style[js_property_name] = normalized_value

    return style or None


def _sanitize_stylesheet(css: str) -> str:
    return _drop_at_rules(css, _DROP_STYLESHEET_AT_RULES)


def _drop_at_rules(css: str, at_rules: set[str]) -> str:
    out: list[str] = []
    index = 0
    length = len(css)

    while index < length:
        if css[index] != "@":
            out.append(css[index])
            index += 1
            continue

        name_start = index + 1
        name_end = name_start
        while name_end < length and (
            css[name_end].isalnum() or css[name_end] in {"-", "_"}
        ):
            name_end += 1

        at_rule_name = css[name_start:name_end].lower()
        if at_rule_name not in at_rules:
            out.append(css[index])
            index += 1
            continue

        index = _at_rule_end(css, name_end)

    return "".join(out)


def _at_rule_end(css: str, index: int) -> int:
    length = len(css)
    while index < length and css[index].isspace():
        index += 1

    while index < length and css[index] not in {";", "{"}:
        index += 1

    if index >= length:
        return length

    if css[index] == ";":
        return index + 1

    return _block_end(css, index)


def _block_end(css: str, index: int) -> int:
    depth = 0
    quote: str | None = None
    escape = False

    while index < len(css):
        char = css[index]

        if quote is not None:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                quote = None
            index += 1
            continue

        if char in {"'", '"'}:
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index + 1

        index += 1

    return index


def _normalize_inline_style_value(value: str) -> str | None:
    value = value.strip()
    if "\\9" in value:
        return None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1].strip()
    return value or None


def _is_supported_inline_declaration(property_name: str, value: str) -> bool:
    if property_name.startswith("--"):
        return False
    if property_name == "display":
        return value in _SUPPORTED_DISPLAY_VALUES
    return True


def _is_hidden_element(attrs: dict[str, str]) -> bool:
    if "hidden" in attrs:
        return True

    style = _parse_inline_style(attrs.get("style"))
    if not style:
        return False

    return style.get("display") == "none" or style.get("visibility") == "hidden"


def _css_property_to_js_property(property_name: str) -> str:
    if property_name.startswith("--"):
        return property_name

    parts = property_name.split("-")
    return parts[0] + "".join(part[:1].upper() + part[1:] for part in parts[1:] if part)


def _set_dimension(node: dict[str, object], attrs: dict[str, str], key: str) -> None:
    value = attrs.pop(key, None)
    if value is None:
        return

    parsed = _parse_dimension(value)
    if parsed is not None:
        node[key] = parsed


def _parse_dimension(value: str) -> float | None:
    try:
        parsed = float(value)
    except ValueError:
        return None

    return parsed if isfinite(parsed) else None
