from __future__ import annotations

from time import perf_counter

from takumi_py import TemplateRenderer


def main() -> None:
    renderer = TemplateRenderer("examples/templates")
    started = perf_counter()
    count = 50
    for _ in range(count):
        renderer.render(
            "card.html.jinja",
            {"title": "Hello", "subtitle": "Rendered by Takumi"},
            width=240,
            height=120,
        )
    elapsed = perf_counter() - started
    print(f"{count / elapsed:.2f} ops/sec")


if __name__ == "__main__":
    main()
