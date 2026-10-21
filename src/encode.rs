//! Output encoding: static image formats, animation containers, and raw frames.

use std::borrow::Cow;

use pyo3::{Bound, PyAny, PyErr, PyResult, exceptions::PyValueError};
use takumi::{
  prelude::{
    AnimatedGifOptions, AnimatedPngOptions, AnimatedWebpOptions, AnimationFormat, AnimationFrame,
    Bitmap, Error as CoreError, OutputFormat as CoreOutputFormat, Quality,
  },
  write_animated_gif, write_animated_png, write_animated_webp, write_image,
};

use crate::{
  errors::{AnimationError, RenderError},
  options::{AnimationOutputFormat, OutputFormat},
  validate::{self, attr},
};

/// A validated static output format; `None` returns the raw RGBA buffer.
#[derive(Clone, Copy)]
pub(crate) struct ImageEncoding(Option<CoreOutputFormat>);

impl ImageEncoding {
  /// Reads the `format`, `quality`, and `lossless` fields of a `RenderOptions` object,
  /// rejecting invalid combinations before anything renders.
  pub(crate) fn from_py(options: &Bound<'_, PyAny>) -> PyResult<Self> {
    let quality = validate::quality(attr(options, "quality")?)?;
    let format = OutputFormat::parse(&attr::<String>(options, "format")?)?;
    let lossless: Option<bool> = attr(options, "lossless")?;
    if format != OutputFormat::WebP {
      reject_lossless(lossless)?;
    }
    let lossy_quality = || quality.map_or_else(Quality::default, Quality::new);

    Ok(Self(match format {
      OutputFormat::Png => Some(CoreOutputFormat::Png),
      OutputFormat::Jpeg => Some(CoreOutputFormat::Jpeg {
        quality: lossy_quality(),
      }),
      OutputFormat::WebP if webp_lossless(quality, lossless)? => {
        Some(CoreOutputFormat::WebPLossless)
      }
      OutputFormat::WebP => Some(CoreOutputFormat::WebP {
        quality: lossy_quality(),
      }),
      OutputFormat::Ico => Some(CoreOutputFormat::Ico),
      OutputFormat::Raw => None,
    }))
  }

  pub(crate) fn encode(self, image: Bitmap) -> PyResult<Vec<u8>> {
    let Some(format) = self.0 else {
      return Ok(image.into_raw());
    };

    let mut buffer = Vec::new();
    write_image(&image, &mut buffer, format)
      .map_err(|error| RenderError::new_err(error.to_string()))?;
    Ok(buffer)
  }
}

/// A validated animation container with its encoder options.
#[derive(Clone, Copy)]
pub(crate) enum AnimationEncoder {
  WebP(AnimatedWebpOptions),
  Apng(AnimatedPngOptions),
  Gif(AnimatedGifOptions),
}

impl AnimationEncoder {
  /// Reads an `AnimationEncodeOptions` object, rejecting invalid combinations.
  pub(crate) fn from_py(options: &Bound<'_, PyAny>) -> PyResult<Self> {
    let quality = validate::quality(attr(options, "quality")?)?;
    let speed = validate::webp_speed(attr(options, "webp_speed")?)?;
    let lossless: Option<bool> = attr(options, "lossless")?;
    let loop_count: Option<u16> = attr(options, "loop_count")?;

    Ok(
      match AnimationOutputFormat::parse(&attr::<String>(options, "format")?)? {
        AnimationOutputFormat::WebP => {
          let mut webp = AnimatedWebpOptions::default();
          webp.blend = attr(options, "webp_blend")?;
          webp.dispose = attr(options, "webp_dispose")?;
          webp.loop_count = loop_count;
          webp.lossless = webp_lossless(quality, lossless)?;
          if let Some(quality) = quality {
            webp.quality = quality;
          }
          webp.speed = speed;
          Self::WebP(webp)
        }
        AnimationOutputFormat::Apng => {
          reject_lossless(lossless)?;
          let mut apng = AnimatedPngOptions::default();
          apng.loop_count = loop_count;
          Self::Apng(apng)
        }
        AnimationOutputFormat::Gif => {
          reject_lossless(lossless)?;
          let mut gif = AnimatedGifOptions::default();
          gif.loop_count = loop_count;
          Self::Gif(gif)
        }
      },
    )
  }

