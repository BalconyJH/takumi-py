use std::{
    borrow::Cow,
    collections::HashMap,
    sync::{Arc, RwLock, RwLockReadGuard, RwLockWriteGuard},
};

use pyo3::{
    Bound, Py, PyAny, PyRef, PyResult, Python,
    exceptions::PyValueError,
    prelude::*,
    types::{PyBytes, PyDict, PyList},
};
use serde::Deserialize;
use takumi::{
    from_html, measure,
    prelude::{
        AnimatedGifOptions, AnimatedPngOptions, AnimatedWebpOptions, AnimationFrame, Bitmap,
        DEFAULT_MAX_DEPTH, FontFamily, FontOverride, FontResource, FontStyle, Fonts, FromCssStr,
        FromHtmlOptions, GenericFamily, ImageCacheMode, ImageSource, KeyframesRule, Lang,
        MeasuredNode as CoreMeasuredNode, MeasuredTextRun as CoreMeasuredTextRun, Node,
        RenderOptions as CoreRenderOptions, SequentialScene, StylePresets, StyleSheet, SvgOptions,
        Viewport,
    },
    render, render_animation as render_sequence_animation, render_svg, write_animated_gif,
    write_animated_png, write_animated_webp, write_image,
};
use takumi_core::resources::image::ImageCache;

use crate::{
    errors::{
        AnimationError, FontError, HtmlParseError, NodeDecodeError, RenderError, ResourceError,
        StyleSheetError,
    },
    options::{AnimationOutputFormat, DitheringAlgorithm, OutputFormat},
};

type ImageResourceInput = (String, Vec<u8>, String);
type FontResourceInput = (
    Vec<u8>,
    Option<String>,
    Option<f64>,
    Option<String>,
    Option<String>,
    Option<String>,
);
type RawAnimationFrameInput = (Vec<u8>, u32, u32, u32);

#[derive(Deserialize)]
struct KeyframesInput {
    #[serde(deserialize_with = "takumi_core::keyframes::deserialize_keyframes")]
    keyframes: Vec<KeyframesRule>,
}

#[pyclass(module = "takumi_py._core")]
pub struct CompiledNode {
    node: Node,
}

#[pymethods]
impl CompiledNode {
    pub fn resource_urls(&self) -> Vec<String> {
        self.node.image_urls().map(str::to_owned).collect()
    }
}

#[pyclass(module = "takumi_py._core")]
pub struct CompiledStyleSheet {
    css: String,
    stylesheet: StyleSheet,
    keyframes: Vec<KeyframesRule>,
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
    images: Vec<ImageResourceInput>,
    font_families: Option<Vec<String>>,
    lang: Option<String>,
}

impl RenderSettings {
    fn new(input: RenderSettingsInput) -> PyResult<Self> {
        validate_optional_dimension("width", input.width)?;
        validate_optional_dimension("height", input.height)?;

        let font_size = validate_positive_f64("font_size", input.font_size)? as f32;
        let device_pixel_ratio =
            validate_positive_f64("device_pixel_ratio", input.device_pixel_ratio)? as f32;
        let time_ms = validate_non_negative_i64("time_ms", input.time_ms)?;
        let mut images = input.fetched_resources.unwrap_or_default();
        images.extend(input.images.unwrap_or_default());

        Ok(Self {
            width: input.width,
            height: input.height,
            font_size,
            device_pixel_ratio,
            draw_debug_border: input.draw_debug_border,
            time_ms,
            dithering: DitheringAlgorithm::parse(input.dithering)?,
            images,
            font_families: input.font_families,
            lang: input.lang,
        })
    }

    fn viewport(&self) -> Viewport {
        Viewport::new((self.width, self.height))
            .with_font_size(self.font_size)
            .with_device_pixel_ratio(self.device_pixel_ratio)
    }

    fn svg_viewport(&self) -> Viewport {
        Viewport::new((self.width, self.height)).with_font_size(self.font_size)
    }

    fn lang(&self) -> Option<Lang> {
        self.lang.as_deref().and_then(|lang| Lang::parse(lang).ok())
    }

