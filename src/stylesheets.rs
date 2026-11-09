//! Compiled stylesheets: CSS text parsed strictly or error-tolerantly, structured
//! keyframe rules, and compositions that preserve every source boundary.

use std::fmt::Write;

use cssparser::{serialize_identifier, serialize_string};
use pyo3::{Bound, PyAny, PyRef, PyResult, prelude::*};
use serde::Deserialize;
use takumi::prelude::{KeyframesRule, StyleDeclaration, StyleSheet, ToCss};

use crate::{
  css_source::{closed_declaration, closed_stylesheet},
  errors::StyleSheetError,
  pyvalue, stack,
};

#[derive(Clone)]
#[pyclass(module = "takumi_py._core")]
pub struct CompiledStyleSheet {
  source: Source,
  stylesheet: StyleSheet,
}

/// The exact source text used to rebuild a stylesheet when sources are composed.
#[derive(Clone)]
enum Source {
  Css { text: String, lossy: bool },
}

#[derive(Deserialize)]
struct KeyframesInput {
  #[serde(deserialize_with = "takumi_core::keyframes::deserialize_keyframes")]
  keyframes: Vec<KeyframesRule>,
}

impl CompiledStyleSheet {
  pub(crate) fn strict(css: &str) -> PyResult<Self> {
    stack::run(stack::nested_css(css), || Self::strict_on_stack(css))
      .map_err(StyleSheetError::new_err)?
  }

  fn strict_on_stack(css: &str) -> PyResult<Self> {
    // Keep diagnostics tied to the source the caller supplied.
    let stylesheet =
      StyleSheet::parse(css).map_err(|error| StyleSheetError::new_err(error.to_string()))?;
    Ok(Self {
      source: Source::Css {
        text: closed_stylesheet(css),
        lossy: false,
      },
      stylesheet,
    })
  }

  pub(crate) fn lossy(css: &str) -> PyResult<Self> {
    stack::run(stack::nested_css(css), || Self::lossy_on_stack(css))
      .map_err(StyleSheetError::new_err)?
  }

  fn lossy_on_stack(css: &str) -> PyResult<Self> {
    Ok(Self {
      source: Source::Css {
        text: closed_stylesheet(css),
        lossy: true,
      },
      stylesheet: StyleSheet::parse_loosy(css),
    })
  }

  /// Compiles a `{"keyframes": ...}` mapping of structured keyframe rules.
  pub(crate) fn keyframes(keyframes: Bound<'_, PyAny>) -> PyResult<Self> {
    let input: KeyframesInput = pyvalue::from_pyobject(&keyframes, 1024)
      .map_err(|error| StyleSheetError::new_err(error.to_string()))?;
    keyframes.py().detach(move || {
      stack::run(true, move || {
        let text = keyframes_css(&input.keyframes)?;
        let stylesheet =
          StyleSheet::parse(&text).map_err(|error| StyleSheetError::new_err(error.to_string()))?;
        Ok(Self {
          stylesheet,
          source: Source::Css { text, lossy: false },
        })
      })
      .map_err(StyleSheetError::new_err)?
    })
  }
}

/// Materializes ordered source fragments into a stylesheet for rendering.
fn stylesheet_from_sources(sources: &[Source]) -> PyResult<StyleSheet> {
  let mut css = String::new();
  let mut lossy = false;
  for Source::Css {
    text,
    lossy: source_lossy,
  } in sources
  {
    css.push_str(text);
    css.push('\n');
    lossy |= source_lossy;
  }

  stack::run(stack::nested_css(&css), move || {
    if lossy {
      Ok(StyleSheet::parse_loosy(&css))
    } else {
      StyleSheet::parse(&css).map_err(|error| StyleSheetError::new_err(error.to_string()))
    }
  })
  .map_err(StyleSheetError::new_err)?
}

/// Serializes structured keyframes as the same CSS source they describe, placing
/// them at their exact position among CSS stylesheets during composition.
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
pub(crate) fn merge(stylesheets: &[PyRef<'_, CompiledStyleSheet>]) -> PyResult<StyleSheet> {
  match stylesheets {
    [stylesheet] => {
      let Source::Css { text, .. } = &stylesheet.source;
      let stylesheet = &stylesheet.stylesheet;
      stack::run(stack::nested_css(text), move || stylesheet.clone())
        .map_err(StyleSheetError::new_err)
    }
    _ => {
      let sources: Vec<_> = stylesheets
        .iter()
        .map(|stylesheet| stylesheet.source.clone())
        .collect();
      stylesheet_from_sources(&sources)
    }
  }
}
