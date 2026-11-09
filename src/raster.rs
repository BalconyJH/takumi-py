//! An owned static bitmap. Encoding borrows it and never re-runs layout or paint.

use std::sync::Arc;

use pyo3::{Py, PyResult, Python, exceptions::PyValueError, prelude::*, types::PyBytes};
use takumi::prelude::Bitmap;

use crate::encode::ImageEncoding;

#[pyclass(module = "takumi_py._core", frozen)]
pub struct RasterImage {
  image: Arc<Bitmap>,
}

impl RasterImage {
  pub(crate) fn new(image: Bitmap) -> Self {
    Self {
      image: Arc::new(image),
    }
  }
}

#[pymethods]
impl RasterImage {
  #[staticmethod]
  pub fn from_raw(data: &[u8], width: u32, height: u32) -> PyResult<Self> {
    if width == 0 || height == 0 {
      return Err(PyValueError::new_err("width and height must be positive"));
    }
    let expected = u64::from(width)
      .checked_mul(u64::from(height))
      .and_then(|pixels| pixels.checked_mul(4));
    if expected != Some(data.len() as u64) {
      return Err(PyValueError::new_err(
        "RGBA buffer size must equal width * height * 4",
      ));
    }
    Bitmap::from_raw(width, height, data.to_vec())
      .map(Self::new)
      .ok_or_else(|| PyValueError::new_err("invalid RGBA buffer dimensions"))
  }

  #[getter]
  pub fn width(&self) -> u32 {
    self.image.width()
  }

  #[getter]
  pub fn height(&self) -> u32 {
    self.image.height()
  }

  pub fn tobytes(&self, py: Python<'_>) -> Py<PyBytes> {
    PyBytes::new(py, self.image.as_raw()).unbind()
  }

  #[pyo3(signature = (*, format="png", quality=None, lossless=None))]
  pub fn encode(
    &self,
    py: Python<'_>,
    format: &str,
    quality: Option<u8>,
    lossless: Option<bool>,
  ) -> PyResult<Py<PyBytes>> {
    let encoding = ImageEncoding::new(format, quality, lossless)?;
    if format == "raw" {
      return Ok(self.tobytes(py));
    }
    let image = Arc::clone(&self.image);
    let output = py.detach(move || encoding.encode_ref(&image))?;
    Ok(PyBytes::new(py, &output).unbind())
  }
}