    fn font_family(&self) -> Option<FontFamily> {
        self.font_families.clone().map(FontFamily::from_names)
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
    images: Option<Vec<ImageResourceInput>>,
    font_families: Option<Vec<String>>,
    lang: Option<String>,
}

#[pyclass(module = "takumi_py._core")]
pub struct NativeRenderer {
    fonts: Arc<RwLock<Fonts>>,
    image_cache: Arc<ImageCache>,
    legacy_images: Arc<RwLock<HashMap<Arc<str>, ImageSource>>>,
}

#[pymethods]
impl NativeRenderer {
    #[new]
    #[pyo3(signature = (*, load_default_fonts=true, fonts=None, persistent_images=None))]
    pub fn new(
        load_default_fonts: bool,
        fonts: Option<Vec<FontResourceInput>>,
        persistent_images: Option<Vec<ImageResourceInput>>,
    ) -> PyResult<Self> {
        let mut font_store = Fonts::default();

        if load_default_fonts {
            load_default_font(&mut font_store)?;
        }

        for font in fonts.unwrap_or_default() {
            drop(register_font_input(&mut font_store, font)?);
        }

        let image_cache = Arc::new(ImageCache::default());
        let mut legacy_images = HashMap::new();
        for (src, data, cache) in persistent_images.unwrap_or_default() {
            let image =
                decode_image_resource(&image_cache, &data, parse_image_cache_mode(&cache)?)?;
            legacy_images.insert(Arc::from(src), image);
        }

        Ok(Self {
            fonts: Arc::new(RwLock::new(font_store)),
            image_cache,
            legacy_images: Arc::new(RwLock::new(legacy_images)),
        })
    }

    pub fn compile_node_py(&self, node: Bound<'_, PyAny>) -> PyResult<CompiledNode> {
        let node = serde_pyobject::from_pyobject(node)
            .map_err(|error| NodeDecodeError::new_err(error.to_string()))?;
        Ok(CompiledNode { node })
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
        let source = html.to_owned();
        let options = html_options(presets, tailwind_property, max_depth)?;
        let node = py
            .detach(move || from_html(&source, options).map_err(|error| error.to_string()))
            .map_err(HtmlParseError::new_err)?;
        Ok(CompiledNode { node })
    }

    pub fn compile_stylesheet(&self, css: &str) -> PyResult<CompiledStyleSheet> {
        let stylesheet =
            StyleSheet::parse(css).map_err(|error| StyleSheetError::new_err(error.to_string()))?;

        Ok(CompiledStyleSheet {
            css: css.to_owned(),
            stylesheet,
            keyframes: Vec::new(),
            lossy: false,
        })
    }

    pub fn compile_stylesheet_lossy(&self, css: &str) -> CompiledStyleSheet {
        CompiledStyleSheet {
            css: css.to_owned(),
            stylesheet: StyleSheet::parse_loosy(css),
            keyframes: Vec::new(),
            lossy: true,
        }
    }

    pub fn compile_keyframes(&self, keyframes: Bound<'_, PyAny>) -> PyResult<CompiledStyleSheet> {
        let input: KeyframesInput = serde_pyobject::from_pyobject(keyframes)
            .map_err(|error| StyleSheetError::new_err(error.to_string()))?;

        Ok(CompiledStyleSheet {
            css: String::new(),
            stylesheet: StyleSheet::from(input.keyframes.clone()),
            keyframes: input.keyframes,
            lossy: false,
        })
    }

    pub fn register_font(&self, font: FontResourceInput) -> PyResult<Vec<String>> {
        let mut fonts = self.write_fonts()?;
        register_font_input(&mut fonts, font)
    }

    pub fn register_fonts(&self, fonts: Vec<FontResourceInput>) -> PyResult<Vec<String>> {
        let mut registered = Vec::new();
        let mut font_store = self.write_fonts()?;
        for font in fonts {
            registered.extend(register_font_input(&mut font_store, font)?);
        }
        Ok(registered)
    }

    pub fn load_font(&self, font: FontResourceInput) -> PyResult<()> {
        drop(self.register_font(font)?);
        Ok(())
    }

    pub fn load_fonts(&self, fonts: Vec<FontResourceInput>) -> PyResult<()> {
        drop(self.register_fonts(fonts)?);
        Ok(())
    }

    #[pyo3(signature = (src, data, cache="auto"))]
    pub fn put_persistent_image(&self, src: String, data: Vec<u8>, cache: &str) -> PyResult<()> {
        let image =
            decode_image_resource(&self.image_cache, &data, parse_image_cache_mode(cache)?)?;
        let mut images = self.write_legacy_images()?;
        images.insert(Arc::from(src), image);
        Ok(())
    }

