from __future__ import annotations

from time import perf_counter

from takumi_py import Renderer


HTML = """
<div class="card">Hello</div>
<style>
.card {
  width: 240px;
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  color: black;
}
</style>
"""


def main() -> None:
    renderer = Renderer()
    started = perf_counter()
    count = 50
    for _ in range(count):
        renderer.render_html(HTML, width=240, height=120)
    elapsed = perf_counter() - started
    print(f"{count / elapsed:.2f} ops/sec")


if __name__ == "__main__":
    main()
