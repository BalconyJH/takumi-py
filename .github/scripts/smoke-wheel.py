from __future__ import annotations

from importlib.metadata import version
import platform
import sys

from takumi_py import Renderer

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def main() -> None:
    renderer = Renderer()

    png = renderer.render_html(
        '<div class="card">wheel smoke</div>',
        stylesheets=[
            """
            .card {
              width: 160px;
              height: 80px;
              display: flex;
              align-items: center;
              justify-content: center;
              color: white;
              background: #111827;
              font-size: 20px;
            }
            """
        ],
        width=160,
        height=80,
    )
    if not png.startswith(PNG_SIGNATURE):
        raise SystemExit("render_html did not return PNG bytes")

    raw = renderer.render_node(
        {
            "type": "container",
            "style": {"width": "2px", "height": "2px", "backgroundColor": "black"},
        },
        width=2,
        height=2,
        format="raw",
    )
    if len(raw) != 2 * 2 * 4:
        raise SystemExit(f"raw output has unexpected size: {len(raw)}")

    svg = renderer.render_svg_html(
        '<div class="card">svg smoke</div>',
        stylesheets=[".card { width: 64px; height: 32px; color: black; }"],
        width=64,
        height=32,
    )
    if not svg.startswith("<svg") or 'width="64"' not in svg:
        raise SystemExit("render_svg_html did not return the expected SVG document")

    measured = renderer.measure_node(
        {
            "type": "container",
            "style": {"width": "48px", "height": "24px"},
            "children": [{"type": "text", "text": "measure"}],
        },
        width=None,
        height=None,
    )
    if measured.width != 48 or measured.height != 24:
        raise SystemExit(f"measure_node returned {measured.width}x{measured.height}")

    sys.stdout.write(
        f"takumi-py {version('takumi-py')} wheel smoke passed on {platform.platform()}\n"
    )


if __name__ == "__main__":
    main()
