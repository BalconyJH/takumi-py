//! Image resources: `ImageResource` values read from Python and decoded through the
//! renderer's resource cache.

use std::{collections::HashMap, sync::Arc};

use pyo3::{Bound, PyAny, PyResult, exceptions::PyValueError, prelude::*};
use takumi::prelude::{ImageCacheMode, ImageSource};
use takumi_core::resources::image::ResourceCache;

use crate::{errors::ResourceError, validate::attr};

/// Decoded images keyed by the `src` that nodes reference them with.
pub(crate) type ImageMap = HashMap<Arc<str>, ImageSource>;

#[derive(Clone, Copy, PartialEq, Eq)]
enum CacheMode {
  Auto,
  None,
}

impl CacheMode {
  fn from_str(value: &str) -> PyResult<Self> {
    match value {
      "auto" => Ok(Self::Auto),
      "none" => Ok(Self::None),
      other => Err(PyValueError::new_err(format!(
        "unsupported image cache mode {other:?}"
      ))),
    }
  }

  const fn upstream(self) -> ImageCacheMode {
    match self {
      Self::Auto => ImageCacheMode::Auto,
      Self::None => ImageCacheMode::None,
    }
  }
}

/// An `ImageResource` as the Python layer passes it: a source key, raw bytes, and a
/// validated cache policy.
#[derive(Clone)]
pub(crate) struct ImageInput {
  src: Arc<str>,
  data: Arc<[u8]>,
  cache: CacheMode,
}

impl ImageInput {
  pub(crate) fn from_py(resource: &Bound<'_, PyAny>) -> PyResult<Self> {
    Ok(Self {
      src: Arc::from(attr::<String>(resource, "src")?),
      data: Arc::from(attr::<Vec<u8>>(resource, "data")?),
      cache: CacheMode::from_str(&attr::<String>(resource, "cache")?)?,
    })
  }

  pub(crate) fn from_py_list(resources: &Bound<'_, PyAny>) -> PyResult<Vec<Self>> {
    resources
      .try_iter()?
      .map(|resource| Self::from_py(&resource?))
      .collect()
  }

  /// Decodes the bytes through `cache`, keyed by `src`.
  pub(crate) fn decode(&self, cache: &ResourceCache) -> PyResult<(Arc<str>, ImageSource)> {
    let image = cache
      .get_or_decode(&self.data, self.cache.upstream())
      .map_err(|error| {
        ResourceError::new_err(format!("failed to decode image resource: {error}"))
      })?;
    Ok((Arc::clone(&self.src), image))
  }
}

/// Decodes `inputs`; a later input replaces an earlier one with the same `src`.
pub(crate) fn decode_all(cache: &ResourceCache, inputs: Arc<[ImageInput]>) -> PyResult<ImageMap> {
  inputs.iter().map(|input| input.decode(cache)).collect()
}

/// Native encoded-resource snapshot; decoding still uses the chosen renderer's cache.
#[pyclass(module = "takumi_py._core", frozen)]
pub struct CompiledResources {
  pub(crate) images: Arc<[ImageInput]>,
}

#[pymethods]
impl CompiledResources {
  /// Return this snapshot followed by additional inputs without copying existing
  /// source keys or encoded buffers.
  pub fn merged(&self, resources: &Bound<'_, PyAny>) -> PyResult<Self> {
    let additional = ImageInput::from_py_list(resources)?;
    Ok(Self {
      images: merge_image_inputs(&self.images, additional)?.into(),
    })
  }
}

#[pyfunction]
pub(crate) fn compile_resources(resources: &Bound<'_, PyAny>) -> PyResult<CompiledResources> {
  let images = merge_image_inputs(&[], ImageInput::from_py_list(resources)?)?;
  Ok(CompiledResources {
    images: images.into(),
  })
}

pub(crate) fn read_resources(value: &Bound<'_, PyAny>) -> PyResult<Arc<[ImageInput]>> {
  if let Ok(resources) = value.extract::<PyRef<'_, CompiledResources>>() {
    return Ok(Arc::clone(&resources.images));
  }
  ImageInput::from_py_list(value).map(Arc::from)
}

/// Append inputs in first-seen order. Existing source keys and buffers are Arc
/// clones; only the pointer table is rebuilt.
fn merge_image_inputs(
  existing: &[ImageInput],
  additional: Vec<ImageInput>,
) -> PyResult<Vec<ImageInput>> {
  let mut merged = Vec::with_capacity(existing.len().saturating_add(additional.len()));
  let mut sources = HashMap::with_capacity(merged.capacity());

  for image in existing {
    sources.insert(Arc::clone(&image.src), merged.len());
    merged.push(image.clone());
  }

  for image in additional {
    if let Some(&index) = sources.get(image.src.as_ref()) {
      let previous = &merged[index];
      if previous.data == image.data && previous.cache == image.cache {
        continue;
      }
      return Err(ResourceError::new_err(format!(
        "conflicting image resources for src {:?}: bytes and cache must match",
        image.src
      )));
    }

    sources.insert(Arc::clone(&image.src), merged.len());
    merged.push(image);
  }

  Ok(merged)
}
