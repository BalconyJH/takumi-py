//! Conversion of Takumi's measured layout tree into the mappings the Python layer reads.

use pyo3::{
  Py, PyAny, PyResult, Python,
  types::{PyDict, PyDictMethods, PyList, PyListMethods},
};
use takumi::prelude::{MeasuredNode, MeasuredTextRun};

pub(crate) fn measured_node_to_py(py: Python<'_>, node: &MeasuredNode) -> PyResult<Py<PyAny>> {
  // Build parent mappings first and append descendants with an explicit work
  // stack. A legal 512-node result must not consume 512 native Python frames.
  let (root, children) = measured_node_shell(py, node)?;
  let mut pending = vec![(node, children)];
  while let Some((node, children)) = pending.pop() {
    for child in &node.children {
      let (child_dict, child_children) = measured_node_shell(py, child)?;
      children.append(child_dict)?;
      pending.push((child, child_children));
    }
  }
  Ok(root.into_any().unbind())
}

fn measured_node_shell<'py>(
  py: Python<'py>,
  node: &MeasuredNode,
) -> PyResult<(pyo3::Bound<'py, PyDict>, pyo3::Bound<'py, PyList>)> {
  let dict = PyDict::new(py);
  dict.set_item("width", f64::from(node.width))?;
  dict.set_item("height", f64::from(node.height))?;
  dict.set_item(
    "transform",
    node
      .transform
      .iter()
      .map(|value| f64::from(*value))
      .collect::<Vec<_>>(),
  )?;
  let children = PyList::empty(py);
  dict.set_item("children", &children)?;
  let runs = PyList::empty(py);
  for run in &node.runs {
    runs.append(measured_text_run_to_py(py, run)?)?;
  }
  dict.set_item("runs", runs)?;
  Ok((dict, children))
}

fn measured_text_run_to_py(py: Python<'_>, run: &MeasuredTextRun) -> PyResult<Py<PyAny>> {
  let dict = PyDict::new(py);
  dict.set_item("text", &run.text)?;
  dict.set_item("x", f64::from(run.x))?;
  dict.set_item("y", f64::from(run.y))?;
  dict.set_item("width", f64::from(run.width))?;
  dict.set_item("height", f64::from(run.height))?;
  Ok(dict.into_any().unbind())
}

/// Upstream's result owns its children recursively. Release it iteratively on
/// the caller thread, including when Python mapping construction returned an error.
pub(crate) fn drop_measured_node(node: MeasuredNode) {
  let mut pending = vec![node];
  while let Some(mut node) = pending.pop() {
    pending.append(&mut node.children);
  }
}
