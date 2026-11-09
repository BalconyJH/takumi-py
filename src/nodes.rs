//! Compiled node trees, decoded from Python mappings or parsed from HTML.

use std::sync::Arc;

use pyo3::{Bound, PyAny, PyResult, Python, exceptions::PyValueError, prelude::*};
use takumi::{
  from_html,
  prelude::{DEFAULT_MAX_DEPTH, FromHtmlOptions, Node, NodeKind, StylePresets},
};

use crate::{
  errors::{HtmlParseError, NodeDecodeError},
  pyvalue, stack,
};

const DEEP_HTML_MARKER_COUNT: usize = stack::DEEP_NODE_DEPTH;

#[pyclass(module = "takumi_py._core")]
pub struct CompiledNode {
  pub(crate) node: Arc<Node>,
  pub(crate) deep: bool,
}

#[pymethods]
impl CompiledNode {
  pub fn resource_urls(&self, py: Python<'_>) -> PyResult<Vec<String>> {
    let node = Arc::clone(&self.node);
    let deep = self.deep;
    py.detach(move || {
      stack::run(deep, move || -> Vec<String> {
        node.image_urls().map(str::to_owned).collect()
      })
    })
    .map_err(NodeDecodeError::new_err)
  }
}

impl CompiledNode {
  /// Decodes a Python node mapping with Takumi's serde node format.
  pub(crate) fn from_mapping(node: Bound<'_, PyAny>) -> PyResult<Self> {
    let max_depth = DEFAULT_MAX_DEPTH.saturating_mul(2).saturating_add(32);
    let node = pyvalue::from_pyobject(&node, max_depth)
      .map_err(|error| NodeDecodeError::new_err(error.to_string()))?;
    Self::from_native(node).map_err(NodeDecodeError::new_err)
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
      .detach(move || {
        let deep = source.bytes().filter(|byte| *byte == b'<').count() >= DEEP_HTML_MARKER_COUNT
          || stack::nested_css(&source);
        stack::run(deep, move || {
          from_html(&source, options).map_err(|error| error.to_string())
        })
      })
      .map_err(HtmlParseError::new_err)?
      .map_err(HtmlParseError::new_err)?;
    Self::from_native(node).map_err(HtmlParseError::new_err)
  }

  pub(crate) fn from_native(node: Node) -> Result<Self, String> {
    let depth = node_depth(&node);
    if depth > DEFAULT_MAX_DEPTH {
      return Err(format!("nodes nest deeper than {DEFAULT_MAX_DEPTH} levels"));
    }

    Ok(Self {
      node: Arc::new(node),
      deep: depth >= stack::DEEP_NODE_DEPTH,
    })
  }
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
  if max_depth > DEFAULT_MAX_DEPTH {
    return Err(PyValueError::new_err(format!(
      "max_depth cannot exceed {DEFAULT_MAX_DEPTH}"
    )));
  }

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

fn node_depth(root: &Node) -> usize {
  let mut deepest = 1;
  let mut pending = vec![(root, 1)];

  while let Some((node, depth)) = pending.pop() {
    deepest = deepest.max(depth);
    if let NodeKind::Container { children } = &node.kind {
      pending.extend(children.iter().map(|child| (child, depth + 1)));
    }
  }

  deepest
}
