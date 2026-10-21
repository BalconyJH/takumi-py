//! Output format and dithering names accepted by the Python API.

use pyo3::PyResult;
use takumi::prelude::DitheringAlgorithm as CoreDitheringAlgorithm;

use crate::errors::{AnimationError, UnsupportedFormatError};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum OutputFormat {
  Png,
  Jpeg,
  WebP,
  Ico,
  Raw,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum AnimationOutputFormat {
  WebP,
  Apng,
  Gif,
}

impl AnimationOutputFormat {
  pub(crate) fn parse(value: &str) -> PyResult<Self> {
    match value {
      "webp" => Ok(Self::WebP),
      "apng" => Ok(Self::Apng),
      "gif" => Ok(Self::Gif),
      other => Err(AnimationError::new_err(format!(
        "unsupported animation output format {other:?}"
      ))),
    }
  }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum DitheringAlgorithm {
  None,
  OrderedBayer,
  FloydSteinberg,
}

impl DitheringAlgorithm {
  pub(crate) fn parse(value: &str) -> PyResult<Self> {
    match value {
      "none" => Ok(Self::None),
      "ordered-bayer" => Ok(Self::OrderedBayer),
      "floyd-steinberg" => Ok(Self::FloydSteinberg),
      other => Err(UnsupportedFormatError::new_err(format!(
        "unsupported dithering algorithm {other:?}"
      ))),
    }
  }
}

impl From<DitheringAlgorithm> for CoreDitheringAlgorithm {
  fn from(value: DitheringAlgorithm) -> Self {
    match value {
      DitheringAlgorithm::None => Self::None,
      // Takumi 2.15 dropped the whole-image error-diffusion pass; its
      // `FloydSteinberg` variant is a deprecated alias of `OrderedBayer`.
      DitheringAlgorithm::OrderedBayer | DitheringAlgorithm::FloydSteinberg => Self::OrderedBayer,
    }
  }
}

impl OutputFormat {
  pub(crate) fn parse(value: &str) -> PyResult<Self> {
    match value {
      "png" => Ok(Self::Png),
      "jpeg" | "jpg" => Ok(Self::Jpeg),
      "webp" => Ok(Self::WebP),
      "ico" => Ok(Self::Ico),
      "raw" => Ok(Self::Raw),
      other => Err(UnsupportedFormatError::new_err(format!(
        "unsupported output format {other:?}"
      ))),
    }
  }
}