    pub fn clear_image_store(&self) -> PyResult<()> {
        let mut images = self.write_legacy_images()?;
        images.clear();
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
        images=None,
        font_families=None,
        lang=None,
        format="png",
        quality=None,
        lossless=None
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
        images: Option<Vec<ImageResourceInput>>,
        font_families: Option<Vec<String>>,
        lang: Option<String>,
        format: &str,
        quality: Option<u8>,
        lossless: Option<bool>,
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
            images,
            font_families,
            lang,
        })?;
        let node = node.node.clone();
        let stylesheet = merge_stylesheets(stylesheets.unwrap_or_default())?;
        let fonts = Arc::clone(&self.fonts);
        let image_cache = Arc::clone(&self.image_cache);
        let legacy_images = Arc::clone(&self.legacy_images);

        let output = py.detach(move || {
            render_to_vec(
                fonts,
                image_cache,
                legacy_images,
                node,
                stylesheet,
                settings,
                output_format,
                quality,
                lossless,
            )
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
        fetched_resources=None,
        images=None,
        font_families=None,
        lang=None
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
        images: Option<Vec<ImageResourceInput>>,
        font_families: Option<Vec<String>>,
        lang: Option<String>,
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
            images,
            font_families,
            lang,
        })?;
        let node = node.node.clone();
        let stylesheet = merge_stylesheets(stylesheets.unwrap_or_default())?;
        let fonts = Arc::clone(&self.fonts);
        let image_cache = Arc::clone(&self.image_cache);
        let legacy_images = Arc::clone(&self.legacy_images);

        let measured = py.detach(move || {
            measure_to_node(
                fonts,
                image_cache,
                legacy_images,
                node,
                stylesheet,
                settings,
            )
        })?;

        measured_node_to_py(py, &measured)
    }

    #[pyo3(signature = (
        node,
        *,
        stylesheets=None,
        width=1200,
        height=630,
        font_size=16.0,
        time_ms=0,
        fetched_resources=None,
        images=None,
        font_families=None,
        lang=None
    ))]
    pub fn render_svg_compiled(
        &self,
        py: Python<'_>,
        node: PyRef<'_, CompiledNode>,
        stylesheets: Option<Vec<PyRef<'_, CompiledStyleSheet>>>,
        width: Option<u32>,
        height: Option<u32>,
        font_size: f64,
        time_ms: i64,
        fetched_resources: Option<Vec<ImageResourceInput>>,
        images: Option<Vec<ImageResourceInput>>,
        font_families: Option<Vec<String>>,
        lang: Option<String>,
    ) -> PyResult<String> {
        let settings = RenderSettings::new(RenderSettingsInput {
            width,
            height,
            font_size,
            device_pixel_ratio: 1.0,
            draw_debug_border: false,
            time_ms,
            dithering: "none",
            fetched_resources,
            images,
            font_families,
            lang,
        })?;
        let node = node.node.clone();
        let stylesheet = merge_stylesheets(stylesheets.unwrap_or_default())?;
        let fonts = Arc::clone(&self.fonts);
        let image_cache = Arc::clone(&self.image_cache);
        let legacy_images = Arc::clone(&self.legacy_images);

        py.detach(move || {
            render_svg_to_string(
                fonts,
                image_cache,
                legacy_images,
                node,
                stylesheet,
                settings,
            )
        })
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
        images=None,
        font_families=None,
        lang=None,
        format="png",
        quality=None,
        lossless=None
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
        images: Option<Vec<ImageResourceInput>>,
        font_families: Option<Vec<String>>,
        lang: Option<String>,
        format: &str,
        quality: Option<u8>,
        lossless: Option<bool>,
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
            images,
            font_families,
            lang,
        })?;
        let scenes = clone_scene_nodes(scenes);
        let stylesheet = merge_stylesheets(stylesheets.unwrap_or_default())?;
        let fonts = Arc::clone(&self.fonts);
        let image_cache = Arc::clone(&self.image_cache);
        let legacy_images = Arc::clone(&self.legacy_images);

        let output = py.detach(move || {
            render_sequence_at_time_to_vec(
                fonts,
                image_cache,
                legacy_images,
                scenes,
                stylesheet,
                settings,
                sequence_time_ms,
                output_format,
                quality,
                lossless,
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
        images=None,
        font_families=None,
        lang=None,
        fps=30,
        format="webp",
        quality=None,
        lossless=None,
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
        images: Option<Vec<ImageResourceInput>>,
        font_families: Option<Vec<String>>,
        lang: Option<String>,
        fps: u32,
        format: &str,
        quality: Option<u8>,
        lossless: Option<bool>,
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
            images,
            font_families,
            lang,
        })?;
        let encoder_settings = AnimationEncoderSettings {
            format: animation_format,
            quality,
            lossless,
            loop_count,
            webp_blend,
            webp_dispose,
            webp_speed,
        };
        let scenes = clone_scene_nodes(scenes);
        let stylesheet = merge_stylesheets(stylesheets.unwrap_or_default())?;
        let fonts = Arc::clone(&self.fonts);
        let image_cache = Arc::clone(&self.image_cache);
        let legacy_images = Arc::clone(&self.legacy_images);

        let output = py.detach(move || {
            render_animation_to_vec(
                fonts,
                image_cache,
                legacy_images,
                scenes,
                stylesheet,
                settings,
                fps,
                encoder_settings,
            )
        })?;

        Ok(PyBytes::new(py, &output).unbind())
    }

    #[pyo3(signature = (
        frames,
        *,
        format="webp",
        quality=None,
        lossless=None,
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
        lossless: Option<bool>,
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
            lossless,
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
    fn write_fonts(&self) -> PyResult<RwLockWriteGuard<'_, Fonts>> {
        write_lock(&self.fonts, "renderer font lock poisoned")
    }

    fn write_legacy_images(
        &self,
    ) -> PyResult<RwLockWriteGuard<'_, HashMap<Arc<str>, ImageSource>>> {
        write_lock(&self.legacy_images, "renderer image lock poisoned")
    }
}

