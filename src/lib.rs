mod errors;
mod options;
mod renderer;

use pyo3::{prelude::*, types::PyModule};

#[pyfunction]
fn set_glyph_cache_max_bytes(max_bytes: usize) {
  takumi_core::resources::glyph_cache::set_glyph_cache_max_bytes(max_bytes);
}

#[pymodule]
fn _core(py: Python<'_>, module: &Bound<'_, PyModule>) -> PyResult<()> {
  module.add_class::<renderer::NativeRenderer>()?;
  module.add_class::<renderer::CompiledNode>()?;
  module.add_class::<renderer::CompiledStyleSheet>()?;
  module.add_function(wrap_pyfunction!(set_glyph_cache_max_bytes, module)?)?;

  module.add("TakumiError", py.get_type::<errors::TakumiError>())?;
  module.add("HtmlParseError", py.get_type::<errors::HtmlParseError>())?;
  module.add(
    "NodeValidationError",
    py.get_type::<errors::NodeValidationError>(),
  )?;
  module.add("NodeDecodeError", py.get_type::<errors::NodeDecodeError>())?;
  module.add("StyleSheetError", py.get_type::<errors::StyleSheetError>())?;
  module.add("RenderError", py.get_type::<errors::RenderError>())?;
  module.add("ResourceError", py.get_type::<errors::ResourceError>())?;
  module.add("FontError", py.get_type::<errors::FontError>())?;
  module.add("AnimationError", py.get_type::<errors::AnimationError>())?;
  module.add(
    "UnsupportedFormatError",
    py.get_type::<errors::UnsupportedFormatError>(),
  )?;

  Ok(())
}
