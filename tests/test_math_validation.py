from __future__ import annotations

import subprocess
import sys
from threading import TIMEOUT_MAX

import pytest

from takumi_py import TakumiError
from takumi_py.math._validation import (
    MAX_TEX_NESTING_DEPTH,
    validate_color,
    validate_svg,
    validate_tex_nesting_depth,
)
from takumi_py.math.errors import MathError, MathValidationError
from takumi_py.math.models import MathLimits

SVG_NAMESPACE = "http://www.w3.org/2000/svg"


def svg(
    body: str = "",
    *,
    root_attributes: dict[str, str] | None = None,
) -> bytes:
    attributes = (
        {"viewBox": "0 0 10 12"} if root_attributes is None else root_attributes
    )
    rendered_attributes = " ".join(
        f'{name}="{value}"' for name, value in attributes.items()
    )
    return (
        f'<svg xmlns="{SVG_NAMESPACE}" width="10px" height="12px" '
        f"{rendered_attributes}>{body}</svg>"
    ).encode()


def validate(data: bytes, **kwargs: int) -> bytes:
    return validate_svg(
        data,
        width_px=10,
        height_px=12,
        depth_px=0,
        **kwargs,
    )


def test_math_error_integrates_with_takumi_errors() -> None:
    assert issubclass(MathError, TakumiError)


def test_math_limits_cannot_exceed_validated_svg_byte_cap() -> None:
    with pytest.raises(ValueError, match="max_svg_bytes"):
        MathLimits(max_svg_bytes=1_000_001)


def test_math_limits_cannot_exceed_the_safe_tex_nesting_depth() -> None:
    with pytest.raises(ValueError, match="max_nesting_depth"):
        MathLimits(max_nesting_depth=MAX_TEX_NESTING_DEPTH + 1)


@pytest.mark.parametrize("timeout_ms", [int(TIMEOUT_MAX) * 1000 + 1, 10**1000])
def test_math_limits_reject_timeouts_that_overflow_native_waits(
    timeout_ms: int,
) -> None:
    with pytest.raises(ValueError, match="timeout_ms"):
        MathLimits(timeout_ms=timeout_ms)


@pytest.mark.parametrize("memory_limit_bytes", [sys.maxsize + 1, 2**64, 10**1000])
def test_math_limits_reject_memory_budgets_that_wrap_native_integers(
    memory_limit_bytes: int,
) -> None:
    with pytest.raises(ValueError, match="memory_limit_bytes"):
        MathLimits(memory_limit_bytes=memory_limit_bytes)


@pytest.mark.parametrize("depth", [-200.0, 200.0])
def test_depth_may_extend_beyond_image_extent_when_baseline_is_finite(
    depth: float,
) -> None:
    validate_svg(
        svg(),
        width_px=10,
        height_px=12,
        depth_px=depth,
    )


def test_svg_requires_view_box() -> None:
    with pytest.raises(MathValidationError, match="viewBox"):
        validate(svg(root_attributes={}))


def test_every_element_must_use_svg_namespace() -> None:
    data = svg('<x:g xmlns:x="urn:not-svg"><path d="M0 0L1 1Z"/></x:g>')

    with pytest.raises(MathValidationError, match="SVG namespace"):
        validate(data)


def test_metadata_remains_escaped_and_does_not_trigger_url_scanning() -> None:
    data = svg(
        '<g data-latex="xlink:href https://example.test/a?b=1&amp;c=2 '
        '&lt;not markup&gt;"/>'
    )

    assert validate(data) == data


def test_transform_functions_may_be_separated_by_whitespace_or_commas() -> None:
    data = svg('<g transform="translate(1 2), scale(1.02)\n rotate(30) skewX(2)"/>')

    assert validate(data) == data


def test_close_path_cannot_be_followed_by_implicit_arguments() -> None:
    data = svg('<path d="M0 0Z1"/>')
    script = f"""
from takumi_py.math._validation import validate_svg
from takumi_py.math.errors import MathValidationError

data = {data!r}
try:
    validate_svg(data, width_px=10, height_px=12, depth_px=0)
except MathValidationError:
    raise SystemExit(0)
raise SystemExit("path after closepath was accepted")
"""

    completed = subprocess.run(  # noqa: S603 - fixed interpreter and literal script.
        [sys.executable, "-c", script],
        capture_output=True,
        check=False,
        text=True,
        timeout=2,
    )

    assert completed.returncode == 0, completed.stderr


def test_close_path_can_be_followed_by_a_new_command() -> None:
    data = svg('<path d="M0 0Z M1 1L2 2Z"/>')

    assert validate(data) == data


