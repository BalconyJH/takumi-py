from __future__ import annotations

from dataclasses import dataclass

from takumi_py import _core
from takumi_py.options import HtmlOptions
from takumi_py.types import CompiledNode, CompiledStyleSheet


@dataclass(frozen=True, slots=True)
class ParsedHtml:
    """A compiled HTML node and any stylesheets produced with it.

    Takumi removes ``<style>`` elements from the node tree and returns their CSS
    separately in document order. The CSS is compiled with the error-tolerant
    parser used for browser-authored stylesheets.

    Attributes:
        node: The compiled root node.
        stylesheets: Compiled stylesheets returned by the parser.
    """

    node: CompiledNode
    stylesheets: tuple[CompiledStyleSheet, ...] = ()


def parse_html(markup: str, *, options: HtmlOptions | None = None) -> ParsedHtml:
    """Parse HTML without creating a public renderer.

    Args:
        markup: HTML fragment or document source.
        options: Parser presets, Tailwind attribute name, and maximum element
            depth. Defaults to ``HtmlOptions()``.

    Returns:
        A compiled node and the lossily compiled ``<style>`` CSS in document
        order.

    Raises:
        HtmlParseError: If the HTML cannot be parsed or exceeds configured
            limits.
    """
    resolved_options = options or HtmlOptions()
    node, css = _core.parse_html(
        markup,
        presets=resolved_options.presets,
        tailwind_property=resolved_options.tailwind_property,
        max_depth=resolved_options.max_depth,
    )
    return ParsedHtml(
        node=node,
        stylesheets=tuple(
            _core.compile_stylesheet(stylesheet, strict=False) for stylesheet in css
        ),
    )
