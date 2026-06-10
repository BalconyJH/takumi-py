use std::{
    borrow::Cow,
    collections::HashMap,
    sync::{Arc, RwLock},
};

use image::RgbaImage;
use pyo3::{
    Bound, Py, PyAny, PyRef, PyResult, Python,
    exceptions::PyValueError,
    prelude::*,
    types::{PyBytes, PyDict, PyList},
};
use takumi::{
    GlobalContext,
    layout::{Viewport, node::Node, style::StyleSheet},
    rendering::{
        AnimatedGifOptions, AnimatedPngOptions, AnimatedWebpOptions, AnimationFrame,
        MeasuredNode as CoreMeasuredNode, MeasuredTextRun as CoreMeasuredTextRun, SequentialScene,
        encode_animated_gif, encode_animated_png, encode_animated_webp, measure_layout, render,
        render_sequence_animation, render_sequence_at_time, write_image,
    },
    resources::{font::FontResource, image::ImageSource},
};

use crate::{
    errors::{
        AnimationError, FontError, NodeDecodeError, RenderError, ResourceError, StyleSheetError,
    },
    options::{AnimationOutputFormat, DitheringAlgorithm, OutputFormat},
};

type ImageResourceInput = (String, Vec<u8>);
type RawAnimationFrameInput = (Vec<u8>, u32, u32, u32);

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

#[derive(Clone)]
struct RenderSettings {
    width: Option<u32>,
    height: Option<u32>,
    font_size: f32,
    device_pixel_ratio: f32,
    draw_debug_border: bool,
    time_ms: u64,
    dithering: DitheringAlgorithm,
    fetched_resources: Vec<ImageResourceInput>,
}

impl RenderSettings {
    fn new(input: RenderSettingsInput) -> PyResult<Self> {
        validate_optional_dimension("width", input.width)?;
        validate_optional_dimension("height", input.height)?;

        let font_size = validate_positive_f64("font_size", input.font_size)? as f32;
        let device_pixel_ratio =
            validate_positive_f64("device_pixel_ratio", input.device_pixel_ratio)? as f32;
        let time_ms = validate_non_negative_i64("time_ms", input.time_ms)?;

        Ok(Self {
            width: input.width,
            height: input.height,
            font_size,
            device_pixel_ratio,
            draw_debug_border: input.draw_debug_border,
            time_ms,
            dithering: DitheringAlgorithm::parse(input.dithering)?,
            fetched_resources: input.fetched_resources.unwrap_or_default(),
        })
    }

    fn viewport(&self) -> Viewport {
        Viewport::new((self.width, self.height))
            .with_font_size(self.font_size)
            .with_device_pixel_ratio(self.device_pixel_ratio)
    }
}

struct RenderSettingsInput<'a> {
    width: Option<u32>,
    height: Option<u32>,
    font_size: f64,
    device_pixel_ratio: f64,
    draw_debug_border: bool,
    time_ms: i64,
    dithering: &'a str,
    fetched_resources: Option<Vec<ImageResourceInput>>,
}

#[pyclass(module = "takumi_py._core")]
pub struct NativeRenderer {
    context: Arc<RwLock<GlobalContext>>,
}

#[pymethods]
impl NativeRenderer {
    #[new]
    #[pyo3(signature = (*, load_default_fonts=true, fonts=None, persistent_images=None))]
    pub fn new(
        load_default_fonts: bool,
        fonts: Option<Vec<Vec<u8>>>,
        persistent_images: Option<Vec<ImageResourceInput>>,
    ) -> PyResult<Self> {
        let mut context = GlobalContext::default();

        if load_default_fonts {
            load_default_font(&mut context)?;
        }

        for font in fonts.unwrap_or_default() {
            load_font_bytes(&mut context, font)?;
        }

        for (src, data) in persistent_images.unwrap_or_default() {
            let image = decode_image_resource(&data)?;
            context.persistent_image_store.insert(src, image);
        }

        Ok(Self {
            context: Arc::new(RwLock::new(context)),
        })
    }

