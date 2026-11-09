//! Compiled stylesheets: CSS text parsed strictly or error-tolerantly, structured
//! keyframe rules, and compositions that retain their original cascade source.

use std::{fmt::Write, sync::Arc};

use cssparser::{serialize_identifier, serialize_string};
use pyo3::{Bound, PyAny, PyRef, PyResult, Python, prelude::*, types::PyDict};
use serde::Deserialize;
use takumi::prelude::{DEFAULT_MAX_DEPTH, KeyframesRule, StyleDeclaration, StyleSheet, ToCss};

use crate::{
  css_source::{closed_declaration, closed_stylesheet},
  errors::StyleSheetError,
  pyvalue, stack,
};

/// Compiles CSS without constructing a renderer.
#[pyfunction]
#[pyo3(signature = (css, *, strict=true))]
pub(crate) fn compile_stylesheet(
  py: Python<'_>,
  css: &str,
  strict: bool,
) -> PyResult<CompiledStyleSheet> {
  let css = css.to_owned();
  py.detach(move || CompiledStyleSheet::css(&css, strict))
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
  py: Python<'_>,
  stylesheets: Vec<PyRef<'_, CompiledStyleSheet>>,
) -> PyResult<CompiledStyleSheet> {
  let stylesheets: Vec<_> = stylesheets.iter().map(|sheet| (**sheet).clone()).collect();
  py.detach(move || CompiledStyleSheet::merging(&stylesheets))
}

#[derive(Clone)]
#[pyclass(module = "takumi_py._core")]
pub struct CompiledStyleSheet {
  sources: Arc<[Source]>,
  stylesheet: Arc<StyleSheet>,
}

#[pymethods]
impl CompiledStyleSheet {
  pub fn resource_urls(&self) -> Vec<String> {
    let mut urls: Vec<_> = self.stylesheet.image_urls().map(str::to_owned).collect();
    urls.sort_unstable();
    urls
  }
}

/// What a compiled stylesheet came from, which decides how several of them merge.
#[derive(Clone)]
enum Source {
  Css { text: Arc<str>, lossy: bool },
}

#[derive(Deserialize)]
struct KeyframesInput {
  #[serde(deserialize_with = "takumi_core::keyframes::deserialize_keyframes")]
  keyframes: Vec<KeyframesRule>,
}

impl CompiledStyleSheet {
  fn css(css: &str, strict: bool) -> PyResult<Self> {
    stack::run(stack::nested_css(css), || Self::css_on_stack(css, strict))
      .map_err(StyleSheetError::new_err)?
  }

  fn css_on_stack(css: &str, strict: bool) -> PyResult<Self> {
    // Validate the original source first so strict errors keep their context.
    let stylesheet = if strict {
      StyleSheet::parse(css).map_err(|error| StyleSheetError::new_err(error.to_string()))?
    } else {
      StyleSheet::parse_loosy(css)
    };
    Ok(Self {
      sources: Arc::from([Source::Css {
        text: Arc::from(closed_stylesheet(css)),
        lossy: !strict,
      }]),
      stylesheet: Arc::new(stylesheet),
    })
  }

  /// Compiles a `{"keyframes": ...}` mapping of structured keyframe rules.
  pub(crate) fn keyframes(keyframes: Bound<'_, PyAny>) -> PyResult<Self> {
    let max_depth = DEFAULT_MAX_DEPTH.saturating_mul(2).saturating_add(32);
    let input: KeyframesInput = pyvalue::from_pyobject(&keyframes, max_depth)
      .map_err(|error| StyleSheetError::new_err(error.to_string()))?;
    keyframes.py().detach(move || {
      // Structured declarations can contain recursive CSS values even when the
      // surrounding Python mapping is shallow. Keep serialization and reparse
      // together on the controlled stack, outside the GIL.
      stack::run(true, move || {
        let text = keyframes_css(&input.keyframes)?;
        let stylesheet =
          StyleSheet::parse(&text).map_err(|error| StyleSheetError::new_err(error.to_string()))?;
        Ok(Self {
          stylesheet: Arc::new(stylesheet),
          sources: Arc::from([Source::Css {
            text: Arc::from(text),
            lossy: false,
          }]),
        })
      })
      .map_err(StyleSheetError::new_err)?
    })
  }

