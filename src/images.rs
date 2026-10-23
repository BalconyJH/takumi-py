//! Image resources: `ImageResource` values read from Python and decoded through the
//! renderer's resource cache.

use std::{collections::HashMap, sync::Arc};

use pyo3::{Bound, PyAny, PyResult, exceptions::PyValueError, prelude::*};
use takumi::prelude::{ImageCacheMode, ImageSource};
use takumi_core::resources::image::ResourceCache;

use crate::{errors::ResourceError, validate::attr};

/// Decoded images keyed by the `src` that nodes reference them with.
pub(crate) type ImageMap = HashMap<Arc<str>, ImageSource>;

/// An `ImageResource` as the Python layer passes it: a source key, raw bytes, and a
/// cache hint.
pub(crate) struct ImageInput {
  src: String,
  data: Vec<u8>,
  cache: String,
}

impl ImageInput {
  pub(crate) fn from_py(resource: &Bound<'_, PyAny>) -> PyResult<Self> {
    Ok(Self {
      src: attr(resource, "src")?,
      data: attr(resource, "data")?,
      cache: attr(resource, "cache")?,
    })
  }

  pub(crate) fn from_py_list(resources: &Bound<'_, PyAny>) -> PyResult<Vec<Self>> {
    resources
      .try_iter()?
      .map(|resource| Self::from_py(&resource?))
      .collect()
  }

  /// Decodes the bytes through `cache`, keyed by `src`.
  pub(crate) fn decode(self, cache: &ResourceCache) -> PyResult<(Arc<str>, ImageSource)> {
    let mode = parse_cache_mode(&self.cache)?;
    let image = cache.get_or_decode(&self.data, mode).map_err(|error| {
      ResourceError::new_err(format!("failed to decode image resource: {error}"))
    })?;
    Ok((Arc::from(self.src), image))
  }
}

/// Decodes `inputs`; a later input replaces an earlier one with the same `src`.
pub(crate) fn decode_all(cache: &ResourceCache, inputs: Vec<ImageInput>) -> PyResult<ImageMap> {
  inputs
    .into_iter()
    .map(|input| input.decode(cache))
    .collect()
}

fn parse_cache_mode(value: &str) -> PyResult<ImageCacheMode> {
  match value {
    "auto" => Ok(ImageCacheMode::Auto),
    "none" => Ok(ImageCacheMode::None),
    other => Err(PyValueError::new_err(format!(
      "unsupported image cache mode {other:?}"
    ))),
  }
}
