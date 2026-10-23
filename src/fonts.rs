//! Font registration: `FontResource` values read from Python and registered with Takumi,
//! recorded in the renderer's font cache.

use std::sync::Arc;

use pyo3::{Bound, PyAny, PyResult, exceptions::PyValueError, prelude::*, types::PyBytes};
use takumi::prelude::{
  FontOverride, FontResource, FontStyle, Fonts, FromCssStr, GenericFamily, UnicodeRange,
  UnicodeRangeSet,
};
use takumi_bindings_common::{default_fonts, font_cache::FontCache, input::register_resource};
use takumi_core::resources::font::RegisteredFamily;

use crate::{
  errors::FontError,
  validate::{self, attr},
};

const MAX_CODEPOINT: u32 = 0x10_FFFF;

/// A font as the Python layer passes it: raw bytes, or a `FontResource` whose fields
/// override what the file declares.
pub(crate) struct FontInput {
  data: Vec<u8>,
  name: Option<String>,
  weight: Option<f64>,
  style: Option<String>,
  subset_of: Option<String>,
  generic_family: Option<String>,
  unicode_range: Option<Vec<Vec<u32>>>,
}

impl FontInput {
  pub(crate) fn from_py(font: &Bound<'_, PyAny>) -> PyResult<Self> {
    let raw = match font.cast::<PyBytes>() {
      Ok(data) => Some(data.as_bytes().to_vec()),
      Err(_) if !font.hasattr("data")? => Some(font.extract()?),
      Err(_) => None,
    };
    if let Some(data) = raw {
      return Ok(Self {
        data,
        name: None,
        weight: None,
        style: None,
        subset_of: None,
        generic_family: None,
        unicode_range: None,
      });
    }

    Ok(Self {
      data: attr(font, "data")?,
      name: attr(font, "name")?,
      weight: attr(font, "weight")?,
      style: attr(font, "style")?,
      subset_of: attr(font, "subset_of")?,
      generic_family: attr(font, "generic_family")?,
      unicode_range: attr(font, "unicode_range")?,
    })
  }

  /// Registers the font and records it in `cache` under `key`. A font that is not
  /// `pinned` can be released for space, and admitting it releases the least recently
  /// used unpinned families past the cache budget. Returns the family names Takumi
  /// registered.
  pub(crate) fn register(
    self,
    fonts: &mut Fonts,
    cache: &mut FontCache,
    key: Option<&str>,
    pinned: bool,
  ) -> PyResult<Vec<String>> {
    let style = self
      .style
      .as_deref()
      .map(|style| {
        FontStyle::from_css_str(style)
          .map_err(|_| FontError::new_err(format!("unsupported font style {style:?}")))
      })
      .transpose()?;
    // Since Takumi 2.16 `subset_of` only names the family, taking precedence over
    // `name`; `unicode_range` decides which subset serves a codepoint.
    let mut resource = FontResource::new(self.data)
      .override_info(FontOverride {
        family_name: self.subset_of.or(self.name).map(Arc::from),
        width: None,
        style,
        weight: self.weight.map(validate::font_weight).transpose()?,
        axes: Vec::new(),
      })
      .unicode_range(parse_unicode_range(self.unicode_range.unwrap_or_default())?);

    if let Some(generic_family) = self.generic_family {
      resource = resource.generic_family(parse_generic_family(&generic_family)?);
    }

    let (registered, bytes) = register_resource(fonts, resource).map_err(font_error)?;
    cache
      .admit(fonts, key, &registered, bytes, pinned)
      .map_err(font_error)?;
    Ok(family_names(registered))
  }
}

/// The fonts a new renderer starts with: the bundled Geist last-resort font, or none.
pub(crate) fn initial_fonts(load_default_fonts: bool) -> PyResult<Fonts> {
  if load_default_fonts {
    default_fonts().map_err(font_error)
  } else {
    Ok(Fonts::default())
  }
}

pub(crate) fn family_names(families: Vec<RegisteredFamily>) -> Vec<String> {
  families.into_iter().map(|family| family.name).collect()
}

fn font_error(error: impl std::fmt::Display) -> PyErr {
  FontError::new_err(format!("failed to register font: {error}"))
}

/// Parses `(start, end)` pairs, given as tuples or lists.
fn parse_unicode_range(ranges: Vec<Vec<u32>>) -> PyResult<UnicodeRangeSet> {
  ranges
    .into_iter()
    .map(|range| {
      let [from, to] = range[..] else {
        return Err(PyValueError::new_err(format!(
          "unicode_range entries must be (start, end) pairs, got {range:?}"
        )));
      };
      if from > to || to > MAX_CODEPOINT {
        return Err(PyValueError::new_err(format!(
          "unicode_range entries must satisfy 0 <= start <= end <= 0x10FFFF, got ({from:#X}, {to:#X})"
        )));
      }
      Ok(UnicodeRange::new(from, to))
    })
    .collect()
}

fn parse_generic_family(value: &str) -> PyResult<GenericFamily> {
  match value {
    "serif" => Ok(GenericFamily::SERIF),
    "sans-serif" => Ok(GenericFamily::SANS_SERIF),
    "monospace" => Ok(GenericFamily::MONOSPACE),
    "cursive" => Ok(GenericFamily::CURSIVE),
    "fantasy" => Ok(GenericFamily::FANTASY),
    "system-ui" => Ok(GenericFamily::SYSTEM_UI),
    "ui-serif" => Ok(GenericFamily::UI_SERIF),
    "ui-sans-serif" => Ok(GenericFamily::UI_SANS_SERIF),
    "ui-monospace" => Ok(GenericFamily::UI_MONOSPACE),
    "ui-rounded" => Ok(GenericFamily::UI_ROUNDED),
    "emoji" => Ok(GenericFamily::EMOJI),
    "math" => Ok(GenericFamily::MATH),
    "fangsong" => Ok(GenericFamily::FANG_SONG),
    other => Err(FontError::new_err(format!(
      "unsupported generic font family {other:?}"
    ))),
  }
}
