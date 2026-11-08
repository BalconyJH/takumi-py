from pathlib import Path

from takumi_py import (
    Document,
    LayoutOptions,
    RasterOptions,
    Renderer,
    compile_document,
)
from takumi_py.math import MathOptions, MathTypesetter

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

with MathTypesetter() as typesetter:
    inline = typesetter.typeset(
        r"E = mc^2",
        options=MathOptions(font_size_px=32, color="#000000"),
    )
    display = typesetter.typeset(
        r"\frac{x^2 + y^2}{a + b}",
        options=MathOptions(display=True, font_size_px=42, color="#000000"),
    )

    document = Document.from_node(
        {
            "type": "container",
            "style": {
                "width": "100%",
                "height": "520px",
                "boxSizing": "border-box",
                "padding": "72px",
                "backgroundColor": "#ffffff",
                "color": "#000000",
                "fontSize": "28px",
                "lineHeight": "1.5",
            },
            "children": [
                {
                    "type": "text",
                    "text": "Mathematical formulas",
                    "style": {
                        "display": "block",
                        "fontSize": "42px",
                        "fontWeight": "700",
                        "marginBottom": "40px",
                    },
                },
                {"type": "text", "text": "Inline formula: "},
                inline.to_fragment(),
                {"type": "text", "text": " keeps its baseline with body text."},
                display.to_fragment(),
                {
                    "type": "text",
                    "text": "The display fraction is centered in its own block.",
                    "style": {"fontSize": "22px", "marginTop": "24px"},
                },
            ],
        }
    )

compiled = compile_document(document)
layout = LayoutOptions(width=960, height=520)
renderer = Renderer()

(OUTPUT_DIR / "math.png").write_bytes(
    renderer.render(compiled, layout=layout, output=RasterOptions(scale=2))
)
(OUTPUT_DIR / "math.svg").write_text(
    renderer.render_svg(compiled, layout=layout),
    encoding="utf-8",
)