    pub fn compile_node_py(&self, node: Bound<'_, PyAny>) -> PyResult<CompiledNode> {
        let node = serde_pyobject::from_pyobject(node)
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

    pub fn load_font(&self, data: Vec<u8>) -> PyResult<()> {
        let mut context = self.write_context()?;
        load_font_bytes(&mut context, data)
    }

    pub fn load_fonts(&self, fonts: Vec<Vec<u8>>) -> PyResult<()> {
        let mut context = self.write_context()?;
        for font in fonts {
            load_font_bytes(&mut context, font)?;
        }
        Ok(())
    }

    pub fn put_persistent_image(&self, src: String, data: Vec<u8>) -> PyResult<()> {
        let image = decode_image_resource(&data)?;
        let context = self.read_context()?;
        context.persistent_image_store.insert(src, image);
        Ok(())
    }

    pub fn clear_image_store(&self) -> PyResult<()> {
        let context = self.read_context()?;
        context.persistent_image_store.clear();
        Ok(())
    }

    #[pyo3(signature = (
        node,
        *,
        stylesheets=None,
        width=1200,
        height=630,
        font_size=16.0,
        device_pixel_ratio=1.0,
        draw_debug_border=false,
        time_ms=0,
        dithering="none",
        fetched_resources=None,
        format="png",
        quality=None
    ))]
    pub fn render_compiled(
        &self,
        py: Python<'_>,
        node: PyRef<'_, CompiledNode>,
        stylesheets: Option<Vec<PyRef<'_, CompiledStyleSheet>>>,
        width: Option<u32>,
        height: Option<u32>,
        font_size: f64,
        device_pixel_ratio: f64,
        draw_debug_border: bool,
        time_ms: i64,
        dithering: &str,
        fetched_resources: Option<Vec<ImageResourceInput>>,
        format: &str,
        quality: Option<u8>,
    ) -> PyResult<Py<PyBytes>> {
        validate_quality(quality)?;

        let output_format = OutputFormat::parse(format)?;
        let settings = RenderSettings::new(RenderSettingsInput {
            width,
            height,
            font_size,
            device_pixel_ratio,
            draw_debug_border,
            time_ms,
            dithering,
            fetched_resources,
        })?;
        let node = node.node.clone();
        let stylesheet = merge_stylesheets(stylesheets.unwrap_or_default())?;
        let context = Arc::clone(&self.context);

        let output = py.detach(move || {
            render_to_vec(context, node, stylesheet, settings, output_format, quality)
        })?;

        Ok(PyBytes::new(py, &output).unbind())
    }

    #[pyo3(signature = (
        node,
        *,
        stylesheets=None,
        width=1200,
        height=630,
        font_size=16.0,
        device_pixel_ratio=1.0,
        draw_debug_border=false,
        time_ms=0,
        dithering="none",
        fetched_resources=None
    ))]
    pub fn measure_compiled(
        &self,
        py: Python<'_>,
        node: PyRef<'_, CompiledNode>,
        stylesheets: Option<Vec<PyRef<'_, CompiledStyleSheet>>>,
        width: Option<u32>,
        height: Option<u32>,
        font_size: f64,
        device_pixel_ratio: f64,
        draw_debug_border: bool,
        time_ms: i64,
        dithering: &str,
        fetched_resources: Option<Vec<ImageResourceInput>>,
    ) -> PyResult<Py<PyAny>> {
        let settings = RenderSettings::new(RenderSettingsInput {
            width,
            height,
            font_size,
            device_pixel_ratio,
            draw_debug_border,
            time_ms,
            dithering,
            fetched_resources,
        })?;
        let node = node.node.clone();
        let stylesheet = merge_stylesheets(stylesheets.unwrap_or_default())?;
        let context = Arc::clone(&self.context);

        let measured = py.detach(move || measure_to_node(context, node, stylesheet, settings))?;

        measured_node_to_py(py, &measured)
    }

    #[pyo3(signature = (
        scenes,
        time_ms,
        *,
        stylesheets=None,
        width=1200,
        height=630,
        font_size=16.0,
        device_pixel_ratio=1.0,
        draw_debug_border=false,
        dithering="none",
        fetched_resources=None,
        format="png",
        quality=None
    ))]
    pub fn render_sequence_at_time_compiled(
        &self,
        py: Python<'_>,
        scenes: Vec<(PyRef<'_, CompiledNode>, u32)>,
        time_ms: i64,
        stylesheets: Option<Vec<PyRef<'_, CompiledStyleSheet>>>,
        width: Option<u32>,
        height: Option<u32>,
        font_size: f64,
        device_pixel_ratio: f64,
        draw_debug_border: bool,
        dithering: &str,
        fetched_resources: Option<Vec<ImageResourceInput>>,
        format: &str,
        quality: Option<u8>,
    ) -> PyResult<Py<PyBytes>> {
        validate_scenes(&scenes)?;
        let sequence_time_ms = validate_non_negative_i64("time_ms", time_ms)?;
        validate_quality(quality)?;

        let output_format = OutputFormat::parse(format)?;
        let settings = RenderSettings::new(RenderSettingsInput {
            width,
            height,
            font_size,
            device_pixel_ratio,
            draw_debug_border,
            time_ms: 0,
            dithering,
            fetched_resources,
        })?;
        let scenes = clone_scene_nodes(scenes);
        let stylesheet = merge_stylesheets(stylesheets.unwrap_or_default())?;
        let context = Arc::clone(&self.context);

        let output = py.detach(move || {
            render_sequence_at_time_to_vec(
                context,
                scenes,
                stylesheet,
                settings,
                sequence_time_ms,
                output_format,
                quality,
            )
        })?;

        Ok(PyBytes::new(py, &output).unbind())
    }

    #[pyo3(signature = (
        scenes,
        *,
        stylesheets=None,
        width=1200,
        height=630,
        font_size=16.0,
        device_pixel_ratio=1.0,
        draw_debug_border=false,
        dithering="none",
        fetched_resources=None,
        fps=30,
        format="webp",
        quality=None,
        loop_count=None,
        webp_blend=true,
        webp_dispose=false,
        webp_speed=None
    ))]
    pub fn render_animation_compiled(
        &self,
        py: Python<'_>,
        scenes: Vec<(PyRef<'_, CompiledNode>, u32)>,
        stylesheets: Option<Vec<PyRef<'_, CompiledStyleSheet>>>,
        width: Option<u32>,
        height: Option<u32>,
        font_size: f64,
        device_pixel_ratio: f64,
        draw_debug_border: bool,
        dithering: &str,
        fetched_resources: Option<Vec<ImageResourceInput>>,
        fps: u32,
        format: &str,
        quality: Option<u8>,
        loop_count: Option<u16>,
        webp_blend: bool,
        webp_dispose: bool,
        webp_speed: Option<u8>,
    ) -> PyResult<Py<PyBytes>> {
        validate_scenes(&scenes)?;
        validate_fps(fps)?;
        validate_quality(quality)?;
        validate_webp_speed(webp_speed)?;

        let animation_format = AnimationOutputFormat::parse(format)?;
        let settings = RenderSettings::new(RenderSettingsInput {
            width,
            height,
            font_size,
            device_pixel_ratio,
            draw_debug_border,
            time_ms: 0,
            dithering,
            fetched_resources,
        })?;
        let encoder_settings = AnimationEncoderSettings {
            format: animation_format,
            quality,
            loop_count,
            webp_blend,
            webp_dispose,
            webp_speed,
        };
        let scenes = clone_scene_nodes(scenes);
        let stylesheet = merge_stylesheets(stylesheets.unwrap_or_default())?;
        let context = Arc::clone(&self.context);

        let output = py.detach(move || {
            render_animation_to_vec(context, scenes, stylesheet, settings, fps, encoder_settings)
        })?;

        Ok(PyBytes::new(py, &output).unbind())
    }

    #[pyo3(signature = (
        frames,
        *,
        format="webp",
        quality=None,
        loop_count=None,
        webp_blend=true,
        webp_dispose=false,
        webp_speed=None
    ))]
    pub fn encode_frames(
        &self,
        py: Python<'_>,
        frames: Vec<RawAnimationFrameInput>,
        format: &str,
        quality: Option<u8>,
        loop_count: Option<u16>,
        webp_blend: bool,
        webp_dispose: bool,
        webp_speed: Option<u8>,
    ) -> PyResult<Py<PyBytes>> {
        validate_quality(quality)?;
        validate_webp_speed(webp_speed)?;

        let encoder_settings = AnimationEncoderSettings {
            format: AnimationOutputFormat::parse(format)?,
            quality,
            loop_count,
            webp_blend,
            webp_dispose,
            webp_speed,
        };

        let output = py.detach(move || {
            let frames = raw_frames_to_animation_frames(frames)?;
            encode_animation_frames(frames, encoder_settings)
        })?;

        Ok(PyBytes::new(py, &output).unbind())
    }
}

