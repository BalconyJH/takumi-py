//! Compiled node trees, decoded from Python mappings or parsed from HTML.

use pyo3::{
  Bound, Py, PyAny, PyResult, Python,
  exceptions::PyValueError,
  prelude::*,
  types::{PyBytes, PyDict, PyList, PyTuple},
};
use takumi::{
  from_html,
  prelude::{DEFAULT_MAX_DEPTH, FromHtmlOptions, Node, StylePresets},
};

use crate::errors::{HtmlParseError, NodeDecodeError};

#[pyclass(module = "takumi_py._core")]
pub struct CompiledNode {
  pub(crate) node: Node,
}

#[pymethods]
impl CompiledNode {
  pub fn resource_urls(&self) -> Vec<String> {
    self.node.image_urls().map(str::to_owned).collect()
  }
}

impl CompiledNode {
  /// Decodes a Python node mapping with Takumi's serde node format.
  pub(crate) fn from_mapping(node: Bound<'_, PyAny>) -> PyResult<Self> {
    let py = node.py();
    let node = to_serde_input(py, node)?;
    let node = serde_pyobject::from_pyobject(node.into_bound(py))
      .map_err(|error| NodeDecodeError::new_err(error.to_string()))?;
    Ok(Self { node })
  }

  /// Parses HTML with Takumi's Rust parser, outside the GIL.
  pub(crate) fn from_html(
    py: Python<'_>,
    html: &str,
    presets: &str,
    tailwind_property: Option<String>,
    max_depth: Option<usize>,
  ) -> PyResult<Self> {
    let source = html.to_owned();
    let options = html_options(presets, tailwind_property, max_depth)?;
    let node = py
      .detach(move || from_html(&source, options).map_err(|error| error.to_string()))
      .map_err(HtmlParseError::new_err)?;
    Ok(Self { node })
  }
}

/// Rewrites the input into the shapes serde-pyobject decodes: tuples and `bytes` become
/// lists, so byte buffers deserialize as `serde_bytes` sequences.
fn to_serde_input(py: Python<'_>, value: Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
  if let Ok(bytes) = value.cast::<PyBytes>() {
    return Ok(
      PyList::new(py, bytes.as_bytes().iter().copied())?
        .into_any()
        .unbind(),
    );
  }

  if let Ok(dict) = value.cast::<PyDict>() {
    let normalized = PyDict::new(py);
    for (key, item) in dict {
      normalized.set_item(key, to_serde_input(py, item)?)?;
    }
    return Ok(normalized.into_any().unbind());
  }

  if let Ok(list) = value.cast::<PyList>() {
    return Ok(to_serde_list(py, list.iter())?.into_any().unbind());
  }

  if let Ok(tuple) = value.cast::<PyTuple>() {
    return Ok(to_serde_list(py, tuple.iter())?.into_any().unbind());
  }

  Ok(value.unbind())
}

fn to_serde_list<'py>(
  py: Python<'py>,
  items: impl Iterator<Item = Bound<'py, PyAny>>,
) -> PyResult<Bound<'py, PyList>> {
  let normalized = PyList::empty(py);
  for item in items {
    normalized.append(to_serde_input(py, item)?)?;
  }
  Ok(normalized)
}

fn html_options(
  presets: &str,
  tailwind_property: Option<String>,
  max_depth: Option<usize>,
) -> PyResult<FromHtmlOptions> {
  let presets = match presets {
    "chromium" => StylePresets::chromium(),
    "none" => StylePresets::empty(),
    other => {
      return Err(PyValueError::new_err(format!(
        "unsupported HTML style presets {other:?}"
      )));
    }
  };
  let max_depth = max_depth.unwrap_or(DEFAULT_MAX_DEPTH);

  Ok(match tailwind_property {
    Some(tailwind_property) => FromHtmlOptions::builder()
      .presets(presets)
      .tailwind_property(tailwind_property)
      .max_depth(max_depth)
      .build(),
    None => FromHtmlOptions::builder()
      .presets(presets)
      .max_depth(max_depth)
      .build(),
  })
}
