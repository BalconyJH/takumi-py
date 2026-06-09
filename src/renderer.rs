use std::{
    borrow::Cow,
    sync::{Arc, RwLock},
};

use pyo3::{
    Bound, Py, PyAny, PyRef, PyResult, Python, exceptions::PyValueError, prelude::*, types::PyBytes,
};
use takumi::{
    GlobalContext,
    layout::{Viewport, node::Node, style::StyleSheet},
    rendering::{render, write_image},
    resources::font::FontResource,
};

use crate::{
    errors::{NodeDecodeError, RenderError, StyleSheetError},
    options::OutputFormat,
};

#[pyclass(module = "takumi_py._core")]
pub struct CompiledNode {
    node: Node,
}

#[pyclass(module = "takumi_py._core")]
pub struct CompiledStyleSheet {
    css: String,
    stylesheet: StyleSheet,
    lossy: bool,
}

#[pyclass(module = "takumi_py._core")]
pub struct NativeRenderer {
    context: Arc<RwLock<GlobalContext>>,
}

#[pymethods]
impl NativeRenderer {
    #[new]
    pub fn new() -> PyResult<Self> {
        let mut context = GlobalContext::default();
        load_default_fonts(&mut context)?;

        Ok(Self {
            context: Arc::new(RwLock::new(context)),
        })
    }

    pub fn compile_node_py(&self, node: Bound<'_, PyAny>) -> PyResult<CompiledNode> {
        let node = serde_pyobject::from_pyobject(node)
            .map_err(|error| NodeDecodeError::new_err(error.to_string()))?;
        Ok(CompiledNode { node })
    }

    pub fn compile_node_msgpack(&self, packed: &[u8]) -> PyResult<CompiledNode> {
        let node = rmp_serde::from_slice(packed)
            .map_err(|error| NodeDecodeError::new_err(error.to_string()))?;
        Ok(CompiledNode { node })
    }

    pub fn compile_stylesheet(&self, css: &str) -> PyResult<CompiledStyleSheet> {
        let stylesheet =
            StyleSheet::parse(css).map_err(|error| StyleSheetError::new_err(error.to_string()))?;

        Ok(CompiledStyleSheet {
            css: css.to_owned(),
            stylesheet,
            lossy: false,
        })
    }

    pub fn compile_stylesheet_lossy(&self, css: &str) -> CompiledStyleSheet {
        CompiledStyleSheet {
            css: css.to_owned(),
            stylesheet: StyleSheet::parse_loosy(css),
            lossy: true,
        }
    }

    #[pyo3(signature = (node, *, stylesheets=None, width=1200, height=630, format="png", quality=None))]
    pub fn render_compiled(
        &self,
        py: Python<'_>,
        node: PyRef<'_, CompiledNode>,
        stylesheets: Option<Vec<PyRef<'_, CompiledStyleSheet>>>,
        width: u32,
        height: u32,
        format: &str,
        quality: Option<u8>,
    ) -> PyResult<Py<PyBytes>> {
        if width == 0 || height == 0 {
            return Err(PyValueError::new_err(
                "width and height must be greater than zero",
            ));
        }

        if let Some(quality) = quality
            && quality > 100
        {
            return Err(PyValueError::new_err(
                "quality must be an integer in the range 0..=100",
            ));
        }

        let output_format = OutputFormat::parse(format)?;
        let node = node.node.clone();
        let stylesheet = merge_stylesheets(stylesheets.unwrap_or_default())?;
        let context = Arc::clone(&self.context);

        let output = py.detach(move || {
            render_to_vec(
                context,
                node,
                stylesheet,
                width,
                height,
                output_format,
                quality,
            )
        })?;

        Ok(PyBytes::new(py, &output).unbind())
    }
}

fn load_default_fonts(context: &mut GlobalContext) -> PyResult<()> {
    const MANROPE: &[u8] =
        include_bytes!("../takumilib/assets/fonts/manrope/manrope-latin-wght-normal.woff2");

    context
        .font_context
        .load_and_store(FontResource::new(MANROPE))
        .map_err(|error| RenderError::new_err(format!("failed to load default font: {error}")))?;

    Ok(())
}

fn merge_stylesheets(stylesheets: Vec<PyRef<'_, CompiledStyleSheet>>) -> PyResult<StyleSheet> {
    match stylesheets.as_slice() {
        [] => Ok(StyleSheet::default()),
        [stylesheet] => Ok(stylesheet.stylesheet.clone()),
        _ => {
            if stylesheets.iter().any(|stylesheet| stylesheet.lossy) {
                let css = stylesheets
                    .iter()
                    .map(|stylesheet| stylesheet.css.clone())
                    .collect::<Vec<_>>();
                Ok(StyleSheet::parse_owned_list_loosy(css))
            } else {
                let css = stylesheets
                    .iter()
                    .map(|stylesheet| stylesheet.css.as_str())
                    .collect::<Vec<_>>();
                StyleSheet::parse_list(css)
                    .map_err(|error| StyleSheetError::new_err(error.to_string()))
            }
        }
    }
}

fn render_to_vec(
    context: Arc<RwLock<GlobalContext>>,
    node: Node,
    stylesheet: StyleSheet,
    width: u32,
    height: u32,
    format: OutputFormat,
    quality: Option<u8>,
) -> PyResult<Vec<u8>> {
    let context = context
        .read()
        .map_err(|error| RenderError::new_err(format!("renderer lock poisoned: {error}")))?;

    let image = render(
        takumi::rendering::RenderOptions::builder()
            .viewport(Viewport::new((width, height)))
            .stylesheet(stylesheet)
            .node(node)
            .global(&context)
            .build(),
    )
    .map_err(|error| RenderError::new_err(error.to_string()))?;

    let Some(image_format) = format.image_format() else {
        return Ok(image.into_raw());
    };

    let mut buffer = Vec::new();
    write_image(Cow::Owned(image), &mut buffer, image_format, quality)
        .map_err(|error| RenderError::new_err(error.to_string()))?;

    Ok(buffer)
}
