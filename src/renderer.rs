//! `NativeRenderer`, the extension's entry point. Its methods read and validate their
//! inputs while holding the GIL, then run the pipeline without it.

use std::{
  collections::HashMap,
  sync::{Arc, RwLock, RwLockWriteGuard},
};

use pyo3::{Bound, Py, PyAny, PyRef, PyResult, Python, prelude::*, types::PyBytes};
use takumi::prelude::{Fonts, Node};
use takumi_core::resources::image::ResourceCache;

use crate::{
  encode::{self, AnimationEncoder, ImageEncoding},
  errors::RenderError,
  fonts::{self, FontInput},
  images::{ImageInput, ImageMap},
  measure::measured_node_to_py,
  nodes::CompiledNode,
  pipeline::Resources,
  settings::RenderSettings,
  stylesheets::{self, CompiledStyleSheet},
  validate,
};

type Scenes<'py> = Vec<(PyRef<'py, CompiledNode>, u32)>;

#[pyclass(module = "takumi_py._core")]
pub struct NativeRenderer {
  resources: Resources,
  load_default_fonts: bool,
}

#[pymethods]
impl NativeRenderer {
  #[new]
  #[pyo3(signature = (*, load_default_fonts=true, fonts=None, persistent_images=None, cache_max_bytes=None))]
  pub fn new(
    load_default_fonts: bool,
    fonts: Option<Vec<Bound<'_, PyAny>>>,
    persistent_images: Option<Vec<Bound<'_, PyAny>>>,
    cache_max_bytes: Option<u64>,
  ) -> PyResult<Self> {
    let fonts = fonts
      .unwrap_or_default()
      .iter()
      .map(FontInput::from_py)
      .collect::<PyResult<Vec<_>>>()?;
    let persistent_images = persistent_images
      .unwrap_or_default()
      .iter()
      .map(ImageInput::from_py)
      .collect::<PyResult<Vec<_>>>()?;

    let mut font_store = fonts::initial_fonts(load_default_fonts)?;
    for font in fonts {
      drop(font.register(&mut font_store)?);
    }

    let resource_cache = cache_max_bytes.map_or_else(ResourceCache::default, ResourceCache::new);
    let mut images = HashMap::new();
    for image in persistent_images {
      let (src, image) = image.decode(&resource_cache)?;
      images.insert(src, image);
    }

    Ok(Self {
      resources: Resources {
        fonts: Arc::new(RwLock::new(font_store)),
        resource_cache,
        persistent_images: Arc::new(RwLock::new(images)),
      },
      load_default_fonts,
    })
  }

  pub fn compile_node(&self, node: Bound<'_, PyAny>) -> PyResult<CompiledNode> {
    CompiledNode::from_mapping(node)
  }

  #[pyo3(signature = (html, *, presets="chromium", tailwind_property=None, max_depth=None))]
  pub fn compile_html(
    &self,
    py: Python<'_>,
    html: &str,
    presets: &str,
    tailwind_property: Option<String>,
    max_depth: Option<usize>,
  ) -> PyResult<CompiledNode> {
    CompiledNode::from_html(py, html, presets, tailwind_property, max_depth)
  }

  pub fn compile_stylesheet(&self, css: &str) -> PyResult<CompiledStyleSheet> {
    CompiledStyleSheet::strict(css)
  }

  pub fn compile_stylesheet_lossy(&self, css: &str) -> CompiledStyleSheet {
    CompiledStyleSheet::lossy(css)
  }

  pub fn compile_keyframes(&self, keyframes: Bound<'_, PyAny>) -> PyResult<CompiledStyleSheet> {
    CompiledStyleSheet::keyframes(keyframes)
  }

  pub fn register_font(&self, font: Bound<'_, PyAny>) -> PyResult<Vec<String>> {
    let font = FontInput::from_py(&font)?;
    let mut fonts = self.write_fonts()?;
    font.register(&mut fonts)
  }

  pub fn register_fonts(&self, fonts: Vec<Bound<'_, PyAny>>) -> PyResult<Vec<String>> {
    let fonts = fonts
      .iter()
      .map(FontInput::from_py)
      .collect::<PyResult<Vec<_>>>()?;
    let mut font_store = self.write_fonts()?;
    let mut registered = Vec::new();
    for font in fonts {
      registered.extend(font.register(&mut font_store)?);
    }
    Ok(registered)
  }

  pub fn unregister_font(&self, family: &str) -> PyResult<bool> {
    Ok(self.write_fonts()?.unregister_family(family))
  }

  pub fn clear_fonts(&self) -> PyResult<()> {
    let font_store = fonts::initial_fonts(self.load_default_fonts)?;
    *self.write_fonts()? = font_store;
    Ok(())
  }

  pub fn put_persistent_image(&self, resource: Bound<'_, PyAny>) -> PyResult<()> {
    let (src, image) = ImageInput::from_py(&resource)?.decode(&self.resources.resource_cache)?;
    self.write_persistent_images()?.insert(src, image);
    Ok(())
  }

  pub fn clear_image_store(&self) -> PyResult<()> {
    self.write_persistent_images()?.clear();
    Ok(())
  }