#[derive(Clone, Copy)]
struct AnimationEncoderSettings {
    format: AnimationOutputFormat,
    quality: Option<u8>,
    lossless: Option<bool>,
    loop_count: Option<u16>,
    webp_blend: bool,
    webp_dispose: bool,
    webp_speed: Option<u8>,
}

fn read_lock<'a, T>(lock: &'a RwLock<T>, message: &str) -> PyResult<RwLockReadGuard<'a, T>> {
    lock.read()
        .map_err(|error| RenderError::new_err(format!("{message}: {error}")))
}

fn write_lock<'a, T>(lock: &'a RwLock<T>, message: &str) -> PyResult<RwLockWriteGuard<'a, T>> {
    lock.write()
        .map_err(|error| RenderError::new_err(format!("{message}: {error}")))
}

fn load_default_font(fonts: &mut Fonts) -> PyResult<()> {
    const MANROPE: &[u8] =
        include_bytes!("../takumilib/assets/fonts/manrope/manrope-latin-wght-normal.woff2");

    drop(register_font_resource(fonts, FontResource::new(MANROPE))?);
    Ok(())
}

fn register_font_input(fonts: &mut Fonts, input: FontResourceInput) -> PyResult<Vec<String>> {
    let (data, name, weight, style, subset_of, generic_family) = input;
    let style = match style.as_deref() {
        Some(style) => Some(
            FontStyle::from_css_str(style)
                .map_err(|_| FontError::new_err(format!("unsupported font style {style:?}")))?,
        ),
        None => None,
    };
    let mut resource = FontResource::new(data).override_info(FontOverride {
        family_name: name.map(Arc::from),
        width: None,
        style,
        weight: weight.map(|weight| weight as f32),
        axes: Vec::new(),
    });

    if let Some(generic_family) = generic_family {
        resource = resource.generic_family(parse_generic_family(&generic_family)?);
    }

    if let Some(logical) = subset_of {
        resource = resource.subset_of(logical);
    }

    register_font_resource(fonts, resource)
}

fn register_font_resource(fonts: &mut Fonts, font: FontResource<'_>) -> PyResult<Vec<String>> {
    let families = fonts
        .register(font)
        .map_err(|error| FontError::new_err(format!("failed to register font: {error}")))?;
    Ok(families.into_iter().map(|family| family.name).collect())
}

