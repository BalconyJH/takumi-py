//! Compiled stylesheets: CSS text parsed strictly or error-tolerantly, structured
//! keyframe rules, and compositions that retain their original cascade source.

use pyo3::{Bound, PyAny, PyRef, PyResult, Python, prelude::*, types::PyDict};
use serde::Deserialize;
use takumi::prelude::{KeyframesRule, StyleSheet};

use crate::errors::StyleSheetError;

/// Compiles CSS without constructing a renderer.
#[pyfunction]
#[pyo3(signature = (css, *, strict=true))]
pub(crate) fn compile_stylesheet(
  py: Python<'_>,
  css: &str,
  strict: bool,
) -> PyResult<CompiledStyleSheet> {
  let text = css.to_owned();
  let parse_source = text.clone();
  let stylesheet = py
    .detach(move || {
      if strict {
        StyleSheet::parse(&parse_source).map_err(|error| error.to_string())
      } else {
        Ok(StyleSheet::parse_loosy(&parse_source))
      }
    })
    .map_err(StyleSheetError::new_err)?;

  Ok(CompiledStyleSheet {
    source: Source::Css {
      text,
      lossy: !strict,
    },
    stylesheet,
  })
}

/// Compiles structured keyframes without constructing a renderer.
#[pyfunction]
pub(crate) fn compile_keyframes(
  py: Python<'_>,
  keyframes: Bound<'_, PyAny>,
) -> PyResult<CompiledStyleSheet> {
  let wrapped = PyDict::new(py);
  wrapped.set_item("keyframes", keyframes)?;
  CompiledStyleSheet::keyframes(wrapped.into_any())
}

/// Merges compiled stylesheets while retaining their source order for later merges.
#[pyfunction]
pub(crate) fn merge_stylesheets(
  stylesheets: Vec<PyRef<'_, CompiledStyleSheet>>,
) -> PyResult<CompiledStyleSheet> {
  CompiledStyleSheet::merging(&stylesheets)
}

#[derive(Clone)]
#[pyclass(module = "takumi_py._core")]
pub struct CompiledStyleSheet {
  source: Source,
  stylesheet: StyleSheet,
}

/// What a compiled stylesheet came from, which decides how several of them merge.
#[derive(Clone)]
enum Source {
  Css { text: String, lossy: bool },
  Keyframes(Vec<KeyframesRule>),
  Composite(Vec<Source>),
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

  /// Combines sources in input order. Composite sources are flattened so repeated
  /// merges keep the same cascade order without reconstructing CSS text.
  fn merging(stylesheets: &[PyRef<'_, CompiledStyleSheet>]) -> PyResult<Self> {
    match stylesheets {
      [] => Ok(Self {
        source: Source::Composite(Vec::new()),
        stylesheet: StyleSheet::default(),
      }),
      [stylesheet] => Ok((**stylesheet).clone()),
      _ => {
        let mut sources = Vec::new();
        for stylesheet in stylesheets {
          stylesheet.source.append_to(&mut sources);
        }
        let stylesheet = stylesheet_from_sources(&sources)?;
        Ok(Self {
          source: Source::Composite(sources),
          stylesheet,
        })
      }
    }
  }
}

impl Source {
  fn append_to(&self, sources: &mut Vec<Self>) {
    match self {
      Self::Composite(parts) => {
        for part in parts {
          part.append_to(sources);
        }
      }
      source => sources.push(source.clone()),
    }
  }
}

/// Materializes ordered source fragments into a stylesheet for rendering.
fn stylesheet_from_sources(sources: &[Source]) -> PyResult<StyleSheet> {
  let css: Vec<(&str, bool)> = sources
    .iter()
    .filter_map(|source| match source {
      Source::Css { text, lossy } => Some((text.as_str(), *lossy)),
      Source::Keyframes(_) | Source::Composite(_) => None,
    })
    .collect();
  let keyframes = sources.iter().filter_map(|source| match source {
    Source::Keyframes(rules) => Some(rules),
    Source::Css { .. } | Source::Composite(_) => None,
  });

  let mut merged = match css.as_slice() {
    [] => StyleSheet::default(),
    [(text, true)] => StyleSheet::parse_loosy(text),
    [(text, false)] => {
      StyleSheet::parse(text).map_err(|error| StyleSheetError::new_err(error.to_string()))?
    }
    _ if css.iter().any(|(_, lossy)| *lossy) => {
      StyleSheet::parse_owned_list_loosy(css.iter().map(|(text, _)| (*text).to_owned()).collect())
    }
    _ => StyleSheet::parse_list(css.iter().map(|(text, _)| *text).collect::<Vec<_>>())
      .map_err(|error| StyleSheetError::new_err(error.to_string()))?,
  };

  for rules in keyframes {
    merged.extend_keyframes(rules.clone());
  }
  Ok(merged)
}

/// Merges compiled stylesheets in order for rendering.
pub(crate) fn merge(stylesheets: &[PyRef<'_, CompiledStyleSheet>]) -> PyResult<StyleSheet> {
  match stylesheets {
    [stylesheet] => Ok(stylesheet.stylesheet.clone()),
    _ => Ok(CompiledStyleSheet::merging(stylesheets)?.stylesheet),
  }
}