  pub fn render_compiled(
    &self,
    py: Python<'_>,
    node: PyRef<'_, CompiledNode>,
    stylesheets: Vec<PyRef<'_, CompiledStyleSheet>>,
    settings: Bound<'_, PyAny>,
    encoding: Bound<'_, PyAny>,
  ) -> PyResult<Py<PyBytes>> {
    let encoding = ImageEncoding::from_py(&encoding)?;
    let settings = RenderSettings::from_py(&settings)?;
    let stylesheet = stylesheets::merge(&stylesheets)?;
    let node = node.node.clone();
    let resources = self.resources.clone();

    let output = py.detach(move || resources.render(node, stylesheet, settings, encoding))?;
    Ok(PyBytes::new(py, &output).unbind())
  }

  pub fn measure_compiled(
    &self,
    py: Python<'_>,
    node: PyRef<'_, CompiledNode>,
    stylesheets: Vec<PyRef<'_, CompiledStyleSheet>>,
    settings: Bound<'_, PyAny>,
  ) -> PyResult<Py<PyAny>> {
    let settings = RenderSettings::from_py(&settings)?;
    let stylesheet = stylesheets::merge(&stylesheets)?;
    let node = node.node.clone();
    let resources = self.resources.clone();

    let measured = py.detach(move || resources.measure(node, stylesheet, settings))?;
    measured_node_to_py(py, &measured)
  }

  pub fn render_svg_compiled(
    &self,
    py: Python<'_>,
    node: PyRef<'_, CompiledNode>,
    stylesheets: Vec<PyRef<'_, CompiledStyleSheet>>,
    settings: Bound<'_, PyAny>,
  ) -> PyResult<String> {
    let settings = RenderSettings::from_py(&settings)?;
    let stylesheet = stylesheets::merge(&stylesheets)?;
    let node = node.node.clone();
    let resources = self.resources.clone();

    py.detach(move || resources.render_svg(node, stylesheet, settings))
  }

  pub fn render_sequence_at_time_compiled(
    &self,
    py: Python<'_>,
    scenes: Scenes<'_>,
    time_ms: i64,
    stylesheets: Vec<PyRef<'_, CompiledStyleSheet>>,
    settings: Bound<'_, PyAny>,
    encoding: Bound<'_, PyAny>,
  ) -> PyResult<Py<PyBytes>> {
    validate::scene_durations(scenes.iter().map(|(_, duration_ms)| *duration_ms))?;
    let time_ms = validate::non_negative("time_ms", time_ms)?;
    let encoding = ImageEncoding::from_py(&encoding)?;
    let settings = RenderSettings::from_py(&settings)?;
    let stylesheet = stylesheets::merge(&stylesheets)?;
    let scenes = clone_scenes(&scenes);
    let resources = self.resources.clone();

    let output = py.detach(move || {
      resources.render_sequence_at_time(scenes, stylesheet, settings, time_ms, encoding)
    })?;
    Ok(PyBytes::new(py, &output).unbind())
  }

  pub fn render_animation_compiled(
    &self,
    py: Python<'_>,
    scenes: Scenes<'_>,
    stylesheets: Vec<PyRef<'_, CompiledStyleSheet>>,
    settings: Bound<'_, PyAny>,
    fps: u32,
    encoding: Bound<'_, PyAny>,
  ) -> PyResult<Py<PyBytes>> {
    validate::scene_durations(scenes.iter().map(|(_, duration_ms)| *duration_ms))?;
    let fps = validate::fps(fps)?;
    let encoder = AnimationEncoder::from_py(&encoding)?;
    let settings = RenderSettings::from_py(&settings)?;
    let fps = encoder.validate_fps(fps)?;
    let stylesheet = stylesheets::merge(&stylesheets)?;
    let scenes = clone_scenes(&scenes);
    let resources = self.resources.clone();

    let output =
      py.detach(move || resources.render_animation(scenes, stylesheet, settings, fps, encoder))?;
    Ok(PyBytes::new(py, &output).unbind())
  }

  pub fn encode_frames(
    &self,
    py: Python<'_>,
    frames: Vec<Bound<'_, PyAny>>,
    encoding: Bound<'_, PyAny>,
  ) -> PyResult<Py<PyBytes>> {
    let encoder = AnimationEncoder::from_py(&encoding)?;
    let frames = frames
      .iter()
      .map(encode::raw_frame)
      .collect::<PyResult<Vec<_>>>()?;

    let output = py.detach(move || encoder.encode(frames))?;
    Ok(PyBytes::new(py, &output).unbind())
  }
}

impl NativeRenderer {
  fn write_fonts(&self) -> PyResult<RwLockWriteGuard<'_, Fonts>> {
    self
      .resources
      .fonts
      .write()
      .map_err(|error| RenderError::new_err(format!("renderer font lock poisoned: {error}")))
  }

  fn write_persistent_images(&self) -> PyResult<RwLockWriteGuard<'_, ImageMap>> {
    self
      .resources
      .persistent_images
      .write()
      .map_err(|error| RenderError::new_err(format!("renderer image lock poisoned: {error}")))
  }
}

fn clone_scenes(scenes: &Scenes<'_>) -> Vec<(Node, u32)> {
  scenes
    .iter()
    .map(|(node, duration_ms)| (node.node.clone(), *duration_ms))
    .collect()
}
