use pyo3::PyResult;
use takumi::rendering::{DitheringAlgorithm as CoreDitheringAlgorithm, ImageOutputFormat};

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
            DitheringAlgorithm::OrderedBayer => Self::OrderedBayer,
            DitheringAlgorithm::FloydSteinberg => Self::FloydSteinberg,
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

    pub(crate) fn image_format(self) -> Option<ImageOutputFormat> {
        match self {
            Self::Png => Some(ImageOutputFormat::Png),
            Self::Jpeg => Some(ImageOutputFormat::Jpeg),
            Self::WebP => Some(ImageOutputFormat::WebP),
            Self::Ico => Some(ImageOutputFormat::Ico),
            Self::Raw => None,
        }
    }
}
