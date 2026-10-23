//! The render pipeline behind every native entry point. Each function runs without the
//! GIL: it decodes the call's images, takes the font store, and hands Takumi one set of
//! options built the same way for raster, measurement, SVG, and animation output.

use std::sync::{Arc, RwLock, RwLockReadGuard};

use takumi::{
  measure,
  prelude::{Fonts, MeasuredNode, Node, RenderOptions, SequentialScene, StyleSheet, SvgOptions},
  render, render_svg, write_animation,
};
use takumi_core::resources::image::ResourceCache;

use pyo3::PyResult;

use crate::{
  encode::{AnimationEncoder, ImageEncoding, animation_error},
  errors::RenderError,
  images::{self, ImageInput, ImageMap},
  settings::RenderSettings,
};

/// The renderer state a call needs, shareable with a thread that has released the GIL.
#[derive(Clone)]
pub(crate) struct Resources {
  pub(crate) fonts: Arc<RwLock<Fonts>>,
  pub(crate) resource_cache: ResourceCache,
}

impl Resources {
  pub(crate) fn render(
    &self,
    node: Node,
    stylesheet: StyleSheet,
    mut settings: RenderSettings,
    encoding: ImageEncoding,
  ) -> PyResult<Vec<u8>> {
    let images = self.decode_images(std::mem::take(&mut settings.images))?;
    let fonts = self.fonts()?;
    let options = self.raster_options(
      &fonts,
      images,
      node,
      Arc::new(stylesheet),
      &settings,
      settings.time_ms,
    );
    let image = render(options).map_err(render_error)?;
    encoding.encode(image)
  }

  pub(crate) fn measure(
    &self,
    node: Node,
    stylesheet: StyleSheet,
    mut settings: RenderSettings,
  ) -> PyResult<MeasuredNode> {
    let images = self.decode_images(std::mem::take(&mut settings.images))?;
    let fonts = self.fonts()?;
    let options = self.raster_options(
      &fonts,
      images,
      node,
      Arc::new(stylesheet),
      &settings,
      settings.time_ms,
    );
    measure(options).map_err(render_error)
  }

  pub(crate) fn render_svg(
    &self,
    node: Node,
    stylesheet: StyleSheet,
    mut settings: RenderSettings,
  ) -> PyResult<String> {
    let images = self.decode_images(std::mem::take(&mut settings.images))?;
    let fonts = self.fonts()?;
    render_svg(
      SvgOptions::builder()
        .viewport(settings.svg_viewport())
        .images(images)
        .stylesheet(Arc::new(stylesheet))
        .time_ms(settings.time_ms)
        .node(node)
        .fonts(&fonts)
        .font_families(settings.font_family())
        .lang(settings.lang)
        .build(),
    )
    .map_err(render_error)
  }

  /// Renders the scene active at `time_ms` of a sequence, sampled at its local time.
  pub(crate) fn render_sequence_at_time(
    &self,
    scenes: Vec<(Node, u32)>,
    stylesheet: StyleSheet,
    mut settings: RenderSettings,
    time_ms: u64,
    encoding: ImageEncoding,
  ) -> PyResult<Vec<u8>> {
    let Some((node, local_time_ms)) = scene_at_time(scenes, time_ms) else {
      return Err(RenderError::new_err(
        "expected at least one animation scene",
      ));
    };
    settings.time_ms = local_time_ms;
    self.render(node, stylesheet, settings, encoding)
  }

  /// Renders every frame of a scene sequence at `fps`, streaming each one into the
  /// encoder so only one raw frame is held at a time.
  pub(crate) fn render_animation(
    &self,
    scenes: Vec<(Node, u32)>,
    stylesheet: StyleSheet,
    mut settings: RenderSettings,
    fps: u32,
    encoder: AnimationEncoder,
  ) -> PyResult<Vec<u8>> {
    let images = self.decode_images(std::mem::take(&mut settings.images))?;
    let fonts = self.fonts()?;
    let stylesheet = Arc::new(stylesheet);
    let scenes: Vec<SequentialScene<'_>> = scenes
      .into_iter()
      .map(|(node, duration_ms)| {
        SequentialScene::builder()
          .duration_ms(duration_ms)
          .options(self.raster_options(
            &fonts,
            images.clone(),
            node,
            Arc::clone(&stylesheet),
            &settings,
            0,
          ))
          .build()
      })
      .collect();

    let mut buffer = Vec::new();
    write_animation(&scenes, fps, encoder.format(), &mut buffer).map_err(animation_error)?;
    Ok(buffer)
  }

  fn decode_images(&self, inputs: Vec<ImageInput>) -> PyResult<ImageMap> {
    images::decode_all(&self.resource_cache, inputs)
  }

  fn fonts(&self) -> PyResult<RwLockReadGuard<'_, Fonts>> {
    self
      .fonts
      .read()
      .map_err(|error| RenderError::new_err(format!("renderer font lock poisoned: {error}")))
  }

  fn raster_options<'g>(
    &self,
    fonts: &'g Fonts,
    images: ImageMap,
    node: Node,
    stylesheet: Arc<StyleSheet>,
    settings: &RenderSettings,
    time_ms: u64,
  ) -> RenderOptions<'g> {
    RenderOptions::builder()
      .viewport(settings.viewport())
      .draw_debug_border(settings.draw_debug_border)
      .images(images)
      .resource_cache(self.resource_cache.clone())
      .stylesheet(stylesheet)
      .time_ms(time_ms)
      .dithering(settings.dithering.into())
      .node(node)
      .fonts(fonts)
      .font_families(settings.font_family())
      .lang(settings.lang)
      .build()
  }
}

/// The scene active at `time_ms` and the time within it. Past the end, the last scene is
/// held at its final millisecond.
fn scene_at_time(scenes: Vec<(Node, u32)>, time_ms: u64) -> Option<(Node, u64)> {
  let total_duration = scenes
    .iter()
    .map(|(_, duration_ms)| u64::from(*duration_ms))
    .sum::<u64>();
  let clamped_time_ms = time_ms.min(total_duration.saturating_sub(1));
  let mut elapsed_ms = 0_u64;
  let mut last = None;

  for (node, duration_ms) in scenes {
    let next_elapsed_ms = elapsed_ms + u64::from(duration_ms);
    if clamped_time_ms < next_elapsed_ms {
      return Some((node, clamped_time_ms - elapsed_ms));
    }
    elapsed_ms = next_elapsed_ms;
    last = Some((node, u64::from(duration_ms.saturating_sub(1))));
  }

  last
}

fn render_error(error: impl ToString) -> pyo3::PyErr {
  RenderError::new_err(error.to_string())
}