impl NativeRenderer {
    fn read_context(&self) -> PyResult<std::sync::RwLockReadGuard<'_, GlobalContext>> {
        self.context
            .read()
            .map_err(|error| RenderError::new_err(format!("renderer lock poisoned: {error}")))
    }

    fn write_context(&self) -> PyResult<std::sync::RwLockWriteGuard<'_, GlobalContext>> {
        self.context
            .write()
            .map_err(|error| RenderError::new_err(format!("renderer lock poisoned: {error}")))
    }
}

#[derive(Clone, Copy)]
struct AnimationEncoderSettings {
    format: AnimationOutputFormat,
    quality: Option<u8>,
    loop_count: Option<u16>,
    webp_blend: bool,
    webp_dispose: bool,
    webp_speed: Option<u8>,
}

fn load_default_font(context: &mut GlobalContext) -> PyResult<()> {
    const MANROPE: &[u8] =
        include_bytes!("../takumilib/assets/fonts/manrope/manrope-latin-wght-normal.woff2");

    load_font_resource(context, FontResource::new(MANROPE))
}

fn load_font_bytes(context: &mut GlobalContext, data: Vec<u8>) -> PyResult<()> {
    load_font_resource(context, FontResource::new(data))
}

fn load_font_resource(context: &mut GlobalContext, font: FontResource<'_>) -> PyResult<()> {
    context
        .font_context
        .load_and_store(font)
        .map_err(|error| FontError::new_err(format!("failed to load font: {error}")))
}

