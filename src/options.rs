use pyo3::PyResult;
use pyo3::exceptions::PyValueError;
use takumi::prelude::{
    DitheringAlgorithm as CoreDitheringAlgorithm, OutputFormat as CoreOutputFormat, Quality,
};

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

    pub(crate) fn image_format(
        self,
        quality: Option<u8>,
        lossless: Option<bool>,
    ) -> PyResult<Option<CoreOutputFormat>> {
        if lossless.is_some() && self != Self::WebP {
            return Err(PyValueError::new_err(
                "lossless is only supported when format is 'webp'",
            ));
        }
        if self == Self::WebP && lossless == Some(true) && quality.is_some() {
            return Err(PyValueError::new_err(
                "quality cannot be set when lossless WebP is requested",
            ));
        }

        match self {
            Self::Png => Ok(Some(CoreOutputFormat::Png)),
            Self::Jpeg => Ok(Some(CoreOutputFormat::Jpeg {
                quality: quality.map_or_else(Quality::default, Quality::new),
            })),
            Self::WebP if lossless.unwrap_or(quality.is_none()) => {
                Ok(Some(CoreOutputFormat::WebPLossless))
            }
            Self::WebP => Ok(Some(CoreOutputFormat::WebP {
                quality: quality.map_or_else(Quality::default, Quality::new),
            })),
            Self::Ico => Ok(Some(CoreOutputFormat::Ico)),
            Self::Raw => Ok(None),
        }
    }
}