  /// Combines sources in input order. Composite sources are flattened so repeated
  /// merges keep the same cascade order without reconstructing CSS text.
  fn merging(stylesheets: &[Self]) -> PyResult<Self> {
    match stylesheets {
      [] => Ok(Self {
        sources: Arc::from([]),
        stylesheet: Arc::default(),
      }),
      [stylesheet] => Ok(stylesheet.clone()),
      _ => {
        let mut sources = Vec::new();
        for stylesheet in stylesheets {
          sources.extend(stylesheet.sources.iter().cloned());
        }
        let stylesheet = stylesheet_from_sources(&sources)?;
        Ok(Self {
          sources: sources.into(),
          stylesheet: Arc::new(stylesheet),
        })
      }
    }
  }
}

/// Materializes ordered source fragments into a stylesheet for rendering.
fn stylesheet_from_sources(sources: &[Source]) -> PyResult<StyleSheet> {
  let mut css = String::new();
  let mut lossy = false;
  for Source::Css { text, lossy: mode } in sources {
    css.push_str(text);
    css.push('\n');
    lossy |= mode;
  }
  stack::run(stack::nested_css(&css), || {
    if lossy {
      Ok(StyleSheet::parse_loosy(&css))
    } else {
      StyleSheet::parse(&css).map_err(|error| StyleSheetError::new_err(error.to_string()))
    }
  })
  .map_err(StyleSheetError::new_err)?
}

/// Put structured keyframes at their exact position among the CSS sources.
/// The upstream declaration serializer preserves shorthand expansion and order.
fn keyframes_css(rules: &[KeyframesRule]) -> PyResult<String> {
  let mut css = String::new();
  let serialization_error = |_| StyleSheetError::new_err("could not serialize keyframes");
  for rule in rules {
    css.push_str("@keyframes ");
    serialize_string(&rule.name, &mut css).map_err(serialization_error)?;
    css.push('{');
    for keyframe in &rule.keyframes {
      if keyframe.offsets.is_empty() {
        continue;
      }
      for (index, offset) in keyframe.offsets.iter().enumerate() {
        if !offset.is_finite() || !(0.0..=1.0).contains(offset) {
          return Err(StyleSheetError::new_err(
            "keyframe offsets must be finite values from 0 through 1",
          ));
        }
        if index > 0 {
          css.push(',');
        }
        write!(css, "{}%", f64::from(*offset) * 100.0).map_err(serialization_error)?;
      }
      css.push('{');
      for declaration in keyframe.declarations.iter() {
        let mut serialized = String::new();
        if let StyleDeclaration::CustomProperty(name, value) = declaration {
          serialize_identifier(name, &mut serialized).map_err(serialization_error)?;
          write!(serialized, ":{value};").map_err(serialization_error)?;
        } else {
          declaration
            .to_css(&mut serialized)
            .map_err(serialization_error)?;
        }
        css.push_str(&closed_declaration(&serialized).map_err(|()| {
          StyleSheetError::new_err("structured keyframe contains an invalid CSS declaration")
        })?);
      }
      css.push('}');
    }
    css.push_str("}\n");
  }
  Ok(css)
}

/// Merges compiled stylesheets in order for rendering.
pub(crate) fn merge(
  py: Python<'_>,
  stylesheets: &[PyRef<'_, CompiledStyleSheet>],
) -> PyResult<Arc<StyleSheet>> {
  match stylesheets {
    [stylesheet] => Ok(Arc::clone(&stylesheet.stylesheet)),
    _ => {
      let stylesheets: Vec<_> = stylesheets.iter().map(|sheet| (**sheet).clone()).collect();
      py.detach(move || CompiledStyleSheet::merging(&stylesheets).map(|sheet| sheet.stylesheet))
    }
  }
}