fn decode_image_resource(data: &[u8]) -> PyResult<ImageSource> {
    ImageSource::from_bytes(data).map_err(|error| {
        ResourceError::new_err(format!("failed to decode image resource: {error}"))
    })
}

fn decode_fetched_resources(
    resources: Vec<ImageResourceInput>,
) -> PyResult<HashMap<Arc<str>, ImageSource>> {
    resources
        .into_iter()
        .map(|(src, data)| decode_image_resource(&data).map(|image| (Arc::from(src), image)))
        .collect()
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
    settings: RenderSettings,
    format: OutputFormat,
    quality: Option<u8>,
) -> PyResult<Vec<u8>> {
    let image = render_to_image(context, node, stylesheet, settings)?;
    encode_static_image(image, format, quality)
}

fn render_to_image(
    context: Arc<RwLock<GlobalContext>>,
    node: Node,
    stylesheet: StyleSheet,
    settings: RenderSettings,
) -> PyResult<RgbaImage> {
    let fetched_resources = decode_fetched_resources(settings.fetched_resources.clone())?;
    let context = context
        .read()
        .map_err(|error| RenderError::new_err(format!("renderer lock poisoned: {error}")))?;

    render(
        takumi::rendering::RenderOptions::builder()
            .viewport(settings.viewport())
            .draw_debug_border(settings.draw_debug_border)
            .fetched_resources(fetched_resources)
            .stylesheet(stylesheet)
            .time_ms(settings.time_ms)
            .dithering(settings.dithering.into())
            .node(node)
            .global(&context)
            .build(),
    )
    .map_err(|error| RenderError::new_err(error.to_string()))
}

fn measure_to_node(
    context: Arc<RwLock<GlobalContext>>,
    node: Node,
    stylesheet: StyleSheet,
    settings: RenderSettings,
) -> PyResult<CoreMeasuredNode> {
    let fetched_resources = decode_fetched_resources(settings.fetched_resources.clone())?;
    let context = context
        .read()
        .map_err(|error| RenderError::new_err(format!("renderer lock poisoned: {error}")))?;

    measure_layout(
        takumi::rendering::RenderOptions::builder()
            .viewport(settings.viewport())
            .draw_debug_border(settings.draw_debug_border)
            .fetched_resources(fetched_resources)
            .stylesheet(stylesheet)
            .time_ms(settings.time_ms)
            .dithering(settings.dithering.into())
            .node(node)
            .global(&context)
            .build(),
    )
    .map_err(|error| RenderError::new_err(error.to_string()))
}

