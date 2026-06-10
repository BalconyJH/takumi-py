from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from takumi_py.options import (
    UNSET,
    DitheringAlgorithm,
    ImageOutputFormat,
    ImageResourceInput,
    RenderOptions,
    UnsetType,
)


def create_environment(template_dir: str | Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(
            enabled_extensions=("html", "xml", "jinja"),
            default_for_string=False,
        ),
    )


def render_template_to_html(
    template_name: str,
    context: Mapping[str, object],
    *,
    template_dir: str | Path = ".",
) -> str:
    return (
        create_environment(template_dir).get_template(template_name).render(**context)
    )


class TemplateRenderer:
    def __init__(self, template_dir: str | Path) -> None:
        from takumi_py.renderer import Renderer

        self._renderer = Renderer()
        self._environment = create_environment(template_dir)

    def render(
        self,
        template_name: str,
        context: Mapping[str, object],
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
    ) -> bytes:
        html = self._environment.get_template(template_name).render(**context)
        return self._renderer.render_html(
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
