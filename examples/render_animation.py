from pathlib import Path

from takumi_py import AnimationScene, Renderer

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

renderer = Renderer()

html = """
<div class="box"></div>
"""

stylesheets = [
    """
@keyframes fade {
  from { opacity: 0; transform: scale(0.7); }
  to { opacity: 1; transform: scale(1); }
}
.box {
  width: 128px;
  height: 128px;
  background: black;
  animation: fade 1000ms both;
}
"""
]

(OUTPUT_DIR / "animation-frame.png").write_bytes(
    renderer.render_html(
        html,
        stylesheets=stylesheets,
        width=160,
        height=160,
        time_ms=500,
    )
)

webp = renderer.render_animation(
    [
        AnimationScene(
            {
                "type": "container",
                "style": {
                    "width": "100%",
                    "height": "100%",
                    "backgroundColor": "black",
                },
            },
            duration_ms=120,
        ),
        AnimationScene(
            {
                "type": "container",
                "style": {
                    "width": "100%",
                    "height": "100%",
                    "backgroundColor": "white",
                },
            },
            duration_ms=120,
        ),
    ],
    width=160,
    height=160,
    fps=20,
)

(OUTPUT_DIR / "animation.webp").write_bytes(webp)
