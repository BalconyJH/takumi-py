"""Strict validation helpers for the math value layer."""

from __future__ import annotations

import math
import re
from xml.etree import ElementTree as ET

from takumi_py.math.errors import MathValidationError

F32_MIN = 1.401298464324817e-45
F32_MAX = 3.4028234663852886e38
SVG_NAMESPACE = "http://www.w3.org/2000/svg"
MAX_VALIDATED_SVG_BYTES = 1_000_000

_NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
_NUMBER_RE = re.compile(_NUMBER)
_COMMA_OR_SPACE_RE = re.compile(r"[\s,]*")
_PX_RE = re.compile(rf"^({_NUMBER})px$")
_PATH_COMMANDS = frozenset("MmZzLlHhVvCcSsQqTtAa")
_PATH_ARITY = {
    "M": 2,
    "L": 2,
    "H": 1,
    "V": 1,
    "C": 6,
    "S": 4,
    "Q": 4,
    "T": 2,
    "A": 7,
    "Z": 0,
}
_SAFE_COLOR_NAMES = frozenset(
    """
    aliceblue antiquewhite aqua aquamarine azure beige bisque black
    blanchedalmond blue blueviolet brown burlywood cadetblue chartreuse
    chocolate coral cornflowerblue cornsilk crimson cyan darkblue darkcyan
    darkgoldenrod darkgray darkgreen darkgrey darkkhaki darkmagenta
    darkolivegreen darkorange darkorchid darkred darksalmon darkseagreen
    darkslateblue darkslategray darkslategrey darkturquoise darkviolet
    deeppink deepskyblue dimgray dimgrey dodgerblue firebrick floralwhite
    forestgreen fuchsia gainsboro ghostwhite gold goldenrod gray green
    greenyellow grey honeydew hotpink indianred indigo ivory khaki lavender
    lavenderblush lawngreen lemonchiffon lightblue lightcoral lightcyan
    lightgoldenrodyellow lightgray lightgreen lightgrey lightpink lightsalmon
    lightseagreen lightskyblue lightslategray lightslategrey lightsteelblue
    lightyellow lime limegreen linen magenta maroon mediumaquamarine
    mediumblue mediumorchid mediumpurple mediumseagreen mediumslateblue
    mediumspringgreen mediumturquoise mediumvioletred midnightblue mintcream
    mistyrose moccasin navajowhite navy oldlace olive olivedrab orange
    orangered orchid palegoldenrod palegreen paleturquoise palevioletred
    papayawhip peachpuff peru pink plum powderblue purple rebeccapurple red
    rosybrown royalblue saddlebrown salmon sandybrown seagreen seashell
    sienna silver skyblue slateblue slategray slategrey snow springgreen
    steelblue tan teal thistle tomato transparent turquoise violet wheat
    white whitesmoke yellow yellowgreen currentcolor
    """.split()  # noqa: SIM905 - the grouped literal is easier to audit.
)
_HEX_COLOR_RE = re.compile(
    r"^#(?:[0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})$",
    re.IGNORECASE,
)
_TRANSFORM_FUNCTION_RE = re.compile(r"([A-Za-z]+)\s*\(([^()]*)\)")
_TRANSFORM_ARITY = {
    "matrix": frozenset((6,)),
    "translate": frozenset((1, 2)),
    "scale": frozenset((1, 2)),
    "rotate": frozenset((1, 3)),
    "skewX": frozenset((1,)),
    "skewY": frozenset((1,)),
}

_ROOT_ATTRIBUTES = frozenset(
    {
        "width",
        "height",
        "role",
        "focusable",
        "viewBox",
        "preserveAspectRatio",
    }
)
_GROUP_ATTRIBUTES = frozenset(
    {
        "fill",
        "stroke",
        "stroke-width",
        "transform",
        "aria-hidden",
        "data-latex",
        "data-mml-node",
        "data-mjx-texclass",
    }
)
_PATH_ATTRIBUTES = frozenset(
    {
        "d",
        "data-c",
        "fill",
        "stroke",
        "stroke-width",
        "transform",
    }
)
_RECT_ATTRIBUTES = frozenset(
    {
        "x",
        "y",
        "width",
        "height",
        "rx",
        "ry",
        "fill",
        "stroke",
        "stroke-width",
        "transform",
        "data-bgcolor",
    }
)
_LINE_ATTRIBUTES = frozenset(
    {
        "x1",
        "y1",
        "x2",
        "y2",
        "stroke",
        "stroke-width",
        "transform",
    }
)
_SAFE_PRESERVE_ASPECT_RATIOS = frozenset(
    {
        "none",
        "xMinYMin",
        "xMidYMin",
        "xMaxYMin",
        "xMinYMid",
        "xMidYMid",
        "xMaxYMid",
        "xMinYMax",
        "xMidYMax",
        "xMaxYMax",
        "xMidYMid meet",
        "xMidYMid slice",
    }
)