fn parse_generic_family(value: &str) -> PyResult<GenericFamily> {
    match value {
        "serif" => Ok(GenericFamily::SERIF),
        "sans-serif" => Ok(GenericFamily::SANS_SERIF),
        "monospace" => Ok(GenericFamily::MONOSPACE),
        "cursive" => Ok(GenericFamily::CURSIVE),
        "fantasy" => Ok(GenericFamily::FANTASY),
        "system-ui" => Ok(GenericFamily::SYSTEM_UI),
        "ui-serif" => Ok(GenericFamily::UI_SERIF),
        "ui-sans-serif" => Ok(GenericFamily::UI_SANS_SERIF),
        "ui-monospace" => Ok(GenericFamily::UI_MONOSPACE),
        "ui-rounded" => Ok(GenericFamily::UI_ROUNDED),
        "emoji" => Ok(GenericFamily::EMOJI),
        "math" => Ok(GenericFamily::MATH),
        "fangsong" => Ok(GenericFamily::FANG_SONG),
        other => Err(FontError::new_err(format!(
            "unsupported generic font family {other:?}"
        ))),
    }
}

fn parse_image_cache_mode(value: &str) -> PyResult<ImageCacheMode> {
    match value {
        "auto" => Ok(ImageCacheMode::Auto),
        "none" => Ok(ImageCacheMode::None),
        other => Err(PyValueError::new_err(format!(
            "unsupported image cache mode {other:?}"
        ))),
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

    if let Some(tailwind_property) = tailwind_property {
        Ok(FromHtmlOptions::builder()
            .presets(presets)
            .tailwind_property(tailwind_property)
            .max_depth(max_depth)
            .build())
    } else {
        Ok(FromHtmlOptions::builder()
            .presets(presets)
            .max_depth(max_depth)
            .build())
    }
}

fn decode_image_resource(
    image_cache: &ImageCache,
    data: &[u8],
    mode: ImageCacheMode,
) -> PyResult<ImageSource> {
    image_cache.get_or_decode(data, mode).map_err(|error| {
        ResourceError::new_err(format!("failed to decode image resource: {error}"))
    })
}

fn decode_render_images(
    image_cache: &ImageCache,
    legacy_images: &RwLock<HashMap<Arc<str>, ImageSource>>,
    resources: Vec<ImageResourceInput>,
) -> PyResult<HashMap<Arc<str>, ImageSource>> {
    let mut images = read_lock(legacy_images, "renderer image lock poisoned")?.clone();

    for (src, data, cache) in resources {
        let image = decode_image_resource(image_cache, &data, parse_image_cache_mode(&cache)?)?;
        images.insert(Arc::from(src), image);
    }

    Ok(images)
}

fn merge_stylesheets(stylesheets: Vec<PyRef<'_, CompiledStyleSheet>>) -> PyResult<StyleSheet> {
    let (css_stylesheets, structured_stylesheets): (Vec<_>, Vec<_>) = stylesheets
        .into_iter()
        .partition(|stylesheet| !stylesheet.css.is_empty());

    let mut stylesheet = if css_stylesheets.is_empty() {
        StyleSheet::default()
    } else if css_stylesheets.len() == 1 && structured_stylesheets.is_empty() {
        return Ok(css_stylesheets[0].stylesheet.clone());
    } else if css_stylesheets.iter().any(|stylesheet| stylesheet.lossy) {
        let css = css_stylesheets
            .iter()
            .map(|stylesheet| stylesheet.css.clone())
            .collect::<Vec<_>>();
        StyleSheet::parse_owned_list_loosy(css)
    } else {
        let css = css_stylesheets
            .iter()
            .map(|stylesheet| stylesheet.css.as_str())
            .collect::<Vec<_>>();
        StyleSheet::parse_list(css).map_err(|error| StyleSheetError::new_err(error.to_string()))?
    };

    for structured in structured_stylesheets {
        stylesheet.extend_keyframes(structured.keyframes.clone());
    }

    Ok(stylesheet)
}

fn render_to_vec(
    fonts: Arc<RwLock<Fonts>>,
    image_cache: Arc<ImageCache>,
    legacy_images: Arc<RwLock<HashMap<Arc<str>, ImageSource>>>,
    node: Node,
    stylesheet: StyleSheet,
    settings: RenderSettings,
    format: OutputFormat,
    quality: Option<u8>,
    lossless: Option<bool>,
) -> PyResult<Vec<u8>> {
    let image = render_to_bitmap(
        fonts,
        image_cache,
        legacy_images,
        node,
        stylesheet,
        settings,
    )?;
    encode_static_image(image, format, quality, lossless)
}

fn render_to_bitmap(
    fonts: Arc<RwLock<Fonts>>,
    image_cache: Arc<ImageCache>,
    legacy_images: Arc<RwLock<HashMap<Arc<str>, ImageSource>>>,
    node: Node,
    stylesheet: StyleSheet,
    settings: RenderSettings,
) -> PyResult<Bitmap> {
    let images = decode_render_images(&image_cache, &legacy_images, settings.images.clone())?;
    let fonts = read_lock(&fonts, "renderer font lock poisoned")?;
    let lang = settings.lang();
    let font_family = settings.font_family();

    render(
        CoreRenderOptions::builder()
            .viewport(settings.viewport())
            .draw_debug_border(settings.draw_debug_border)
            .images(images)
            .stylesheet(stylesheet)
            .time_ms(settings.time_ms)
            .dithering(settings.dithering.into())
            .node(node)
            .fonts(&fonts)
            .font_families(font_family)
            .lang(lang)
            .build(),
    )
    .map_err(|error| RenderError::new_err(error.to_string()))
}

fn render_svg_to_string(
    fonts: Arc<RwLock<Fonts>>,
    image_cache: Arc<ImageCache>,
    legacy_images: Arc<RwLock<HashMap<Arc<str>, ImageSource>>>,
    node: Node,
    stylesheet: StyleSheet,
    settings: RenderSettings,
) -> PyResult<String> {
    let images = decode_render_images(&image_cache, &legacy_images, settings.images.clone())?;
    let fonts = read_lock(&fonts, "renderer font lock poisoned")?;
    let lang = settings.lang();
    let font_family = settings.font_family();

    render_svg(
        SvgOptions::builder()
            .viewport(settings.svg_viewport())
            .images(images)
            .stylesheet(stylesheet)
            .time_ms(settings.time_ms)
            .node(node)
            .fonts(&fonts)
            .font_families(font_family)
            .lang(lang)
            .build(),
    )
    .map_err(|error| RenderError::new_err(error.to_string()))
}

fn measure_to_node(
    fonts: Arc<RwLock<Fonts>>,
    image_cache: Arc<ImageCache>,
    legacy_images: Arc<RwLock<HashMap<Arc<str>, ImageSource>>>,
    node: Node,
    stylesheet: StyleSheet,
    settings: RenderSettings,
) -> PyResult<CoreMeasuredNode> {
    let images = decode_render_images(&image_cache, &legacy_images, settings.images.clone())?;
    let fonts = read_lock(&fonts, "renderer font lock poisoned")?;
    let lang = settings.lang();
    let font_family = settings.font_family();

    measure(
        CoreRenderOptions::builder()
            .viewport(settings.viewport())
            .draw_debug_border(settings.draw_debug_border)
            .images(images)
            .stylesheet(stylesheet)
            .time_ms(settings.time_ms)
            .dithering(settings.dithering.into())
            .node(node)
            .fonts(&fonts)
            .font_families(font_family)
            .lang(lang)
            .build(),
    )
    .map_err(|error| RenderError::new_err(error.to_string()))
}

fn render_sequence_at_time_to_vec(
    fonts: Arc<RwLock<Fonts>>,
    image_cache: Arc<ImageCache>,
    legacy_images: Arc<RwLock<HashMap<Arc<str>, ImageSource>>>,
    scenes: Vec<(Node, u32)>,
    stylesheet: StyleSheet,
    mut settings: RenderSettings,
    time_ms: u64,
    format: OutputFormat,
    quality: Option<u8>,
    lossless: Option<bool>,
) -> PyResult<Vec<u8>> {
    let Some((node, local_time_ms)) = select_scene_at_time(scenes, time_ms) else {
        return Err(RenderError::new_err(
            "expected at least one animation scene",
        ));
    };
    settings.time_ms = local_time_ms;

    render_to_vec(
        fonts,
        image_cache,
        legacy_images,
        node,
        stylesheet,
        settings,
        format,
        quality,
        lossless,
    )
}

fn render_animation_to_vec(
    fonts: Arc<RwLock<Fonts>>,
    image_cache: Arc<ImageCache>,
    legacy_images: Arc<RwLock<HashMap<Arc<str>, ImageSource>>>,
    scenes: Vec<(Node, u32)>,
    stylesheet: StyleSheet,
    settings: RenderSettings,
    fps: u32,
    encoder_settings: AnimationEncoderSettings,
) -> PyResult<Vec<u8>> {
    let images = decode_render_images(&image_cache, &legacy_images, settings.images.clone())?;
    let fonts = read_lock(&fonts, "renderer font lock poisoned")?;
    let scenes = build_sequence_scenes(&fonts, scenes, stylesheet, settings, images);
    let frames = render_sequence_animation(&scenes, fps)
        .map_err(|error| RenderError::new_err(error.to_string()))?;

    encode_animation_frames(frames, encoder_settings)
}

fn build_sequence_scenes<'g>(
    fonts: &'g Fonts,
    scenes: Vec<(Node, u32)>,
    stylesheet: StyleSheet,
    settings: RenderSettings,
    images: HashMap<Arc<str>, ImageSource>,
) -> Vec<SequentialScene<'g>> {
    scenes
        .into_iter()
        .map(|(node, duration_ms)| {
            let font_family = settings.font_family();
            SequentialScene::builder()
                .duration_ms(duration_ms)
                .options(
                    CoreRenderOptions::builder()
                        .viewport(settings.viewport())
                        .draw_debug_border(settings.draw_debug_border)
                        .images(images.clone())
                        .stylesheet(stylesheet.clone())
                        .dithering(settings.dithering.into())
                        .node(node)
                        .fonts(fonts)
                        .font_families(font_family)
                        .lang(settings.lang())
                        .build(),
                )
                .build()
        })
        .collect()
}