fn render_sequence_at_time_to_vec(
    context: Arc<RwLock<GlobalContext>>,
    scenes: Vec<(Node, u32)>,
    stylesheet: StyleSheet,
    settings: RenderSettings,
    time_ms: u64,
    format: OutputFormat,
    quality: Option<u8>,
) -> PyResult<Vec<u8>> {
    let fetched_resources = decode_fetched_resources(settings.fetched_resources.clone())?;
    let context = context
        .read()
        .map_err(|error| RenderError::new_err(format!("renderer lock poisoned: {error}")))?;
    let scenes = build_sequence_scenes(&context, scenes, stylesheet, settings, fetched_resources);
    let image = render_sequence_at_time(&scenes, time_ms)
        .map_err(|error| RenderError::new_err(error.to_string()))?;

    encode_static_image(image, format, quality)
}

fn render_animation_to_vec(
    context: Arc<RwLock<GlobalContext>>,
    scenes: Vec<(Node, u32)>,
    stylesheet: StyleSheet,
    settings: RenderSettings,
    fps: u32,
    encoder_settings: AnimationEncoderSettings,
) -> PyResult<Vec<u8>> {
    let fetched_resources = decode_fetched_resources(settings.fetched_resources.clone())?;
    let context = context
        .read()
        .map_err(|error| RenderError::new_err(format!("renderer lock poisoned: {error}")))?;
    let scenes = build_sequence_scenes(&context, scenes, stylesheet, settings, fetched_resources);
    let frames = render_sequence_animation(&scenes, fps)
        .map_err(|error| RenderError::new_err(error.to_string()))?;

    encode_animation_frames(frames, encoder_settings)
}

fn build_sequence_scenes<'g>(
    context: &'g GlobalContext,
    scenes: Vec<(Node, u32)>,
    stylesheet: StyleSheet,
    settings: RenderSettings,
    fetched_resources: HashMap<Arc<str>, ImageSource>,
) -> Vec<SequentialScene<'g>> {
    scenes
        .into_iter()
        .map(|(node, duration_ms)| {
            SequentialScene::builder()
                .duration_ms(duration_ms)
                .options(
                    takumi::rendering::RenderOptions::builder()
                        .viewport(settings.viewport())
                        .draw_debug_border(settings.draw_debug_border)
                        .fetched_resources(fetched_resources.clone())
                        .stylesheet(stylesheet.clone())
                        .dithering(settings.dithering.into())
                        .node(node)
                        .global(context)
                        .build(),
                )
                .build()
        })
        .collect()
}

fn encode_static_image(
    image: RgbaImage,
    format: OutputFormat,
    quality: Option<u8>,
) -> PyResult<Vec<u8>> {
    let Some(image_format) = format.image_format() else {
        return Ok(image.into_raw());
    };

    let mut buffer = Vec::new();
    write_image(Cow::Owned(image), &mut buffer, image_format, quality)
        .map_err(|error| RenderError::new_err(error.to_string()))?;

    Ok(buffer)
}

fn encode_animation_frames(
    frames: Vec<AnimationFrame>,
    settings: AnimationEncoderSettings,
) -> PyResult<Vec<u8>> {
    let mut buffer = Vec::new();
    match settings.format {
        AnimationOutputFormat::WebP => {
            let mut options = AnimatedWebpOptions::default();
            options.blend = settings.webp_blend;
            options.dispose = settings.webp_dispose;
            options.loop_count = settings.loop_count;
            if let Some(quality) = settings.quality {
                options.quality = quality;
            }
            options.speed = settings.webp_speed;
            encode_animated_webp(Cow::Owned(frames), &mut buffer, options)
                .map_err(|error| AnimationError::new_err(error.to_string()))?;
        }
        AnimationOutputFormat::Apng => {
            let mut options = AnimatedPngOptions::default();
            options.loop_count = settings.loop_count;
            encode_animated_png(&frames, &mut buffer, options)
                .map_err(|error| AnimationError::new_err(error.to_string()))?;
        }
        AnimationOutputFormat::Gif => {
            let mut options = AnimatedGifOptions::default();
            options.loop_count = settings.loop_count;
            encode_animated_gif(Cow::Owned(frames), &mut buffer, options)
                .map_err(|error| AnimationError::new_err(error.to_string()))?;
        }
    }
    Ok(buffer)
}

