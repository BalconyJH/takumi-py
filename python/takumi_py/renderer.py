from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from takumi_py import _core
from takumi_py.html import parse_html
from takumi_py.options import ImageOutputFormat
from takumi_py.template import render_template_to_html
from takumi_py.types import CompiledNode, CompiledStyleSheet, Node, validate_node


@dataclass(frozen=True, slots=True)
class CompiledHtml:
    node: CompiledNode
    stylesheets: tuple[CompiledStyleSheet, ...]


class Renderer:
    def __init__(self) -> None:
        self._native = _core.NativeRenderer()

    def compile_node(
        self,
        node: Node | dict[str, object] | bytes,
        *,
        validate: bool = False,
        codec: Literal["pyobject", "msgpack"] = "pyobject",
    ) -> CompiledNode:
        if codec == "pyobject":
            if isinstance(node, bytes):
                raise TypeError("bytes input requires codec='msgpack'")

            if validate:
                node = validate_node(node)
            return self._native.compile_node_py(node)

        if codec == "msgpack":
            if not isinstance(node, bytes):
                raise TypeError("msgpack codec requires bytes input")
            return self._native.compile_node_msgpack(node)

        raise ValueError(f"unsupported node codec {codec!r}")

    def compile_stylesheet(self, css: str) -> CompiledStyleSheet:
        return self._native.compile_stylesheet(css)

    def compile_stylesheet_lossy(self, css: str) -> CompiledStyleSheet:
        return self._native.compile_stylesheet_lossy(css)

    def render_compiled(
        self,
        node: CompiledNode,
        *,
        stylesheets: Sequence[CompiledStyleSheet] | None = None,
        width: int = 1200,
        height: int = 630,
        format: ImageOutputFormat = "png",
        quality: int | None = None,
    ) -> bytes:
        return self._native.render_compiled(
            node,
            stylesheets=stylesheets,
            width=width,
            height=height,
            format=format,
            quality=quality,
        )

    def render_node(
        self,
        node: Node | dict[str, object],
        *,
        stylesheets: Sequence[str] | None = None,
        width: int = 1200,
        height: int = 630,
        format: ImageOutputFormat = "png",
        quality: int | None = None,
        validate: bool = False,
    ) -> bytes:
        compiled = self.compile_node(node, validate=validate)
        compiled_stylesheets = tuple(
            self.compile_stylesheet(stylesheet) for stylesheet in stylesheets or ()
        )
        return self.render_compiled(
            compiled,
            stylesheets=compiled_stylesheets,
            width=width,
            height=height,
            format=format,
            quality=quality,
        )

    def compile_html(self, html: str, *, validate: bool = False) -> CompiledHtml:
        parsed = parse_html(html)
        return CompiledHtml(
            node=self.compile_node(parsed.node, validate=validate),
            stylesheets=tuple(
                self.compile_stylesheet_lossy(stylesheet)
                for stylesheet in parsed.stylesheets
            ),
        )

    def render_html(
        self,
        html: str,
        *,
        width: int = 1200,
        height: int = 630,
        format: ImageOutputFormat = "png",
        quality: int | None = None,
        validate: bool = False,
    ) -> bytes:
        compiled = self.compile_html(html, validate=validate)
        return self.render_compiled(
            compiled.node,
            stylesheets=compiled.stylesheets,
            width=width,
            height=height,
            format=format,
            quality=quality,
        )

    def render_template(
        self,
        template_name: str,
        context: dict[str, object],
        *,
        template_dir: str | Path = ".",
        width: int = 1200,
        height: int = 630,
        format: ImageOutputFormat = "png",
        quality: int | None = None,
    ) -> bytes:
        html = render_template_to_html(
            template_name, context, template_dir=template_dir
        )
        return self.render_html(
            html,
            width=width,
            height=height,
            format=format,
            quality=quality,
        )