fn select_scene_at_time(scenes: Vec<(Node, u32)>, time_ms: u64) -> Option<(Node, u64)> {
    if scenes.is_empty() {
        return None;
    }

    let total_duration = scenes
        .iter()
        .map(|(_, duration_ms)| u64::from(*duration_ms))
        .sum::<u64>();
    let clamped_time_ms = time_ms.min(total_duration.saturating_sub(1));
    let mut elapsed_ms = 0_u64;
    let mut last = None;

    for (node, duration_ms) in scenes {
        let next_elapsed_ms = elapsed_ms + u64::from(duration_ms);
        let local_fallback = u64::from(duration_ms.saturating_sub(1));
        if clamped_time_ms < next_elapsed_ms {
            return Some((node, clamped_time_ms - elapsed_ms));
        }
        elapsed_ms = next_elapsed_ms;
        last = Some((node, local_fallback));
    }

    last
}

fn encode_static_image(
    image: Bitmap,
    format: OutputFormat,
    quality: Option<u8>,
    lossless: Option<bool>,
) -> PyResult<Vec<u8>> {
    let Some(image_format) = format.image_format(quality, lossless)? else {
        return Ok(image.into_raw());
    };

    let mut buffer = Vec::new();
    write_image(&image, &mut buffer, image_format)
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
            options.lossless = webp_lossless(settings.quality, settings.lossless)?;
            if let Some(quality) = settings.quality {
                options.quality = quality;
            }
            options.speed = settings.webp_speed;
            write_animated_webp(Cow::Owned(frames), &mut buffer, options)
                .map_err(|error| AnimationError::new_err(error.to_string()))?;
        }
        AnimationOutputFormat::Apng => {
            if settings.lossless.is_some() {
                return Err(PyValueError::new_err(
                    "lossless is only supported when format is 'webp'",
                ));
            }
            let mut options = AnimatedPngOptions::default();
            options.loop_count = settings.loop_count;
            write_animated_png(&frames, &mut buffer, options)
                .map_err(|error| AnimationError::new_err(error.to_string()))?;
        }
        AnimationOutputFormat::Gif => {
            if settings.lossless.is_some() {
                return Err(PyValueError::new_err(
                    "lossless is only supported when format is 'webp'",
                ));
            }
            let mut options = AnimatedGifOptions::default();
            options.loop_count = settings.loop_count;
            write_animated_gif(Cow::Owned(frames), &mut buffer, options)
                .map_err(|error| AnimationError::new_err(error.to_string()))?;
        }
    }
    Ok(buffer)
}

fn webp_lossless(quality: Option<u8>, lossless: Option<bool>) -> PyResult<bool> {
    if lossless == Some(true) && quality.is_some() {
        return Err(PyValueError::new_err(
            "quality cannot be set when lossless WebP is requested",
        ));
    }
    Ok(lossless.unwrap_or(quality.is_none()))
}

fn raw_frames_to_animation_frames(
    frames: Vec<RawAnimationFrameInput>,
) -> PyResult<Vec<AnimationFrame>> {
    frames
        .into_iter()
        .map(|(data, width, height, duration_ms)| {
            validate_dimension("width", width)?;
            validate_dimension("height", height)?;
            let image = Bitmap::from_raw(width, height, data).ok_or_else(|| {
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
