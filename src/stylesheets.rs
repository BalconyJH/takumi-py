//! Compiled stylesheets: CSS text parsed strictly or error-tolerantly, and structured
//! keyframe rules.

use pyo3::{Bound, PyAny, PyRef, PyResult, prelude::*};
use serde::Deserialize;
use takumi::prelude::{KeyframesRule, StyleSheet};

use crate::errors::StyleSheetError;

#[pyclass(module = "takumi_py._core")]
pub struct CompiledStyleSheet {
  source: Source,
  stylesheet: StyleSheet,
}

/// What a compiled stylesheet came from, which decides how several of them merge.
enum Source {
  Css { text: String, lossy: bool },
  Keyframes(Vec<KeyframesRule>),
}

#[derive(Deserialize)]
struct KeyframesInput {
  #[serde(deserialize_with = "takumi_core::keyframes::deserialize_keyframes")]
  keyframes: Vec<KeyframesRule>,
}

impl CompiledStyleSheet {
  pub(crate) fn strict(css: &str) -> PyResult<Self> {
    let stylesheet =
      StyleSheet::parse(css).map_err(|error| StyleSheetError::new_err(error.to_string()))?;
    Ok(Self {
      source: Source::Css {
        text: css.to_owned(),
        lossy: false,
      },
      stylesheet,
    })
  }

  pub(crate) fn lossy(css: &str) -> Self {
    Self {
      source: Source::Css {
        text: css.to_owned(),
        lossy: true,
      },
      stylesheet: StyleSheet::parse_loosy(css),
    }
  }

  /// Compiles a `{"keyframes": ...}` mapping of structured keyframe rules.
  pub(crate) fn keyframes(keyframes: Bound<'_, PyAny>) -> PyResult<Self> {
    let input: KeyframesInput = serde_pyobject::from_pyobject(keyframes)
      .map_err(|error| StyleSheetError::new_err(error.to_string()))?;
    Ok(Self {
      stylesheet: StyleSheet::from(input.keyframes.clone()),
      source: Source::Keyframes(input.keyframes),
    })
  }
}

/// Merges compiled stylesheets in order. CSS sources are parsed again as one list, so
/// later rules cascade over earlier ones, and keyframe rules are appended after them.
pub(crate) fn merge(stylesheets: &[PyRef<'_, CompiledStyleSheet>]) -> PyResult<StyleSheet> {
  let css: Vec<(&str, bool, &StyleSheet)> = stylesheets
    .iter()
    .filter_map(|compiled| match &compiled.source {
      Source::Css { text, lossy } => Some((text.as_str(), *lossy, &compiled.stylesheet)),
      Source::Keyframes(_) => None,
    })
    .collect();
  let keyframes = stylesheets
    .iter()
    .filter_map(|compiled| match &compiled.source {
      Source::Keyframes(rules) => Some(rules),
      Source::Css { .. } => None,
    });

  let mut merged = match css.as_slice() {
    [] => StyleSheet::default(),
    [(_, _, only)] if css.len() == stylesheets.len() => return Ok((*only).clone()),
    _ if css.iter().any(|(_, lossy, _)| *lossy) => {
      StyleSheet::parse_owned_list_loosy(css.iter().map(|(text, ..)| (*text).to_owned()).collect())
    }
    _ => StyleSheet::parse_list(css.iter().map(|(text, ..)| *text).collect::<Vec<_>>())
      .map_err(|error| StyleSheetError::new_err(error.to_string()))?,
  };

  for rules in keyframes {
    merged.extend_keyframes(rules.clone());
  }
  Ok(merged)
}
