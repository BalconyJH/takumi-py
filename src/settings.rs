//! Render settings, read from the Python layer's resolved `RenderOptions`.

use pyo3::{Bound, PyAny, PyResult, exceptions::PyValueError, types::PyAnyMethods};
use takumi::prelude::{FontFamily, Lang, Viewport};

use crate::{
  images::ImageInput,
  options::DitheringAlgorithm,
  validate::{self, attr},
};

/// Validated settings shared by every render, measure, SVG, and animation call.
pub(crate) struct RenderSettings {
  width: Option<u32>,
  height: Option<u32>,
  font_size: f32,
  device_pixel_ratio: f32,
  pub(crate) draw_debug_border: bool,
  pub(crate) time_ms: u64,
  pub(crate) dithering: DitheringAlgorithm,
  pub(crate) images: Vec<ImageInput>,
  font_families: Option<Vec<String>>,
  pub(crate) lang: Option<Lang>,
}

impl RenderSettings {
  /// Reads a `NativeRenderSettings` object, rejecting invalid values with `ValueError`.
  pub(crate) fn from_py(settings: &Bound<'_, PyAny>) -> PyResult<Self> {
    let width = validate::optional_dimension("width", attr(settings, "width")?)?;
    let height = validate::optional_dimension("height", attr(settings, "height")?)?;
    let font_size = validate::positive("font_size", attr(settings, "font_size")?)?;
    let device_pixel_ratio =
      validate::positive("device_pixel_ratio", attr(settings, "device_pixel_ratio")?)?;
    let time_ms = validate::non_negative("time_ms", attr(settings, "time_ms")?)?;
    let lang = attr::<Option<String>>(settings, "lang")?
      .map(|lang| {
        Lang::parse(&lang).map_err(|_| {
          PyValueError::new_err(format!(
            "lang must be a valid BCP-47 language tag, got {lang:?}"
          ))
        })
      })
      .transpose()?;

    Ok(Self {
      width,
      height,
      font_size,
      device_pixel_ratio,
      draw_debug_border: attr(settings, "draw_debug_border")?,
      time_ms,
      dithering: DitheringAlgorithm::parse(&attr::<String>(settings, "dithering")?)?,
      images: ImageInput::from_py_list(&settings.getattr("images")?)?,
      font_families: attr(settings, "font_families")?,
      lang,
    })
  }

  pub(crate) fn viewport(&self) -> Viewport {
    self
      .svg_viewport()
      .with_device_pixel_ratio(self.device_pixel_ratio)
  }

  /// SVG output has no device pixel ratio.
  pub(crate) fn svg_viewport(&self) -> Viewport {
    Viewport::new((self.width, self.height)).with_font_size(self.font_size)
  }

  pub(crate) fn font_family(&self) -> Option<FontFamily> {
    self.font_families.clone().map(FontFamily::from_names)
  }
}