  /// The format for `write_animation`, which renders and encodes frame by frame.
  pub(crate) fn format(self) -> AnimationFormat {
    match self {
      Self::WebP(options) => AnimationFormat::WebP(options),
      Self::Apng(options) => AnimationFormat::Apng(options),
      Self::Gif(options) => AnimationFormat::Gif(options),
    }
  }

  /// Rejects a frame rate whose frame delays decoders would clamp to 100ms: 50 fps for
  /// GIF, which stores centiseconds, and 90 fps for WebP and APNG.
  pub(crate) fn validate_fps(self, fps: u32) -> PyResult<u32> {
    let max_fps = self.format().max_fps();
    if fps > max_fps {
      return Err(PyValueError::new_err(format!(
        "fps must not exceed {max_fps} for this animation format, got {fps}"
      )));
    }
    Ok(fps)
  }

  pub(crate) fn encode(self, frames: Vec<AnimationFrame>) -> PyResult<Vec<u8>> {
    let mut buffer = Vec::new();
    match self {
      Self::WebP(options) => write_animated_webp(Cow::Owned(frames), &mut buffer, options),
      Self::Apng(options) => write_animated_png(&frames, &mut buffer, options),
      Self::Gif(options) => write_animated_gif(Cow::Owned(frames), &mut buffer, options),
    }
    .map_err(|error| AnimationError::new_err(error.to_string()))?;
    Ok(buffer)
  }
}

/// Reads a `RawAnimationFrame` object: row-major RGBA bytes, dimensions, and duration.
pub(crate) fn raw_frame(frame: &Bound<'_, PyAny>) -> PyResult<AnimationFrame> {
  let data: Vec<u8> = attr(frame, "data")?;
  let width = validate::dimension("width", attr(frame, "width")?)?;
  let height = validate::dimension("height", attr(frame, "height")?)?;
  let duration_ms = validate::frame_duration_ms(attr(frame, "duration_ms")?)?;
  let image = Bitmap::from_raw(width, height, data).ok_or_else(|| {
    AnimationError::new_err("raw frame buffer size does not match width * height * 4")
  })?;
  Ok(AnimationFrame::new(image, duration_ms))
}

/// Splits a streamed animation failure into the encoder errors that `encode_frames` also
/// raises and the render errors a single frame raises.
pub(crate) fn animation_error(error: CoreError) -> PyErr {
  match error {
    CoreError::Encode(_)
    | CoreError::WebPError(_)
    | CoreError::IoError(_)
    | CoreError::EmptyAnimationFrames
    | CoreError::AnimationFrameRateTooHigh { .. }
    | CoreError::MixedAnimationFrameDimensions
    | CoreError::GifFrameDimensionsTooLarge { .. } => AnimationError::new_err(error.to_string()),
    error => RenderError::new_err(error.to_string()),
  }
}

/// WebP is lossless when requested explicitly or when no `quality` is given.
fn webp_lossless(quality: Option<u8>, lossless: Option<bool>) -> PyResult<bool> {
  if lossless == Some(true) && quality.is_some() {
    return Err(PyValueError::new_err(
      "quality cannot be set when lossless WebP is requested",
    ));
  }
  Ok(lossless.unwrap_or(quality.is_none()))
}

fn reject_lossless(lossless: Option<bool>) -> PyResult<()> {
  if lossless.is_some() {
    return Err(PyValueError::new_err(
      "lossless is only supported when format is 'webp'",
    ));
  }
  Ok(())
}