fn raw_frames_to_animation_frames(
    frames: Vec<RawAnimationFrameInput>,
) -> PyResult<Vec<AnimationFrame>> {
    frames
        .into_iter()
        .map(|(data, width, height, duration_ms)| {
            validate_dimension("width", width)?;
            validate_dimension("height", height)?;
            let image = RgbaImage::from_raw(width, height, data).ok_or_else(|| {
                AnimationError::new_err("raw frame buffer size does not match width * height * 4")
            })?;
            Ok(AnimationFrame::new(image, duration_ms))
        })
        .collect()
}

fn measured_node_to_py(py: Python<'_>, node: &CoreMeasuredNode) -> PyResult<Py<PyAny>> {
    let dict = PyDict::new(py);
    dict.set_item("width", f64::from(node.width))?;
    dict.set_item("height", f64::from(node.height))?;
    dict.set_item(
        "transform",
        node.transform
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

fn measured_text_run_to_py(py: Python<'_>, run: &CoreMeasuredTextRun) -> PyResult<Py<PyAny>> {
    let dict = PyDict::new(py);
    dict.set_item("text", &run.text)?;
    dict.set_item("x", f64::from(run.x))?;
    dict.set_item("y", f64::from(run.y))?;
    dict.set_item("width", f64::from(run.width))?;
    dict.set_item("height", f64::from(run.height))?;
    Ok(dict.into_any().unbind())
}

fn clone_scene_nodes(scenes: Vec<(PyRef<'_, CompiledNode>, u32)>) -> Vec<(Node, u32)> {
    scenes
        .into_iter()
        .map(|(node, duration_ms)| (node.node.clone(), duration_ms))
        .collect()
}

fn validate_scenes(scenes: &[(PyRef<'_, CompiledNode>, u32)]) -> PyResult<()> {
    if scenes.is_empty() {
        return Err(PyValueError::new_err(
            "expected at least one animation scene",
        ));
    }
    Ok(())
}

fn validate_fps(fps: u32) -> PyResult<()> {
    if fps == 0 {
        return Err(PyValueError::new_err("fps must be greater than zero"));
    }
    Ok(())
}

fn validate_quality(quality: Option<u8>) -> PyResult<()> {
    if let Some(quality) = quality
        && quality > 100
    {
        return Err(PyValueError::new_err(
            "quality must be an integer in the range 0..=100",
        ));
    }
    Ok(())
}

fn validate_webp_speed(speed: Option<u8>) -> PyResult<()> {
    if let Some(speed) = speed
        && speed > 6
    {
        return Err(PyValueError::new_err(
            "webp_speed must be an integer in the range 0..=6",
        ));
    }
    Ok(())
}

fn validate_optional_dimension(name: &str, value: Option<u32>) -> PyResult<()> {
    if let Some(value) = value {
        validate_dimension(name, value)?;
    }
    Ok(())
}

fn validate_dimension(name: &str, value: u32) -> PyResult<()> {
    if value == 0 {
        return Err(PyValueError::new_err(format!(
            "{name} must be greater than zero"
        )));
    }
    Ok(())
}

fn validate_positive_f64(name: &str, value: f64) -> PyResult<f64> {
    if !value.is_finite() || value <= 0.0 {
        return Err(PyValueError::new_err(format!(
            "{name} must be a finite number greater than zero"
        )));
    }
    Ok(value)
}

fn validate_non_negative_i64(name: &str, value: i64) -> PyResult<u64> {
    if value < 0 {
        return Err(PyValueError::new_err(format!(
            "{name} must be non-negative"
        )));
    }
    Ok(value as u64)
}
