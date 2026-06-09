from __future__ import annotations

from time import perf_counter

from takumi_py import Renderer


def main() -> None:
    renderer = Renderer()
    node = renderer.compile_node({"type": "text", "text": "hello"}, validate=True)
    stylesheet = renderer.compile_stylesheet("span { font-size: 32px; color: black; }")

    started = perf_counter()
    count = 50
    for _ in range(count):
        renderer.render_compiled(node, stylesheets=[stylesheet], width=240, height=120)
    elapsed = perf_counter() - started
    print(f"{count / elapsed:.2f} ops/sec")


if __name__ == "__main__":
    main()
