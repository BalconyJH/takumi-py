from takumi_py import Renderer, pack_node


def test_msgpack_node_codec() -> None:
    renderer = Renderer()
    packed = pack_node({"type": "text", "text": "hello"}, validate=True)
    compiled = renderer.compile_node(packed, codec="msgpack")

    png = renderer.render_compiled(compiled, width=240, height=120)

    assert png.startswith(b"\x89PNG")
