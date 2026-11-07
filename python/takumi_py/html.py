from __future__ import annotations

from dataclasses import dataclass

from takumi_py import _core
from takumi_py.options import HtmlOptions
from takumi_py.types import CompiledNode, CompiledStyleSheet


@dataclass(frozen=True, slots=True)
class ParsedHtml:
    """A compiled HTML node and any stylesheets produced with it.

    The current parser keeps ``<style>`` elements out of the node tree and
    returns an empty ``stylesheets`` tuple. Compile document-level CSS
    explicitly with ``Renderer.compile_stylesheet`` or
    ``Renderer.compile_stylesheet_lossy``.

    Attributes:
        node: The compiled root node.
        stylesheets: Compiled stylesheets returned by the parser.
    """

    node: CompiledNode
    stylesheets: tuple[CompiledStyleSheet, ...] = ()


_PARSER = _core.NativeRenderer(load_default_fonts=False)


def parse_html(markup: str, *, options: HtmlOptions | None = None) -> ParsedHtml:
    """Parse HTML without creating a public renderer.

    Args:
        markup: HTML fragment or document source.
        options: Parser presets, Tailwind attribute name, and maximum element
            depth. Defaults to ``HtmlOptions()``.

    Returns:
        A compiled node and its (currently empty) stylesheet bundle.

    Raises:
        HtmlParseError: If the HTML cannot be parsed or exceeds configured
            limits.
    """
    resolved_options = options or HtmlOptions()
    return ParsedHtml(
        node=_PARSER.compile_html(
            markup,
            presets=resolved_options.presets,
            tailwind_property=resolved_options.tailwind_property,
            max_depth=resolved_options.max_depth,
        )
    )