def test_path_command_without_arguments_is_rejected() -> None:
    with pytest.raises(MathValidationError, match="missing arguments"):
        validate(svg('<path d="M0 0L"/>'))


@pytest.mark.parametrize(
    "color",
    ["black", "Red", "currentColor", "#abc", "#abcd", "#aabbcc", "#aabbccdd"],
)
def test_color_accepts_named_and_hex_values(color: str) -> None:
    assert validate_color(color) == color


@pytest.mark.parametrize(
    "color",
    [
        "rgb(0, 0, 0)",
        "rgba(0, 0, 0, 1)",
        "hsl(0 0% 0%)",
        "color(display-p3 0 0 0)",
        "url(#paint)",
    ],
)
def test_color_rejects_css_functions(color: str) -> None:
    with pytest.raises(MathValidationError, match="named color"):
        validate_color(color)


def test_svg_depth_is_bounded() -> None:
    data = svg("<g>" * 5 + '<rect width="1" height="1"/>' + "</g>" * 5)

    with pytest.raises(MathValidationError, match="depth limit"):
        validate(data, max_depth=5)


def test_svg_element_and_path_counts_are_bounded() -> None:
    path = '<path d="M0 0L1 1Z"/>'
    data = svg(path + path)

    with pytest.raises(MathValidationError, match="element limit"):
        validate(data, max_elements=2)
    with pytest.raises(MathValidationError, match="path limit"):
        validate(data, max_paths=1)


def test_svg_input_bytes_are_bounded() -> None:
    data = svg('<path d="M0 0L1 1Z"/>')

    with pytest.raises(MathValidationError, match="validation limit"):
        validate(data, max_bytes=len(data) - 1)


@pytest.mark.parametrize(
    "body",
    [
        "<script/>",
        "<style/>",
        '<path d="M0 0L1 1Z" href="https://example.test"/>',
        '<rect width="1" height="1" fill="url(#paint)"/>',
    ],
)
def test_external_and_executable_svg_content_is_rejected(body: str) -> None:
    with pytest.raises(MathValidationError):
        validate(svg(body))


def test_cancel_line_markup_is_allowed() -> None:
    data = svg(
        '<line x1="1.5" y1="-2" x2="8" y2="9" stroke="#000" stroke-width="1.25"/>'
    )

    assert validate(data) == data


def test_bbox_background_marker_is_allowed_on_rect() -> None:
    data = svg(
        '<rect x="0" y="-1" width="10" height="12" fill="red" data-bgcolor="true"/>'
    )

    assert validate(data) == data


def test_bbox_background_marker_must_be_literal_true() -> None:
    data = svg('<rect width="1" height="1" data-bgcolor="false"/>')

    with pytest.raises(MathValidationError, match="data-bgcolor"):
        validate(data)


def test_empty_path_is_allowed_only_for_an_encoded_character() -> None:
    data = svg('<path data-c="200B" d=""/>')

    assert validate(data) == data

    with pytest.raises(MathValidationError, match="encoded character"):
        validate(svg('<path d=""/>'))
    for codepoint in ("not-a-codepoint", "1234567"):
        with pytest.raises(MathValidationError, match="data-c"):
            validate(svg(f'<path data-c="{codepoint}" d=""/>'))


@pytest.mark.parametrize(
    "element",
    [
        '<line class="mjx-solid" x1="0" y1="0" x2="1" y2="1"/>',
        '<rect data-frame="true" width="1" height="1"/>',
        '<g data-frame-styles="solid none solid none"/>',
    ],
)
def test_raw_mathjax_layout_metadata_is_not_accepted(element: str) -> None:
    with pytest.raises(MathValidationError, match="unsupported attributes"):
        validate(svg(element))


def test_tex_nesting_budget_counts_braces_and_environment_boundaries() -> None:
    validate_tex_nesting_depth("{^{2}}", max_depth=2)
    validate_tex_nesting_depth(r"\left(x\right)", max_depth=1)
    validate_tex_nesting_depth(
        r"\begin{matrix}a\end{matrix}",
        max_depth=2,
    )

    for tex in (
        "{{{",
        r"\left(\left(x\right)\right)",
        r"\begin{matrix}\begin{matrix}x\end{matrix}\end{matrix}",
    ):
        with pytest.raises(TakumiError, match="nesting limit"):
            validate_tex_nesting_depth(tex, max_depth=1)


@pytest.mark.parametrize(
    "tex",
    [
        r"\verb|{{{\left(\begin{matrix}%|",
        r"\verb*+{{{\left(\begin{matrix}%+",
    ],
)
def test_tex_nesting_budget_skips_verbatim_delimiters(tex: str) -> None:
    validate_tex_nesting_depth(tex, max_depth=1)
