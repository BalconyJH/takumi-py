//! Argument checks shared by the native entry points. Each raises `ValueError` with the
//! message the Python API documents.

use pyo3::{
  Bound, PyAny, PyResult, conversion::FromPyObjectOwned, exceptions::PyValueError,
  types::PyAnyMethods,
};

/// Reads attribute `name` from a Python options object, keeping the conversion error
/// CPython raises for a value of the wrong type or range.
pub(crate) fn attr<'py, T: FromPyObjectOwned<'py>>(
  object: &Bound<'py, PyAny>,
  name: &str,
) -> PyResult<T> {
  object.getattr(name)?.extract().map_err(Into::into)
}

pub(crate) fn dimension(name: &str, value: u32) -> PyResult<u32> {
  if value == 0 {
    return Err(PyValueError::new_err(format!(
      "{name} must be greater than zero"
    )));
  }
  Ok(value)
}

pub(crate) fn optional_dimension(name: &str, value: Option<u32>) -> PyResult<Option<u32>> {
  value.map(|value| dimension(name, value)).transpose()
}

pub(crate) fn positive(name: &str, value: f64) -> PyResult<f32> {
  if !value.is_finite() || value <= 0.0 {
    return Err(PyValueError::new_err(format!(
      "{name} must be a finite number greater than zero"
    )));
  }
  Ok(value as f32)
}

pub(crate) fn non_negative(name: &str, value: i64) -> PyResult<u64> {
  u64::try_from(value).map_err(|_| PyValueError::new_err(format!("{name} must be non-negative")))
}

pub(crate) fn quality(quality: Option<u8>) -> PyResult<Option<u8>> {
  if let Some(quality) = quality
    && quality > 100
  {
    return Err(PyValueError::new_err(
      "quality must be an integer in the range 0..=100",
    ));
  }
  Ok(quality)
}

pub(crate) fn webp_speed(speed: Option<u8>) -> PyResult<Option<u8>> {
  if let Some(speed) = speed
    && speed > 6
  {
    return Err(PyValueError::new_err(
      "webp_speed must be an integer in the range 0..=6",
    ));
  }
  Ok(speed)
}

pub(crate) fn fps(fps: u32) -> PyResult<u32> {
  if fps == 0 {
    return Err(PyValueError::new_err("fps must be greater than zero"));
  }
  Ok(fps)
}

pub(crate) fn scene_durations(durations: impl IntoIterator<Item = u32>) -> PyResult<()> {
  let mut durations = durations.into_iter().peekable();
  if durations.peek().is_none() {
    return Err(PyValueError::new_err(
      "expected at least one animation scene",
    ));
  }
  if durations.any(|duration_ms| duration_ms == 0) {
    return Err(PyValueError::new_err(
      "animation scene duration_ms must be greater than zero",
    ));
  }
  Ok(())
}

pub(crate) fn frame_duration_ms(duration_ms: u32) -> PyResult<u32> {
  if duration_ms == 0 {
    return Err(PyValueError::new_err(
      "animation frame duration_ms must be greater than zero",
    ));
  }
  Ok(duration_ms)
}

pub(crate) fn font_weight(weight: f64) -> PyResult<f32> {
  if !weight.is_finite() || !(1.0..=1000.0).contains(&weight) {
    return Err(PyValueError::new_err(
      "font weight must be a finite number in the range 1..=1000",
    ));
  }
  Ok(weight as f32)
}
