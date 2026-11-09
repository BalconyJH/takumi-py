from pathlib import Path
from typing import Any
from unittest.mock import patch

from jinja2 import DictLoader, Environment
import pytest

from takumi_py import AnimationScene, Renderer, RenderOptions, TemplateRenderer

_OMIT = object()

_FADE_X = {
    "fade": {
        "from": {"opacity": 0},
        "to": {"opacity": 1},
    }
}
_FADE_Y = {
    "fade": {
        "from": {"opacity": 1},
        "to": {"opacity": 0},
    }
}
_GROW_X = {
    "grow": {
        "from": {"width": "10px"},
        "to": {"width": "20px"},
    }
}
_GROW_Y = {
    "grow": {
        "from": {"width": "30px"},
        "to": {"width": "40px"},
    }
}

_RASTER_NODE: dict[str, object] = {
    "type": "container",
    "style": {
        "width": "10px",
        "height": "10px",
        "backgroundColor": "black",
        "animation": "fade 1000ms linear both",
    },
}
_RASTER_HTML = """
<div style="
  width: 10px;
  height: 10px;
  background-color: black;
  animation: fade 1000ms linear both;
"></div>
"""
_MEASURE_NODE: dict[str, object] = {
    "type": "container",
    "style": {
        "width": "50px",
        "height": "10px",
        "animation": "grow 1000ms linear both",
    },
}
_MEASURE_HTML = """
<div style="
  width: 50px;
  height: 10px;
  animation: grow 1000ms linear both;
"></div>
"""


@pytest.fixture
def template_dir(tmp_path: Path) -> Path:
    (tmp_path / "card.html.jinja").write_text(_RASTER_HTML, encoding="utf-8")
    return tmp_path


def _render_raster(
    route: str,
    renderer: Renderer,
    template_dir: Path,
    *,
    keyframes: object = _OMIT,
    options: RenderOptions,
) -> bytes:
    kwargs: dict[str, Any] = {
        "width": 1,
        "height": 1,
        "format": "raw",
        "time_ms": 0,
        "options": options,
    }
    if keyframes is not _OMIT:
        kwargs["keyframes"] = keyframes
    if route == "node":
        return renderer.render_node(_RASTER_NODE, **kwargs)
    if route == "html":
        return renderer.render_html(_RASTER_HTML, **kwargs)
    if route == "template":
        return renderer.render_template(
            "card.html.jinja",
            {},
            template_dir=template_dir,
            **kwargs,
        )
    if route == "template_renderer":
        environment = Environment(
            loader=DictLoader({"card.html.jinja": _RASTER_HTML}),
            autoescape=True,
        )
        return TemplateRenderer(
            environment=environment,
            renderer=renderer,
        ).render("card.html.jinja", {}, **kwargs)
    raise AssertionError(f"unknown route: {route}")


@pytest.mark.parametrize("route", ["node", "html", "template", "template_renderer"])
def test_legacy_raster_keyframes_inherit_clear_and_override_options(
    route: str,
    template_dir: Path,
) -> None:
    renderer = Renderer()

    with patch.object(
        renderer,
        "compile_keyframes",
        wraps=renderer.compile_keyframes,
    ) as compile_keyframes:
        inherited = _render_raster(
            route,
            renderer,
            template_dir,
            options=RenderOptions(keyframes=_FADE_X),
        )
    assert inherited[3] == 0
    assert compile_keyframes.call_count == 1

    with patch.object(
        renderer,
        "compile_keyframes",
        wraps=renderer.compile_keyframes,
    ) as compile_keyframes:
        cleared = _render_raster(
            route,
            renderer,
            template_dir,
            keyframes=None,
            options=RenderOptions(keyframes=_FADE_X),
        )
    assert cleared[3] == 255
    assert compile_keyframes.call_count == 0

    with patch.object(
        renderer,
        "compile_keyframes",
        wraps=renderer.compile_keyframes,
    ) as compile_keyframes:
        overridden = _render_raster(
            route,
            renderer,
            template_dir,
            keyframes=_FADE_X,
            options=RenderOptions(keyframes=_FADE_Y),
        )
    assert overridden[3] == 0
    assert compile_keyframes.call_count == 1


def _render_svg(
    route: str,
    renderer: Renderer,
    template_dir: Path,
    *,
    keyframes: object = _OMIT,
    options: RenderOptions,
) -> str:
    kwargs: dict[str, Any] = {
        "width": 10,
        "height": 10,
        "time_ms": 0,
        "options": options,
    }
    if keyframes is not _OMIT:
        kwargs["keyframes"] = keyframes
    if route == "node":
        return renderer.render_svg_node(_RASTER_NODE, **kwargs)
    if route == "html":
        return renderer.render_svg_html(_RASTER_HTML, **kwargs)
    if route == "template":
        return renderer.render_svg_template(
            "card.html.jinja",
            {},
            template_dir=template_dir,
            **kwargs,
        )
    raise AssertionError(f"unknown route: {route}")


