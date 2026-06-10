from importlib.resources import files


def test_package_declares_typing_artifacts() -> None:
    package = files("takumi_py")

    assert package.joinpath("py.typed").is_file()
    assert package.joinpath("_core.pyi").is_file()
