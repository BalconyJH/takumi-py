from pathlib import Path
import runpy

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


def test_examples_run_successfully() -> None:
    examples = [
        "render_node.py",
        "render_html.py",
        "render_template.py",
        "render_options_measure.py",
        "render_resources.py",
        "render_animation.py",
    ]

    for example in examples:
        runpy.run_path(str(EXAMPLES_DIR / example), run_name="__main__")

    output_dir = EXAMPLES_DIR / "output"
    expected_outputs = [
        "node.png",
        "html.png",
        "template.png",
        "options-measure.png",
        "resources.png",
        "animation-frame.png",
        "animation.webp",
    ]

    for output in expected_outputs:
        assert output_dir.joinpath(output).is_file()
