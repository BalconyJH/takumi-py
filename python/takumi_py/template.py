from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from takumi_py.options import ImageOutputFormat


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
    context: dict[str, object],
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
        context: dict[str, object],
        *,
        width: int = 1200,
        height: int = 630,
        format: ImageOutputFormat = "png",
        quality: int | None = None,
    ) -> bytes:
        html = self._environment.get_template(template_name).render(**context)
        return self._renderer.render_html(
            html,
            width=width,
            height=height,
            format=format,
            quality=quality,
        )
