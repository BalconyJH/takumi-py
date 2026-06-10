from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, TypeGuard, cast

from takumi_py import _core
from takumi_py.html import parse_html
from takumi_py.options import (
    UNSET,
    AnimationEncodeOptions,
    AnimationOutputFormat,
    DitheringAlgorithm,
    FontResource,
    FontResourceInput,
    ImageOutputFormat,
    ImageResourceInput,
    RenderOptions,
    UnsetType,
    normalize_font_resources,
    normalize_image_resource,
    normalize_image_resources,
)
from takumi_py.template import render_template_to_html
from takumi_py.types import (
    AnimationScene,
    CompiledNode,
    CompiledStyleSheet,
    MeasuredNode,
    NodeInput,
    RawAnimationFrame,
    measured_node_from_mapping,
    validate_node,
)


@dataclass(frozen=True, slots=True)
class CompiledHtml:
    node: CompiledNode
    stylesheets: tuple[CompiledStyleSheet, ...]


class Renderer:
    def __init__(
        self,
        *,
        load_default_fonts: bool = True,
        fonts: Sequence[FontResourceInput] | None = None,
        persistent_images: Sequence[ImageResourceInput] | None = None,
    ) -> None:
        self._native = _core.NativeRenderer(
            load_default_fonts=load_default_fonts,
            fonts=normalize_font_resources(fonts),
            persistent_images=normalize_image_resources(persistent_images),
        )

    def compile_node(
        self,
        node: NodeInput,
        *,
        validate: bool = False,
    ) -> CompiledNode:
        if validate:
            node = validate_node(node)
        return self._native.compile_node_py(node)

    def compile_stylesheet(self, css: str) -> CompiledStyleSheet:
        return self._native.compile_stylesheet(css)

    def compile_stylesheet_lossy(self, css: str) -> CompiledStyleSheet:
        return self._native.compile_stylesheet_lossy(css)

    def load_font(self, font: FontResourceInput) -> None:
        data = font.data if isinstance(font, FontResource) else font
        self._native.load_font(data)

    def load_fonts(self, fonts: Sequence[FontResourceInput]) -> None:
        self._native.load_fonts(normalize_font_resources(fonts) or [])

    def put_persistent_image(
        self,
        resource: ImageResourceInput | str,
        data: bytes | None = None,
    ) -> None:
        if isinstance(resource, str):
            if data is None:
                raise TypeError("data is required when resource is a src string")
            src = resource
            payload = data
        else:
            src, payload = normalize_image_resource(resource)

        self._native.put_persistent_image(src, payload)

    def clear_image_store(self) -> None:
        self._native.clear_image_store()

    def render_compiled(
        self,
        node: CompiledNode,
        *,
        stylesheets: Sequence[CompiledStyleSheet] | None = None,
        options: RenderOptions | None = None,
        width: int | None | UnsetType = UNSET,
        height: int | None | UnsetType = UNSET,
        format: ImageOutputFormat | UnsetType = UNSET,
        quality: int | None | UnsetType = UNSET,
        font_size: float | UnsetType = UNSET,
        device_pixel_ratio: float | UnsetType = UNSET,
        draw_debug_border: bool | UnsetType = UNSET,
        time_ms: int | UnsetType = UNSET,
        dithering: DitheringAlgorithm | UnsetType = UNSET,
        fetched_resources: Sequence[ImageResourceInput] | None | UnsetType = UNSET,
    ) -> bytes:
        render_options = resolve_render_options(
            options,
            width=width,
            height=height,
            format=format,
            quality=quality,
            font_size=font_size,
            device_pixel_ratio=device_pixel_ratio,
            draw_debug_border=draw_debug_border,
            time_ms=time_ms,
            dithering=dithering,
            fetched_resources=fetched_resources,
        )
        return self._native.render_compiled(
            node,
            stylesheets=stylesheets,
            width=render_options.width,
            height=render_options.height,
            font_size=render_options.font_size,
            device_pixel_ratio=render_options.device_pixel_ratio,
            draw_debug_border=render_options.draw_debug_border,
            time_ms=render_options.time_ms,
            dithering=render_options.dithering,
            fetched_resources=normalize_image_resources(
                render_options.fetched_resources
            ),
            format=render_options.format,
            quality=render_options.quality,
        )

    def measure_compiled(
        self,
        node: CompiledNode,
        *,
        stylesheets: Sequence[CompiledStyleSheet] | None = None,
        options: RenderOptions | None = None,
        width: int | None | UnsetType = UNSET,
        height: int | None | UnsetType = UNSET,
        font_size: float | UnsetType = UNSET,
        device_pixel_ratio: float | UnsetType = UNSET,
        draw_debug_border: bool | UnsetType = UNSET,
        time_ms: int | UnsetType = UNSET,
        dithering: DitheringAlgorithm | UnsetType = UNSET,
        fetched_resources: Sequence[ImageResourceInput] | None | UnsetType = UNSET,
    ) -> MeasuredNode:
        render_options = resolve_render_options(
            options,
            width=width,
            height=height,
            font_size=font_size,
            device_pixel_ratio=device_pixel_ratio,
            draw_debug_border=draw_debug_border,
            time_ms=time_ms,
            dithering=dithering,
            fetched_resources=fetched_resources,
        )
        measured = self._native.measure_compiled(
            node,
            stylesheets=stylesheets,
            width=render_options.width,
            height=render_options.height,
            font_size=render_options.font_size,
            device_pixel_ratio=render_options.device_pixel_ratio,
            draw_debug_border=render_options.draw_debug_border,
            time_ms=render_options.time_ms,
            dithering=render_options.dithering,
            fetched_resources=normalize_image_resources(
                render_options.fetched_resources
            ),
        )
        return measured_node_from_mapping(measured)

    def render_node(
        self,
        node: NodeInput,
        *,
        stylesheets: Sequence[str] | None = None,
        options: RenderOptions | None = None,
        width: int | None | UnsetType = UNSET,
        height: int | None | UnsetType = UNSET,
        format: ImageOutputFormat | UnsetType = UNSET,
        quality: int | None | UnsetType = UNSET,
        font_size: float | UnsetType = UNSET,
        device_pixel_ratio: float | UnsetType = UNSET,
        draw_debug_border: bool | UnsetType = UNSET,
        time_ms: int | UnsetType = UNSET,
        dithering: DitheringAlgorithm | UnsetType = UNSET,
        fetched_resources: Sequence[ImageResourceInput] | None | UnsetType = UNSET,
        validate: bool = False,
    ) -> bytes:
        compiled = self.compile_node(node, validate=validate)
        compiled_stylesheets = self.compile_stylesheets(stylesheets)
        return self.render_compiled(
            compiled,
            stylesheets=compiled_stylesheets,
            options=options,
            width=width,
            height=height,
            format=format,
            quality=quality,
            font_size=font_size,
            device_pixel_ratio=device_pixel_ratio,
            draw_debug_border=draw_debug_border,
            time_ms=time_ms,
            dithering=dithering,
            fetched_resources=fetched_resources,
        )

    def measure_node(
        self,
        node: NodeInput,
        *,
        stylesheets: Sequence[str] | None = None,
        options: RenderOptions | None = None,
        width: int | None | UnsetType = UNSET,
        height: int | None | UnsetType = UNSET,
        font_size: float | UnsetType = UNSET,
        device_pixel_ratio: float | UnsetType = UNSET,
        draw_debug_border: bool | UnsetType = UNSET,
        time_ms: int | UnsetType = UNSET,
        dithering: DitheringAlgorithm | UnsetType = UNSET,
        fetched_resources: Sequence[ImageResourceInput] | None | UnsetType = UNSET,
        validate: bool = False,
    ) -> MeasuredNode:
        compiled = self.compile_node(node, validate=validate)
        compiled_stylesheets = self.compile_stylesheets(stylesheets)
        return self.measure_compiled(
            compiled,
            stylesheets=compiled_stylesheets,
            options=options,
            width=width,
            height=height,
            font_size=font_size,
            device_pixel_ratio=device_pixel_ratio,
            draw_debug_border=draw_debug_border,
            time_ms=time_ms,
            dithering=dithering,
            fetched_resources=fetched_resources,
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
        options: RenderOptions | None = None,
        width: int | None | UnsetType = UNSET,
        height: int | None | UnsetType = UNSET,
        format: ImageOutputFormat | UnsetType = UNSET,
        quality: int | None | UnsetType = UNSET,
        font_size: float | UnsetType = UNSET,
        device_pixel_ratio: float | UnsetType = UNSET,
        draw_debug_border: bool | UnsetType = UNSET,
        time_ms: int | UnsetType = UNSET,
        dithering: DitheringAlgorithm | UnsetType = UNSET,
        fetched_resources: Sequence[ImageResourceInput] | None | UnsetType = UNSET,
        validate: bool = False,
    ) -> bytes:
        compiled = self.compile_html(html, validate=validate)
        return self.render_compiled(
            compiled.node,
            stylesheets=compiled.stylesheets,
            options=options,
            width=width,
            height=height,
            format=format,
            quality=quality,
            font_size=font_size,
            device_pixel_ratio=device_pixel_ratio,
            draw_debug_border=draw_debug_border,
            time_ms=time_ms,
            dithering=dithering,
            fetched_resources=fetched_resources,
        )

    def measure_html(
        self,
        html: str,
        *,
        options: RenderOptions | None = None,
        width: int | None | UnsetType = UNSET,
        height: int | None | UnsetType = UNSET,
        font_size: float | UnsetType = UNSET,
        device_pixel_ratio: float | UnsetType = UNSET,
        draw_debug_border: bool | UnsetType = UNSET,
        time_ms: int | UnsetType = UNSET,
        dithering: DitheringAlgorithm | UnsetType = UNSET,
        fetched_resources: Sequence[ImageResourceInput] | None | UnsetType = UNSET,
        validate: bool = False,
    ) -> MeasuredNode:
        compiled = self.compile_html(html, validate=validate)
        return self.measure_compiled(
            compiled.node,
            stylesheets=compiled.stylesheets,
            options=options,
            width=width,
            height=height,
            font_size=font_size,
            device_pixel_ratio=device_pixel_ratio,
            draw_debug_border=draw_debug_border,
            time_ms=time_ms,
            dithering=dithering,
            fetched_resources=fetched_resources,
        )

    def render_template(
        self,
        template_name: str,
        context: Mapping[str, object],
        *,
        template_dir: str | Path = ".",
        options: RenderOptions | None = None,
        width: int | None | UnsetType = UNSET,
        height: int | None | UnsetType = UNSET,
        format: ImageOutputFormat | UnsetType = UNSET,
        quality: int | None | UnsetType = UNSET,
        font_size: float | UnsetType = UNSET,
        device_pixel_ratio: float | UnsetType = UNSET,
        draw_debug_border: bool | UnsetType = UNSET,
        time_ms: int | UnsetType = UNSET,
        dithering: DitheringAlgorithm | UnsetType = UNSET,
        fetched_resources: Sequence[ImageResourceInput] | None | UnsetType = UNSET,
    ) -> bytes:
        html = render_template_to_html(
            template_name, context, template_dir=template_dir
        )
        return self.render_html(
            html,
            options=options,
            width=width,
            height=height,
            format=format,
            quality=quality,
            font_size=font_size,
            device_pixel_ratio=device_pixel_ratio,
            draw_debug_border=draw_debug_border,
            time_ms=time_ms,
            dithering=dithering,
            fetched_resources=fetched_resources,
        )

    def render_sequence_at_time(
        self,
        scenes: Sequence[AnimationScene],
        time_ms: int,
        *,
        stylesheets: Sequence[str] | None = None,
        options: RenderOptions | None = None,
        width: int | None | UnsetType = UNSET,
        height: int | None | UnsetType = UNSET,
        format: ImageOutputFormat | UnsetType = UNSET,
        quality: int | None | UnsetType = UNSET,
        font_size: float | UnsetType = UNSET,
        device_pixel_ratio: float | UnsetType = UNSET,
        draw_debug_border: bool | UnsetType = UNSET,
        dithering: DitheringAlgorithm | UnsetType = UNSET,
        fetched_resources: Sequence[ImageResourceInput] | None | UnsetType = UNSET,
        validate: bool = False,
    ) -> bytes:
        render_options = resolve_render_options(
            options,
            width=width,
            height=height,
            format=format,
            quality=quality,
            font_size=font_size,
            device_pixel_ratio=device_pixel_ratio,
            draw_debug_border=draw_debug_border,
            dithering=dithering,
            fetched_resources=fetched_resources,
        )
        compiled_scenes = self.compile_animation_scenes(scenes, validate=validate)
        return self._native.render_sequence_at_time_compiled(
            compiled_scenes,
            time_ms,
            stylesheets=self.compile_stylesheets(stylesheets),
            width=render_options.width,
            height=render_options.height,
            font_size=render_options.font_size,
            device_pixel_ratio=render_options.device_pixel_ratio,
            draw_debug_border=render_options.draw_debug_border,
            dithering=render_options.dithering,
            fetched_resources=normalize_image_resources(
                render_options.fetched_resources
            ),
            format=render_options.format,
            quality=render_options.quality,
        )

    def render_animation(
        self,
        scenes: Sequence[AnimationScene],
        *,
        stylesheets: Sequence[str] | None = None,
        options: RenderOptions | None = None,
        encode_options: AnimationEncodeOptions | None = None,
        width: int | None | UnsetType = UNSET,
        height: int | None | UnsetType = UNSET,
        font_size: float | UnsetType = UNSET,
        device_pixel_ratio: float | UnsetType = UNSET,
        draw_debug_border: bool | UnsetType = UNSET,
        dithering: DitheringAlgorithm | UnsetType = UNSET,
        fetched_resources: Sequence[ImageResourceInput] | None | UnsetType = UNSET,
        fps: int = 30,
        format: AnimationOutputFormat | UnsetType = UNSET,
        quality: int | None | UnsetType = UNSET,
        loop_count: int | None | UnsetType = UNSET,
        webp_blend: bool | UnsetType = UNSET,
        webp_dispose: bool | UnsetType = UNSET,
        webp_speed: int | None | UnsetType = UNSET,
        validate: bool = False,
    ) -> bytes:
        render_options = resolve_render_options(
            options,
            width=width,
            height=height,
            font_size=font_size,
            device_pixel_ratio=device_pixel_ratio,
            draw_debug_border=draw_debug_border,
            dithering=dithering,
            fetched_resources=fetched_resources,
        )
        resolved_encode_options = resolve_animation_encode_options(
            encode_options,
            format=format,
            quality=quality,
            loop_count=loop_count,
            webp_blend=webp_blend,
            webp_dispose=webp_dispose,
            webp_speed=webp_speed,
        )
        compiled_scenes = self.compile_animation_scenes(scenes, validate=validate)
        return self._native.render_animation_compiled(
            compiled_scenes,
            stylesheets=self.compile_stylesheets(stylesheets),
            width=render_options.width,
            height=render_options.height,
            font_size=render_options.font_size,
            device_pixel_ratio=render_options.device_pixel_ratio,
            draw_debug_border=render_options.draw_debug_border,
            dithering=render_options.dithering,
            fetched_resources=normalize_image_resources(
                render_options.fetched_resources
            ),
            fps=fps,
            format=resolved_encode_options.format,
            quality=resolved_encode_options.quality,
            loop_count=resolved_encode_options.loop_count,
            webp_blend=resolved_encode_options.webp_blend,
            webp_dispose=resolved_encode_options.webp_dispose,
            webp_speed=resolved_encode_options.webp_speed,
        )

    def encode_frames(
        self,
        frames: Sequence[RawAnimationFrame],
        *,
        encode_options: AnimationEncodeOptions | None = None,
        format: AnimationOutputFormat | UnsetType = UNSET,
        quality: int | None | UnsetType = UNSET,
        loop_count: int | None | UnsetType = UNSET,
        webp_blend: bool | UnsetType = UNSET,
        webp_dispose: bool | UnsetType = UNSET,
        webp_speed: int | None | UnsetType = UNSET,
    ) -> bytes:
        resolved_encode_options = resolve_animation_encode_options(
            encode_options,
            format=format,
            quality=quality,
            loop_count=loop_count,
            webp_blend=webp_blend,
            webp_dispose=webp_dispose,
            webp_speed=webp_speed,
        )
        return self._native.encode_frames(
            [
                (frame.data, frame.width, frame.height, frame.duration_ms)
                for frame in frames
            ],
            format=resolved_encode_options.format,
            quality=resolved_encode_options.quality,
            loop_count=resolved_encode_options.loop_count,
            webp_blend=resolved_encode_options.webp_blend,
            webp_dispose=resolved_encode_options.webp_dispose,
            webp_speed=resolved_encode_options.webp_speed,
        )

    def compile_stylesheets(
        self, stylesheets: Sequence[str] | None
    ) -> tuple[CompiledStyleSheet, ...]:
        return tuple(
            self.compile_stylesheet(stylesheet) for stylesheet in stylesheets or ()
        )

    def compile_animation_scenes(
        self, scenes: Sequence[AnimationScene], *, validate: bool
    ) -> list[tuple[CompiledNode, int]]:
        return [
            (
                self.ensure_compiled_node(scene.node, validate=validate),
                scene.duration_ms,
            )
            for scene in scenes
        ]

    def ensure_compiled_node(
        self,
        node: NodeInput | CompiledNode,
        *,
        validate: bool,
    ) -> CompiledNode:
        if is_compiled_node(node):
            return node
        return self.compile_node(cast(NodeInput, node), validate=validate)