def validate_positive_f32(name: str, value: object) -> float:
    """Return a finite positive float accepted by Takumi's f32 layout path."""
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not F32_MIN <= value <= F32_MAX
    ):
        raise MathValidationError(f"{name} must be a finite positive f32-range number")
    return float(value)


def validate_signed_f32(name: str, value: object) -> float:
    """Return a finite signed float accepted by Takumi's f32 layout path."""
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or abs(value) > F32_MAX
    ):
        raise MathValidationError(f"{name} must be a finite f32-range number")
    return float(value)


def validate_color(value: object) -> str | None:
    """Validate a deliberately small, injection-free CSS color subset."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise MathValidationError("color must be a string or None")
    color = value.strip()
    if not color or len(color) > 128 or any(ord(char) < 0x20 for char in color):
        raise MathValidationError("color must be a non-empty CSS color")
    lowered = color.lower()
    if not (lowered in _SAFE_COLOR_NAMES or _HEX_COLOR_RE.fullmatch(color)):
        raise MathValidationError(
            "color must be a CSS named color or a three-, four-, six-, or "
            "eight-digit hexadecimal color"
        )
    return color


def validate_svg(
    data: object,
    *,
    width_px: object,
    height_px: object,
    depth_px: object,
    max_bytes: int = MAX_VALIDATED_SVG_BYTES,
    max_elements: int = 20_000,
    max_paths: int = 4_000,
    max_depth: int = 128,
) -> bytes:
    """Validate and snapshot the strict, path-based SVG subset used by Takumi."""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise MathValidationError("MathSvg.data must be bytes-like")
    snapshot = bytes(data)
    if not snapshot:
        raise MathValidationError("MathSvg.data must not be empty")
    if len(snapshot) > max_bytes:
        raise MathValidationError(
            f"MathSvg.data exceeds the {max_bytes}-byte validation limit"
        )
    if not snapshot.startswith(b"<svg"):
        raise MathValidationError("MathSvg.data must be a single SVG root element")
    lowered = snapshot.lower()
    forbidden_markup = (
        b"<!doctype",
        b"<!entity",
        b"<?",
        b"<!--",
        b"<script",
        b"<style",
        b"<foreignobject",
        b"<text",
    )
    if any(token in lowered for token in forbidden_markup):
        raise MathValidationError("MathSvg.data contains forbidden XML or SVG markup")

    width = validate_positive_f32("width_px", width_px)
    height = validate_positive_f32("height_px", height_px)
    depth = validate_signed_f32("depth_px", depth_px)
    if not math.isfinite(height - depth):
        raise MathValidationError("height_px - depth_px must be finite")

    try:
        root = ET.fromstring(snapshot)  # noqa: S314 - DTDs/entities are rejected above.
    except ET.ParseError as error:
        raise MathValidationError(
            f"MathSvg.data is not well-formed XML: {error}"
        ) from error

    if root.tag != f"{{{SVG_NAMESPACE}}}svg":
        raise MathValidationError("MathSvg.data must have an SVG namespace root")
    if b'xmlns="http://www.w3.org/2000/svg"' not in snapshot[:256]:
        raise MathValidationError("MathSvg root must declare the SVG namespace")
    if root.get("viewBox") is None:
        raise MathValidationError("SVG root is missing viewBox")

    element_count = 0
    path_count = 0
    stack = [(root, 1)]
    while stack:
        element, depth_level = stack.pop()
        if depth_level > max_depth:
            raise MathValidationError("MathSvg.data exceeds the SVG depth limit")
        element_count += 1
        if element_count > max_elements:
            raise MathValidationError("MathSvg.data exceeds the SVG element limit")
        if element.text and element.text.strip():
            raise MathValidationError("MathSvg.data must not contain text nodes")
        if element.tail and element.tail.strip():
            raise MathValidationError("MathSvg.data contains trailing text")
        name = _local_name(element.tag)
        if name == "svg":
            if element is not root:
                raise MathValidationError("nested SVG roots are not allowed")
            attributes = _ROOT_ATTRIBUTES
        elif name == "g":
            attributes = _GROUP_ATTRIBUTES
        elif name == "path":
            attributes = _PATH_ATTRIBUTES
            path_count += 1
            if path_count > max_paths:
                raise MathValidationError("MathSvg.data exceeds the SVG path limit")
        elif name == "rect":
            attributes = _RECT_ATTRIBUTES
        elif name == "line":
            attributes = _LINE_ATTRIBUTES
        else:
            raise MathValidationError(f"SVG element <{name}> is not allowed")
        if any(attribute not in attributes for attribute in element.attrib):
            unexpected = sorted(set(element.attrib) - attributes)
            raise MathValidationError(
                f"SVG element <{name}> has unsupported attributes: "
                + ", ".join(unexpected)
            )
        for attribute, value in element.attrib.items():
            _validate_svg_attribute(name, attribute, value)
        stack.extend((child, depth_level + 1) for child in element)

    root_width = _parse_px_attribute(root, "width")
    root_height = _parse_px_attribute(root, "height")
    if not math.isclose(root_width, width, rel_tol=1e-9, abs_tol=1e-9):
        raise MathValidationError("MathSvg width_px does not match the SVG root")
    if not math.isclose(root_height, height, rel_tol=1e-9, abs_tol=1e-9):
        raise MathValidationError("MathSvg height_px does not match the SVG root")
    return snapshot


def _local_name(tag: object) -> str:
    if not isinstance(tag, str):
        raise MathValidationError("SVG contains a non-element XML node")
    prefix = f"{{{SVG_NAMESPACE}}}"
    if not tag.startswith(prefix):
        raise MathValidationError("every SVG element must use the SVG namespace")
    return tag.rsplit("}", 1)[-1]


def _validate_svg_attribute(element: str, attribute: str, value: str) -> None:
    lowered = attribute.lower()
    if lowered.startswith("on") or lowered in {"style", "href", "src"}:
        raise MathValidationError(f"SVG attribute {attribute!r} is not allowed")
    if element == "svg":
        if attribute == "role" and value != "img":
            raise MathValidationError("SVG role must be 'img'")
        if attribute == "focusable" and value not in {"true", "false"}:
            raise MathValidationError("SVG focusable must be true or false")
        if attribute == "viewBox":
            _validate_view_box(value)
        if (
            attribute == "preserveAspectRatio"
            and value not in _SAFE_PRESERVE_ASPECT_RATIOS
        ):
            raise MathValidationError("unsupported SVG preserveAspectRatio value")
        return
    if attribute in {"fill", "stroke"}:
        if value == "none":
            return
        if validate_color(value) is None:
            raise MathValidationError(f"SVG {attribute} value is not an allowed color")
        return
    if attribute == "stroke-width":
        _validate_nonnegative_number("stroke-width", value)
        return
    if attribute == "transform":
        _validate_transform(value)
        return
    if attribute == "d":
        _validate_path_data(value)
        return
    if attribute in {"x", "y", "x1", "y1", "x2", "y2", "width", "height", "rx", "ry"}:
        _validate_finite_number(attribute, value)
        if attribute in {"width", "height", "rx", "ry"} and float(value) < 0:
            raise MathValidationError(f"SVG {attribute} must not be negative")
        return
    if attribute == "data-c":
        if not re.fullmatch(r"[0-9A-Fa-f]+", value):
            raise MathValidationError("SVG data-c must be a hexadecimal codepoint")
        return
    if attribute == "data-bgcolor" and value != "true":
        raise MathValidationError("SVG data-bgcolor must be true")
    if attribute == "aria-hidden" and value not in {"true", "false"}:
        raise MathValidationError("SVG aria-hidden must be true or false")
    if "\x00" in value:
        raise MathValidationError("SVG attribute contains a NUL character")


def _parse_px_attribute(root: ET.Element, name: str) -> float:
    raw = root.get(name)
    if raw is None:
        raise MathValidationError(f"SVG root is missing {name}")
    match = _PX_RE.fullmatch(raw)
    if match is None:
        raise MathValidationError(f"SVG root {name} must be an explicit px value")
    value = float(match.group(1))
    return validate_positive_f32(f"SVG root {name}", value)


def _validate_view_box(value: str) -> None:
    parts = [part for part in re.split(r"[\s,]+", value.strip()) if part]
    if len(parts) != 4:
        raise MathValidationError("SVG viewBox must contain four numbers")
    for part in parts:
        _validate_finite_number("viewBox", part)
    if float(parts[2]) <= 0 or float(parts[3]) <= 0:
        raise MathValidationError("SVG viewBox width and height must be positive")


def _validate_finite_number(name: str, value: str) -> None:
    if _NUMBER_RE.fullmatch(value) is None:
        raise MathValidationError(f"SVG {name} must contain a finite number")
    number = float(value)
    if not math.isfinite(number) or abs(number) > F32_MAX:
        raise MathValidationError(f"SVG {name} must be within the finite f32 range")


def _validate_nonnegative_number(name: str, value: str) -> None:
    _validate_finite_number(name, value)
    if float(value) < 0:
        raise MathValidationError(f"SVG {name} must not be negative")


def _validate_transform(value: str) -> None:
    position = 0
    found = False
    while position < len(value):
        position = _skip_separators(value, position)
        if position >= len(value):
            break
        match = _TRANSFORM_FUNCTION_RE.match(value, position)
        if match is None:
            raise MathValidationError("SVG transform contains unsupported syntax")
        found = True
        name, arguments = match.groups()
        if name not in _TRANSFORM_ARITY:
            raise MathValidationError(f"SVG transform {name!r} is not allowed")
        values = [part for part in re.split(r"[\s,]+", arguments.strip()) if part]
        if len(values) not in _TRANSFORM_ARITY[name]:
            raise MathValidationError(
                f"SVG transform {name!r} has the wrong argument count"
            )
        for number in values:
            _validate_finite_number("transform", number)
        position = match.end()
    if not found:
        raise MathValidationError("SVG transform must contain a supported function")


def _validate_path_data(value: str) -> None:
    if not value or len(value) > 500_000:
        raise MathValidationError("SVG path data is empty or over budget")
    position = 0
    command: str | None = None
    first_command = True
    awaiting_arguments = False
    while True:
        position = _skip_separators(value, position)
        if position >= len(value):
            if awaiting_arguments:
                raise MathValidationError("SVG path command is missing arguments")
            break
        char = value[position]
        if char in _PATH_COMMANDS:
            if awaiting_arguments:
                raise MathValidationError("SVG path command is missing arguments")
            command = char
            position += 1
            if first_command and command not in {"M", "m"}:
                raise MathValidationError("SVG path data must start with moveto")
            first_command = False
            upper = command.upper()
            arity = _PATH_ARITY[upper]
            if arity == 0:
                command = None
                continue
            awaiting_arguments = True
        elif command is None:
            raise MathValidationError("SVG path data is missing a command")
        else:
            upper = command.upper()
            arity = _PATH_ARITY[upper]
        for argument_index in range(arity):
            position = _skip_separators(value, position)
            match = _NUMBER_RE.match(value, position)
            if match is None:
                if awaiting_arguments:
                    raise MathValidationError("SVG path command is missing arguments")
                raise MathValidationError("SVG path data has an invalid argument")
            number = float(match.group())
            if not math.isfinite(number) or abs(number) > F32_MAX:
                raise MathValidationError("SVG path number is outside the f32 range")
            if upper == "A" and argument_index in {3, 4} and number not in {0.0, 1.0}:
                raise MathValidationError("SVG arc flags must be 0 or 1")
            position = match.end()
        awaiting_arguments = False
        if upper in {"M", "L"}:
            command = "L" if command == "M" else "l" if command == "m" else command


def _skip_separators(value: str, position: int) -> int:
    match = _COMMA_OR_SPACE_RE.match(value, position)
    if match is None:
        raise AssertionError("the separator pattern must always match")
    return match.end()
