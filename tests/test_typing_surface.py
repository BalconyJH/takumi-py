from importlib.resources import files
import inspect

from takumi_py import _core
from takumi_py.renderer import Renderer

RENDERER_PUBLIC_METHODS = {
    "clear_image_store",
    "compile_html",
    "compile_keyframes",
    "compile_node",
    "compile_stylesheet",
    "compile_stylesheet_lossy",
    "encode_frames",
    "load_font",
    "load_fonts",
    "measure_compiled",
    "measure_html",
    "measure_node",
    "put_persistent_image",
    "register_font",
    "register_fonts",
    "render_animation",
    "render_compiled",
    "render_html",
    "render_node",
    "render_sequence_at_time",
    "render_svg_compiled",
    "render_svg_html",
    "render_svg_node",
    "render_svg_template",
    "render_template",
}


def test_package_declares_typing_artifacts() -> None:
    package = files("takumi_py")

    assert package.joinpath("py.typed").is_file()
    assert package.joinpath("_core.pyi").is_file()


def test_native_exports_exist_at_runtime() -> None:
    assert all(hasattr(_core, name) for name in _core.__all__)


def test_renderer_public_surface_is_intentional_and_documented() -> None:
    public_methods = {
        name
        for name, value in vars(Renderer).items()
        if callable(value) and not name.startswith("_")
    }

    assert public_methods == RENDERER_PUBLIC_METHODS
    assert inspect.getdoc(Renderer.__init__) is not None
    assert all(inspect.getdoc(getattr(Renderer, name)) for name in public_methods)
