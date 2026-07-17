from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, TypeAlias

from jinja2 import Environment, FileSystemLoader, select_autoescape

from takumi_py.options import (
    UNSET,
    DitheringAlgorithm,
    HtmlOptions,
    ImageOutputFormat,
    ImageResourceInput,
    KeyframesInput,
    RenderOptions,
    UnsetType,
)

Filter: TypeAlias = Callable[..., Any]


def create_environment(
    template_dir: str | Path,
    *,
    filters: Mapping[str, Filter] | None = None,
) -> Environment:
    environment = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(
            enabled_extensions=("html", "xml", "jinja"),
            default_for_string=False,
        ),
    )

    if filters:
        environment.filters.update(filters)

    return environment


def render_template_to_html(
    template_name: str,
    context: Mapping[str, object],
    *,
    template_dir: str | Path = ".",
    filters: Mapping[str, Filter] | None = None,
) -> str:
    return (
        create_environment(template_dir, filters=filters)
        .get_template(template_name)
        .render(**context)
    )


class TemplateRenderer:
    def __init__(
        self, template_dir: str | Path, *, filters: Mapping[str, Filter] | None = None
    ) -> None:
        from takumi_py.renderer import Renderer

        self._renderer = Renderer()
        self._environment = create_environment(template_dir, filters=filters)

    def render(
        self,
        template_name: str,
        context: Mapping[str, object],
        *,
        stylesheets: Sequence[str] | None = None,
        keyframes: KeyframesInput | None = None,
        html_options: HtmlOptions | None = None,
        options: RenderOptions | None = None,
        width: int | None | UnsetType = UNSET,
        height: int | None | UnsetType = UNSET,
        format: ImageOutputFormat | UnsetType = UNSET,
        quality: int | None | UnsetType = UNSET,
        lossless: bool | None | UnsetType = UNSET,
        font_size: float | UnsetType = UNSET,
        device_pixel_ratio: float | UnsetType = UNSET,
        draw_debug_border: bool | UnsetType = UNSET,
        time_ms: int | UnsetType = UNSET,
        dithering: DitheringAlgorithm | UnsetType = UNSET,
        images: Sequence[ImageResourceInput] | None | UnsetType = UNSET,
        font_families: Sequence[str] | None | UnsetType = UNSET,
        lang: str | None | UnsetType = UNSET,
        fetched_resources: Sequence[ImageResourceInput] | None | UnsetType = UNSET,
    ) -> bytes:
        html = self._environment.get_template(template_name).render(**context)
        return self._renderer.render_html(
            html,
            stylesheets=stylesheets,
            keyframes=keyframes,
            html_options=html_options,
            options=options,
            width=width,
            height=height,
            format=format,
            quality=quality,
            lossless=lossless,
            font_size=font_size,
            device_pixel_ratio=device_pixel_ratio,
            draw_debug_border=draw_debug_border,
            time_ms=time_ms,
            dithering=dithering,
            images=images,
            font_families=font_families,
            lang=lang,
            fetched_resources=fetched_resources,
        )
