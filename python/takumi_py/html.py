from __future__ import annotations

from dataclasses import dataclass

from takumi_py import _core
from takumi_py.options import HtmlOptions
from takumi_py.types import CompiledNode, CompiledStyleSheet


@dataclass(frozen=True, slots=True)
class ParsedHtml:
    node: CompiledNode
    stylesheets: tuple[CompiledStyleSheet, ...] = ()


_PARSER = _core.NativeRenderer(load_default_fonts=False)


def parse_html(markup: str, *, options: HtmlOptions | None = None) -> ParsedHtml:
    resolved_options = options or HtmlOptions()
    return ParsedHtml(
        node=_PARSER.compile_html(
            markup,
            presets=resolved_options.presets,
            tailwind_property=resolved_options.tailwind_property,
            max_depth=resolved_options.max_depth,
        )
    )