@pytest.mark.parametrize("route", ["node", "html", "template"])
def test_legacy_svg_keyframes_inherit_clear_and_override_options(
    route: str,
    template_dir: Path,
) -> None:
    renderer = Renderer()
    explicit_x = _render_svg(
        route,
        renderer,
        template_dir,
        keyframes=_FADE_X,
        options=RenderOptions(),
    )
    explicit_y = _render_svg(
        route,
        renderer,
        template_dir,
        keyframes=_FADE_Y,
        options=RenderOptions(),
    )
    no_keyframes = _render_svg(
        route,
        renderer,
        template_dir,
        keyframes=None,
        options=RenderOptions(),
    )
    assert explicit_x != explicit_y

    with patch.object(
        renderer,
        "compile_keyframes",
        wraps=renderer.compile_keyframes,
    ) as compile_keyframes:
        inherited = _render_svg(
            route,
            renderer,
            template_dir,
            options=RenderOptions(keyframes=_FADE_X),
        )
    assert inherited == explicit_x
    assert compile_keyframes.call_count == 1

    cleared = _render_svg(
        route,
        renderer,
        template_dir,
        keyframes=None,
        options=RenderOptions(keyframes=_FADE_X),
    )
    assert cleared == no_keyframes

    overridden = _render_svg(
        route,
        renderer,
        template_dir,
        keyframes=_FADE_X,
        options=RenderOptions(keyframes=_FADE_Y),
    )
    assert overridden == explicit_x


def _measure(
    route: str,
    renderer: Renderer,
    *,
    keyframes: object = _OMIT,
    options: RenderOptions,
) -> float:
    kwargs: dict[str, Any] = {
        "width": None,
        "height": None,
        "time_ms": 0,
        "options": options,
    }
    if keyframes is not _OMIT:
        kwargs["keyframes"] = keyframes
    if route == "node":
        return renderer.measure_node(_MEASURE_NODE, **kwargs).width
    if route == "html":
        return renderer.measure_html(_MEASURE_HTML, **kwargs).width
    if route == "compiled":
        compiled = renderer.compile_node(_MEASURE_NODE)
        return renderer.measure_compiled(compiled, **kwargs).width
    raise AssertionError(f"unknown route: {route}")


@pytest.mark.parametrize("route", ["node", "html", "compiled"])
def test_measure_keyframes_inherit_clear_and_override_options(route: str) -> None:
    renderer = Renderer()

    with patch.object(
        renderer,
        "compile_keyframes",
        wraps=renderer.compile_keyframes,
    ) as compile_keyframes:
        inherited = _measure(
            route,
            renderer,
            options=RenderOptions(keyframes=_GROW_X),
        )
    assert inherited == 10
    assert compile_keyframes.call_count == 1

    cleared = _measure(
        route,
        renderer,
        keyframes=None,
        options=RenderOptions(keyframes=_GROW_X),
    )
    assert cleared == 50

    overridden = _measure(
        route,
        renderer,
        keyframes=_GROW_X,
        options=RenderOptions(keyframes=_GROW_Y),
    )
    assert overridden == 10


def test_sequence_keyframes_inherit_clear_and_override_options() -> None:
    renderer = Renderer()
    scenes = [AnimationScene(node=_RASTER_NODE, duration_ms=1000)]

    with patch.object(
        renderer,
        "compile_keyframes",
        wraps=renderer.compile_keyframes,
    ) as compile_keyframes:
        inherited = renderer.render_sequence_at_time(
            scenes,
            0,
            width=1,
            height=1,
            format="raw",
            options=RenderOptions(keyframes=_FADE_X),
        )
    assert inherited[3] == 0
    assert compile_keyframes.call_count == 1

    cleared = renderer.render_sequence_at_time(
        scenes,
        0,
        keyframes=None,
        width=1,
        height=1,
        format="raw",
        options=RenderOptions(keyframes=_FADE_X),
    )
    assert cleared[3] == 255

    overridden = renderer.render_sequence_at_time(
        scenes,
        0,
        keyframes=_FADE_X,
        width=1,
        height=1,
        format="raw",
        options=RenderOptions(keyframes=_FADE_Y),
    )
    assert overridden[3] == 0


def test_animation_keyframes_inherit_clear_and_override_options() -> None:
    renderer = Renderer()
    scenes = [AnimationScene(node=_RASTER_NODE, duration_ms=1000)]
    encode_kwargs: dict[str, Any] = {
        "width": 10,
        "height": 10,
        "format": "apng",
        "fps": 1,
    }
    explicit_x = renderer.render_animation(
        scenes,
        keyframes=_FADE_X,
        **encode_kwargs,
    )
    no_keyframes = renderer.render_animation(
        scenes,
        keyframes=None,
        **encode_kwargs,
    )
    assert explicit_x != no_keyframes

    with patch.object(
        renderer,
        "compile_keyframes",
        wraps=renderer.compile_keyframes,
    ) as compile_keyframes:
        inherited = renderer.render_animation(
            scenes,
            options=RenderOptions(keyframes=_FADE_X),
            **encode_kwargs,
        )
    assert inherited == explicit_x
    assert compile_keyframes.call_count == 1

    cleared = renderer.render_animation(
        scenes,
        keyframes=None,
        options=RenderOptions(keyframes=_FADE_X),
        **encode_kwargs,
    )
    assert cleared == no_keyframes

    overridden = renderer.render_animation(
        scenes,
        keyframes=_FADE_X,
        options=RenderOptions(keyframes=_FADE_Y),
        **encode_kwargs,
    )
    assert overridden == explicit_x
