from takumi_py import Renderer


def test_render_node_returns_png_bytes() -> None:
    png = Renderer().render_node(
        {"type": "text", "text": "hello"},
        stylesheets=["span { font-size: 32px; color: black; }"],
        width=240,
        height=120,
    )

    assert png.startswith(b"\x89PNG")


def test_compiled_node_can_render_repeatedly() -> None:
    renderer = Renderer()
    node = renderer.compile_node({"type": "text", "text": "hello"}, validate=True)
    stylesheet = renderer.compile_stylesheet("span { font-size: 32px; }")

    first = renderer.render_compiled(
        node, stylesheets=[stylesheet], width=240, height=120
    )
    second = renderer.render_compiled(
        node, stylesheets=[stylesheet], width=240, height=120
    )

    assert first.startswith(b"\x89PNG")
    assert second.startswith(b"\x89PNG")