def resolve_render_options(
    options: RenderOptions | None = None,
    *,
    width: int | None | UnsetType = UNSET,
    height: int | None | UnsetType = UNSET,
    format: ImageOutputFormat | UnsetType = UNSET,
    quality: int | None | UnsetType = UNSET,
    font_size: float | UnsetType = UNSET,
    device_pixel_ratio: float | UnsetType = UNSET,
    draw_debug_border: bool | UnsetType = UNSET,
    time_ms: int | UnsetType = UNSET,
    dithering: DitheringAlgorithm | UnsetType = UNSET,
    fetched_resources: Sequence[ImageResourceInput] | None | UnsetType = UNSET,
) -> RenderOptions:
    resolved = RenderOptions() if options is None else options
    updates: dict[str, Any] = {}
    if width is not UNSET:
        updates["width"] = width
    if height is not UNSET:
        updates["height"] = height
    if format is not UNSET:
        updates["format"] = format
    if quality is not UNSET:
        updates["quality"] = quality
    if font_size is not UNSET:
        updates["font_size"] = font_size
    if device_pixel_ratio is not UNSET:
        updates["device_pixel_ratio"] = device_pixel_ratio
    if draw_debug_border is not UNSET:
        updates["draw_debug_border"] = draw_debug_border
    if time_ms is not UNSET:
        updates["time_ms"] = time_ms
    if dithering is not UNSET:
        updates["dithering"] = dithering
    if fetched_resources is not UNSET:
        updates["fetched_resources"] = fetched_resources
    if not updates:
        return resolved
    return replace(resolved, **updates)


def resolve_animation_encode_options(
    options: AnimationEncodeOptions | None = None,
    *,
    format: AnimationOutputFormat | UnsetType = UNSET,
    quality: int | None | UnsetType = UNSET,
    loop_count: int | None | UnsetType = UNSET,
    webp_blend: bool | UnsetType = UNSET,
    webp_dispose: bool | UnsetType = UNSET,
    webp_speed: int | None | UnsetType = UNSET,
) -> AnimationEncodeOptions:
    resolved = AnimationEncodeOptions() if options is None else options
    updates: dict[str, Any] = {}
    if format is not UNSET:
        updates["format"] = format
    if quality is not UNSET:
        updates["quality"] = quality
    if loop_count is not UNSET:
        updates["loop_count"] = loop_count
    if webp_blend is not UNSET:
        updates["webp_blend"] = webp_blend
    if webp_dispose is not UNSET:
        updates["webp_dispose"] = webp_dispose
    if webp_speed is not UNSET:
        updates["webp_speed"] = webp_speed
    if not updates:
        return resolved
    return replace(resolved, **updates)


def is_compiled_node(node: object) -> TypeGuard[CompiledNode]:
    return isinstance(node, _core.CompiledNode)
