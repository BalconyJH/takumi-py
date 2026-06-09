use pyo3::PyResult;
use takumi::rendering::ImageOutputFormat;

use crate::errors::UnsupportedFormatError;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum OutputFormat {
    Png,
    Jpeg,
    WebP,
    Ico,
    Raw,
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
