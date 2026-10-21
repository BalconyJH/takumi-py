//! Conversion of Takumi's measured layout tree into the mappings the Python layer reads.

use pyo3::{
  Py, PyAny, PyResult, Python,
  types::{PyDict, PyDictMethods, PyList, PyListMethods},
};
use takumi::prelude::{MeasuredNode, MeasuredTextRun};

pub(crate) fn measured_node_to_py(py: Python<'_>, node: &MeasuredNode) -> PyResult<Py<PyAny>> {
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
  for child in &node.children {
    children.append(measured_node_to_py(py, child)?)?;
  }
  dict.set_item("children", children)?;
  let runs = PyList::empty(py);
  for run in &node.runs {
    runs.append(measured_text_run_to_py(py, run)?)?;
  }
  dict.set_item("runs", runs)?;
  Ok(dict.into_any().unbind())
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
