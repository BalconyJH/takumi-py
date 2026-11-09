from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
import math
from pathlib import Path
import sys
from typing import Any, TypeGuard, TypeVar, cast
from warnings import warn

from takumi_py import _core
from takumi_py.document import CompiledDocument, Document, compile_document
from takumi_py.html import parse_html
from takumi_py.options import (
    UNSET,
    AnimationEncodeOptions,
    AnimationOutputFormat,
    DitheringAlgorithm,
    FontResourceInput,
    HtmlOptions,
    ImageOutputFormat,
    ImageResourceInput,
    KeyframesInput,
    LayoutOptions,
    RasterOptions,
    RenderOptions,
    UnsetType,
    native_render_settings,
)
from takumi_py.raster import RasterImage
from takumi_py.template import render_template_to_html
from takumi_py.types import (
    AnimationScene,
    CompiledNode,
    CompiledStyleSheet,
    MeasuredNode,
    NodeInput,
    RawAnimationFrame,
    RenderNeeds,
    measured_node_from_mapping,
    validate_node,
)


@dataclass(frozen=True, slots=True)
class CompiledHtml:
    """A compiled HTML node together with its compiled stylesheets.

    The parser extracts ``<style>`` elements in document order and compiles their
    CSS with the error-tolerant HTML parser. The stylesheets travel with the node.

    Attributes:
        node: The compiled root node.
        stylesheets: Compiled stylesheets returned by the parser.
    """

    node: CompiledNode
    stylesheets: tuple[CompiledStyleSheet, ...] = ()


def set_glyph_cache_max_bytes(max_bytes: int) -> None:
    """Set the process-wide glyph cache budget before the first render.

    Args:
        max_bytes: Maximum retained glyph-cache size in bytes. Use ``0`` to
            disable retention.

    The budget only applies to a glyph cache that has not been used yet, so
    later calls do not resize it.

    Raises:
        ValueError: If ``max_bytes`` is negative.
    """
    if max_bytes < 0:
        raise ValueError("max_bytes must be greater than or equal to 0")
    _core.set_glyph_cache_max_bytes(max_bytes)


class Renderer:
    """Compile, measure, and render Takumi nodes, HTML, SVG, and animations."""

    def __init__(
        self,
        *,
        load_default_fonts: bool = True,
        fonts: Sequence[FontResourceInput] | None = None,
        cache_max_bytes: int | None = None,
        font_cache_max_bytes: int | None = None,
    ) -> None:
        """Create a renderer with optional font and cache configuration.

        ``cache_max_bytes`` controls the renderer-local resource cache for decoded
        images, SVG rasters, and related render resources. Pass ``0`` to disable
        retention or ``None`` to use Takumi's default budget.

        ``font_cache_max_bytes`` bounds the decoded fonts that ``cache_font()`` keeps.
        Past it, the least recently used of them are released; fonts registered with
        ``register_font()`` or ``fonts`` are never released for space.

        Args:
            load_default_fonts: Load Takumi's bundled default fonts.
            fonts: Font resources to register during construction.
            cache_max_bytes: Maximum renderer-local resource-cache size in bytes.
            font_cache_max_bytes: Maximum decoded size of cached fonts in bytes, or
                ``None`` for no limit.

        Raises:
            ValueError: If ``cache_max_bytes`` or ``font_cache_max_bytes`` is
                negative.
            TakumiError: If native renderer initialization fails.
        """
        if cache_max_bytes is not None and cache_max_bytes < 0:
            raise ValueError("cache_max_bytes must be greater than or equal to 0")
        if font_cache_max_bytes is not None and font_cache_max_bytes < 0:
            raise ValueError("font_cache_max_bytes must be greater than or equal to 0")
        self._native = _core.NativeRenderer(
            load_default_fonts=load_default_fonts,
            fonts=None if fonts is None else list(fonts),
            cache_max_bytes=cache_max_bytes,
            font_cache_max_bytes=font_cache_max_bytes,
        )

    def render(
        self,
        document: Document | CompiledDocument,
        *,
        layout: LayoutOptions | None = None,
        output: RasterOptions | None = None,
    ) -> bytes:
        """Render a resource-owning document to encoded or raw raster bytes.

        Compile once with ``compile_document`` to reuse parsing and stylesheet
        merging across renderers and outputs. Layout dimensions are CSS pixels;
        ``output.scale`` multiplies explicit canvas dimensions as well as content.
        The existing ``render_*`` entry points retain their original pixel units.
        """
        compiled = _compiled_document(document)
        options = _document_options(layout, output)
        return self._native.render_compiled(
            compiled.node,
            list(compiled.stylesheets),
            native_render_settings(
                options,
                resources=compiled._native_resources,
                failed_font_files=() if layout is None else layout.failed_font_files,
            ),
            options,
        )

    def measure(
        self,
        document: Document | CompiledDocument,
        *,
        layout: LayoutOptions | None = None,
    ) -> MeasuredNode:
        """Measure a resource-owning document in CSS pixels.

        Measurement always uses a device pixel ratio of one. It reports layout
        geometry, before raster output rounds painted boxes to whole pixels.
        """
        compiled = _compiled_document(document)
        options = _document_options(layout)
        return measured_node_from_mapping(
            self._native.measure_compiled(
                compiled.node,
                list(compiled.stylesheets),
                native_render_settings(
                    options,
                    resources=compiled._native_resources,
                    failed_font_files=()
                    if layout is None
                    else layout.failed_font_files,
                ),
            )
        )

    def rasterize(
        self,
        document: Document | CompiledDocument,
        *,
        layout: LayoutOptions | None = None,
        scale: float = 1.0,
        dithering: DitheringAlgorithm = "none",
        draw_debug_border: bool = False,
    ) -> RasterImage:
        """Draw once and retain a bitmap with its actual pixel dimensions.

        Use ``image.encode()`` to export several formats without repeating
        layout, resource decoding, or drawing. ``image.tobytes()`` exposes
        straight-alpha RGBA8 together with ``size`` and ``stride``, including
        when the canvas dimensions are inferred. Scale follows ``render``.
        """
        compiled = _compiled_document(document)
        raster = RasterOptions(
            scale=scale,
            dithering=dithering,
            draw_debug_border=draw_debug_border,
        )
        options = _document_options(layout, raster)
        return RasterImage(
            self._native.rasterize_compiled(
                compiled.node,
                list(compiled.stylesheets),
                native_render_settings(
                    options,
                    resources=compiled._native_resources,
                    failed_font_files=()
                    if layout is None
                    else layout.failed_font_files,
                ),
            )
        )

    def render_svg(
        self,
        document: Document | CompiledDocument,
        *,
        layout: LayoutOptions | None = None,
    ) -> str:
        """Render a resource-owning document as SVG in CSS pixels."""
        compiled = _compiled_document(document)
        options = _document_options(layout)
        return self._native.render_svg_compiled(
            compiled.node,
            list(compiled.stylesheets),
            native_render_settings(
                options,
                resources=compiled._native_resources,
                failed_font_files=() if layout is None else layout.failed_font_files,
            ),
        )

    def needs(
        self,
        document: Document | CompiledDocument,
        *,
        layout: LayoutOptions | None = None,
        scale: float = 1.0,
    ) -> RenderNeeds:
        """Discover images and pending font files after applying the CSS cascade.

        Hidden nodes and unmatched rules are excluded by Takumi. Image identifiers
        include already supplied resources; font files are pending sources. Load
        files explicitly, then query again to resolve fallback and SVG text needs.
        Pass the same ``scale`` as raster output so resolution media queries and
        viewport rounding agree. Measurement and SVG use the default scale of one.
        This does not paint or access the network.
        """
        compiled = _compiled_document(document)
        options = _document_options(layout, RasterOptions(scale=scale))
        images, faces, font_files = self._native.needs_compiled(
            compiled.node,
            list(compiled.stylesheets),
            native_render_settings(
                options,
                resources=compiled._native_resources,
                failed_font_files=() if layout is None else layout.failed_font_files,
            ),
        )
        return RenderNeeds(tuple(images), tuple(faces), tuple(font_files))

    def load_font_file(self, url: str, data: bytes) -> None:
        """Supply bytes for a CSS ``@font-face src`` URL without fetching it.

        CSS supplies the family and face descriptors. The renderer owns loaded
        files until ``forget_font_file`` or ``clear_fonts``; these files are
        separate from the ``cache_font`` budget for manually registered families.
        """
        if not isinstance(url, str) or not url:
            raise ValueError("url must be a non-empty string")
        if not isinstance(data, bytes):
            raise TypeError("font file data must be bytes")
        self._native.load_font_file(url, data)

    def forget_font_file(self, url: str) -> bool:
        """Release a supplied CSS font file, so its URL is pending again."""
        return self._native.forget_font_file(url)

    def compile_node(
        self,
        node: NodeInput,
        *,
        validate: bool = False,
    ) -> CompiledNode:
        """Compile a Python node mapping for repeated rendering.

        Args:
            node: Node mapping accepted by Takumi.
            validate: Validate and normalize the mapping in Python before passing
                it to the native decoder.

        Returns:
            An opaque compiled node owned by the native binding.

        Raises:
            NodeValidationError: If Python-side validation is enabled and fails.
            NodeDecodeError: If the native decoder rejects the node.
        """
        if validate:
            node = validate_node(node)
        return self._native.compile_node(node)

    def compile_stylesheet(self, css: str) -> CompiledStyleSheet:
        """Compile CSS and fail if it cannot be parsed.

        Args:
            css: CSS source text.

        Returns:
            An opaque compiled stylesheet suitable for repeated rendering.

        Raises:
            StyleSheetError: If the stylesheet is invalid.
        """
        return self._native.compile_stylesheet(css)

    def compile_stylesheet_lossy(self, css: str) -> CompiledStyleSheet:
        """Compile CSS using Takumi's error-tolerant HTML stylesheet parser.

        Args:
            css: CSS source text, potentially containing declarations that Takumi
                cannot parse.

        Returns:
            A compiled stylesheet containing the declarations Takumi accepted.
        """
        return self._native.compile_stylesheet_lossy(css)

    def compile_keyframes(self, keyframes: KeyframesInput) -> CompiledStyleSheet:
        """Compile structured keyframe rules into a stylesheet.

        Args:
            keyframes: Keyframe mappings or rule objects accepted by Takumi.

        Returns:
            A compiled stylesheet containing the animation rules.

        Raises:
            StyleSheetError: If a keyframe rule cannot be compiled.
        """
        return self._native.compile_keyframes({"keyframes": keyframes})

    def register_font(self, font: FontResourceInput) -> tuple[str, ...]:
        """Register one font resource with this renderer.

        Args:
            font: Raw font bytes or a ``FontResource`` with metadata.

        Returns:
            The font-family names discovered or assigned during registration.

        Raises:
            FontError: If Takumi cannot decode or register the font.
        """
        return tuple(self._native.register_font(font))

    def register_fonts(self, fonts: Sequence[FontResourceInput]) -> tuple[str, ...]:
        """Register multiple font resources with this renderer.

        Args:
            fonts: Raw fonts or ``FontResource`` objects with metadata.

        Returns:
            All font-family names discovered or assigned during registration.

        Raises:
            FontError: If Takumi cannot decode or register a font.
        """
        return tuple(self._native.register_fonts(list(fonts)))

    def cache_font(self, font: FontResourceInput, key: str) -> tuple[str, ...]:
        """Register a font under ``key`` that the renderer may release for space.

        Use it for fonts that renders load on demand. Past ``font_cache_max_bytes``,
        the least recently used cached families are released, other than the ones
        this call registered; a render marks the families in its ``font_families``
        used. Check ``cached_fonts(key)`` before loading a font again.

        Args:
            font: Raw font bytes or a ``FontResource`` with metadata.
            key: Identifies the font, such as the URL it was downloaded from.
                Caching another font under the same key replaces the record.

        Returns:
            The font-family names discovered or assigned during registration.

        Raises:
            FontError: If Takumi cannot decode or register the font.
        """
        return tuple(self._native.cache_font(font, key))

    def cached_fonts(self, key: str, *, pin: bool = False) -> tuple[str, ...] | None:
        """Return the families a ``cache_font()`` call under ``key`` registered.

        A hit marks the families used, so they are the last to be released.

        Args:
            key: The key passed to ``cache_font()``.
            pin: Keep the families from ever being released for space.

        Returns:
            The family names, or ``None`` if nothing was cached under ``key`` or any
            of its families has since been released or unregistered.
        """
        families = self._native.cached_fonts(key, pin)
        return None if families is None else tuple(families)

    def unregister_font(self, name: str) -> bool:
        """Remove every face registered under a font-family name.

        All ``unicode_range`` subsets registered under ``name`` are removed
        together, so later renders treat the family as unknown and fall back, and
        ``cached_fonts()`` no longer reports the keys that registered it.

        Args:
            name: Font-family name returned by ``register_font()``.

        Returns:
            ``True`` if the family had registered faces, otherwise ``False``.
        """
        return self._native.unregister_font(name)

    def clear_fonts(self) -> None:
        """Remove every registered font, including fonts passed to ``__init__``.

        Only the bundled default font remains, and only when the renderer was
        created with ``load_default_fonts=True``.
        """
        self._native.clear_fonts()

    def render_compiled(
        self,
        node: CompiledNode,
        *,
        stylesheets: Sequence[CompiledStyleSheet] | None = None,
        keyframes: KeyframesInput | UnsetType | None = UNSET,
        options: RenderOptions | None = None,
        width: int | UnsetType | None = UNSET,
        height: int | UnsetType | None = UNSET,
        format: ImageOutputFormat | UnsetType = UNSET,
        quality: int | UnsetType | None = UNSET,
        lossless: bool | UnsetType | None = UNSET,
        font_size: float | UnsetType = UNSET,
        device_pixel_ratio: float | UnsetType = UNSET,
        draw_debug_border: bool | UnsetType = UNSET,
        time_ms: int | UnsetType = UNSET,
        dithering: DitheringAlgorithm | UnsetType = UNSET,
        images: Sequence[ImageResourceInput] | UnsetType | None = UNSET,
        font_families: Sequence[str] | UnsetType | None = UNSET,
        lang: str | UnsetType | None = UNSET,
    ) -> bytes:
        """Render a compiled node to an encoded image or raw RGBA bytes.

        Explicit keyword arguments override matching fields in ``options``;
        parameters left as ``UNSET`` inherit the supplied or default option.

        Args:
            node: Previously compiled node.
            stylesheets: Previously compiled stylesheets applied in order.
            keyframes: Structured animation rules, ``None`` to clear them, or
                ``UNSET`` to inherit ``options.keyframes``.
            options: Base render configuration.
            width: Output viewport width, or ``None`` for intrinsic sizing.
            height: Output viewport height, or ``None`` for intrinsic sizing.
            format: Static output format. ``"raw"`` returns row-major RGBA bytes.
            quality: Lossy encoder quality from 0 through 100 where supported.
            lossless: Whether to use lossless WebP encoding.
            font_size: Root font size in CSS pixels.
            device_pixel_ratio: Scale factor applied to raster output dimensions.
            draw_debug_border: Draw Takumi's layout debug borders.
            time_ms: Animation sampling time in milliseconds.
            dithering: Color-dithering algorithm for formats that use it.
            images: Per-render image resources addressable by their ``src`` values.
            font_families: Preferred fallback font-family order.
            lang: Document language used for text shaping and font selection.

        Returns:
            Encoded image bytes, or raw RGBA pixels when ``format="raw"``.

        Raises:
            RenderError: If layout or rendering fails.
            ResourceError: If an image resource cannot be decoded.
            UnsupportedFormatError: If the requested output cannot be encoded.
            ValueError: If an output option combination is invalid.
        """
        render_options = resolve_render_options(
            options,
            width=width,
            height=height,
            format=format,
            quality=quality,
            lossless=lossless,
            font_size=font_size,
            device_pixel_ratio=device_pixel_ratio,
            draw_debug_border=draw_debug_border,
            time_ms=time_ms,
            dithering=dithering,
            images=images,
            keyframes=keyframes,
            font_families=font_families,
            lang=lang,
        )
        return self._native.render_compiled(
            node,
            self._with_keyframes(stylesheets, render_options.keyframes),
            native_render_settings(render_options),
            render_options,
        )

    def measure_compiled(
        self,
        node: CompiledNode,
        *,
        stylesheets: Sequence[CompiledStyleSheet] | None = None,
        keyframes: KeyframesInput | UnsetType | None = UNSET,
        options: RenderOptions | None = None,
        width: int | UnsetType | None = UNSET,
        height: int | UnsetType | None = UNSET,
        font_size: float | UnsetType = UNSET,
        device_pixel_ratio: float | UnsetType = UNSET,
        draw_debug_border: bool | UnsetType = UNSET,
        time_ms: int | UnsetType = UNSET,
        dithering: DitheringAlgorithm | UnsetType = UNSET,
        images: Sequence[ImageResourceInput] | UnsetType | None = UNSET,
        font_families: Sequence[str] | UnsetType | None = UNSET,
        lang: str | UnsetType | None = UNSET,
    ) -> MeasuredNode:
        """Measure a compiled node without encoding an image.

        Explicit keyword arguments override matching fields in ``options``;
        parameters left as ``UNSET`` inherit the supplied or default option.

        Args:
            node: Previously compiled node.
            stylesheets: Previously compiled stylesheets applied in order.
            keyframes: Structured animation rules, ``None`` to clear them, or
                ``UNSET`` to inherit ``options.keyframes``.
            options: Base render configuration.
            width: Layout viewport width, or ``None`` for intrinsic sizing.
            height: Layout viewport height, or ``None`` for intrinsic sizing.
            font_size: Root font size in CSS pixels.
            device_pixel_ratio: Scale factor used during layout.
            draw_debug_border: Enable Takumi's debug-border layout mode.
            time_ms: Animation sampling time in milliseconds.
            dithering: Dithering option passed to the native measurement context.
            images: Per-render image resources addressable by their ``src`` values.
            font_families: Preferred fallback font-family order.
            lang: Document language used for text shaping and font selection.

        Returns:
            An immutable measurement tree with geometry and shaped text runs.

        Raises:
            RenderError: If layout or measurement fails.
            ResourceError: If an image resource cannot be decoded.
            NodeDecodeError: If Takumi returns an invalid measurement payload.
        """
        render_options = resolve_render_options(
            options,
            width=width,
            height=height,
            font_size=font_size,
            device_pixel_ratio=device_pixel_ratio,
            draw_debug_border=draw_debug_border,
            time_ms=time_ms,
            dithering=dithering,
            images=images,
            keyframes=keyframes,
            font_families=font_families,
            lang=lang,
        )
        measured = self._native.measure_compiled(
            node,
            self._with_keyframes(stylesheets, render_options.keyframes),
            native_render_settings(render_options),
        )
        return measured_node_from_mapping(measured)

    def render_node(
        self,
        node: NodeInput,
        *,
        stylesheets: Sequence[str] | None = None,
        keyframes: KeyframesInput | UnsetType | None = UNSET,
        options: RenderOptions | None = None,
        width: int | UnsetType | None = UNSET,
        height: int | UnsetType | None = UNSET,
        format: ImageOutputFormat | UnsetType = UNSET,
        quality: int | UnsetType | None = UNSET,
        lossless: bool | UnsetType | None = UNSET,
        font_size: float | UnsetType = UNSET,
        device_pixel_ratio: float | UnsetType = UNSET,
        draw_debug_border: bool | UnsetType = UNSET,
        time_ms: int | UnsetType = UNSET,
        dithering: DitheringAlgorithm | UnsetType = UNSET,
        images: Sequence[ImageResourceInput] | UnsetType | None = UNSET,
        font_families: Sequence[str] | UnsetType | None = UNSET,
        lang: str | UnsetType | None = UNSET,
        validate: bool = False,
    ) -> bytes:
        """Compile and render a Python node mapping.

        Explicit render keywords override matching fields in ``options``.

        Args:
            node: Node mapping accepted by Takumi.
            stylesheets: CSS source strings compiled with strict parsing.
            keyframes: Structured animation rules, ``None`` to clear them, or
                ``UNSET`` to inherit ``options.keyframes``.
            options: Base render configuration.
            width: Output viewport width, or ``None`` for intrinsic sizing.
            height: Output viewport height, or ``None`` for intrinsic sizing.
            format: Static output format. ``"raw"`` returns row-major RGBA bytes.
            quality: Lossy encoder quality from 0 through 100 where supported.
            lossless: Whether to use lossless WebP encoding.
            font_size: Root font size in CSS pixels.
            device_pixel_ratio: Scale factor applied to raster output dimensions.
            draw_debug_border: Draw Takumi's layout debug borders.
            time_ms: Animation sampling time in milliseconds.
            dithering: Color-dithering algorithm for formats that use it.
            images: Per-render image resources addressable by their ``src`` values.
            font_families: Preferred fallback font-family order.
            lang: Document language used for text shaping and font selection.
            validate: Validate and normalize ``node`` in Python before compilation.

        Returns:
            Encoded image bytes, or raw RGBA pixels when ``format="raw"``.

        Raises:
            NodeValidationError: If Python-side validation is enabled and fails.
            NodeDecodeError: If the native decoder rejects the node.
            StyleSheetError: If a stylesheet or keyframe rule is invalid.
            RenderError: If layout or rendering fails.
            UnsupportedFormatError: If the requested output cannot be encoded.
        """
        compiled = self.compile_node(node, validate=validate)
        compiled_stylesheets = self._compile_stylesheets(stylesheets)
        return self.render_compiled(
            compiled,
            stylesheets=compiled_stylesheets,
            keyframes=keyframes,
            options=options,
            width=width,
            height=height,
            format=format,
            quality=quality,
            lossless=lossless,
            font_size=font_size,
            device_pixel_ratio=device_pixel_ratio,
            draw_debug_border=draw_debug_border,
            time_ms=time_ms,
            dithering=dithering,
            images=images,
            font_families=font_families,
            lang=lang,
        )

    def measure_node(
        self,
        node: NodeInput,
        *,
        stylesheets: Sequence[str] | None = None,
        keyframes: KeyframesInput | UnsetType | None = UNSET,
        options: RenderOptions | None = None,
        width: int | UnsetType | None = UNSET,
        height: int | UnsetType | None = UNSET,
        font_size: float | UnsetType = UNSET,
        device_pixel_ratio: float | UnsetType = UNSET,
        draw_debug_border: bool | UnsetType = UNSET,
        time_ms: int | UnsetType = UNSET,
        dithering: DitheringAlgorithm | UnsetType = UNSET,
        images: Sequence[ImageResourceInput] | UnsetType | None = UNSET,
        font_families: Sequence[str] | UnsetType | None = UNSET,
        lang: str | UnsetType | None = UNSET,
        validate: bool = False,
    ) -> MeasuredNode:
        """Compile and measure a Python node mapping without encoding an image.

        Explicit render keywords override matching fields in ``options``.

        Args:
            node: Node mapping accepted by Takumi.
            stylesheets: CSS source strings compiled with strict parsing.
            keyframes: Structured animation rules, ``None`` to clear them, or
                ``UNSET`` to inherit ``options.keyframes``.
            options: Base render configuration.
            width: Layout viewport width, or ``None`` for intrinsic sizing.
            height: Layout viewport height, or ``None`` for intrinsic sizing.
            font_size: Root font size in CSS pixels.
            device_pixel_ratio: Scale factor used during layout.
            draw_debug_border: Enable Takumi's debug-border layout mode.
            time_ms: Animation sampling time in milliseconds.
            dithering: Dithering option passed to the native measurement context.
            images: Per-render image resources addressable by their ``src`` values.
            font_families: Preferred fallback font-family order.
            lang: Document language used for text shaping and font selection.
            validate: Validate and normalize ``node`` in Python before compilation.

        Returns:
            An immutable measurement tree with geometry and shaped text runs.

        Raises:
            NodeValidationError: If Python-side validation is enabled and fails.
            NodeDecodeError: If node decoding or measurement conversion fails.
            StyleSheetError: If a stylesheet or keyframe rule is invalid.
            RenderError: If layout or measurement fails.
        """
        compiled = self.compile_node(node, validate=validate)
        compiled_stylesheets = self._compile_stylesheets(stylesheets)
        return self.measure_compiled(
            compiled,
            stylesheets=compiled_stylesheets,
            keyframes=keyframes,
            options=options,
            width=width,
            height=height,
            font_size=font_size,
            device_pixel_ratio=device_pixel_ratio,
            draw_debug_border=draw_debug_border,
            time_ms=time_ms,
            dithering=dithering,
            images=images,
            font_families=font_families,
            lang=lang,
        )

    def compile_html(
        self,
        html: str,
        *,
        html_options: HtmlOptions | None = None,
    ) -> CompiledHtml:
        """Parse HTML into a compiled Takumi node.

        Args:
            html: HTML fragment or document source.
            html_options: Parser presets, Tailwind attribute name, and maximum
                element depth. Defaults to ``HtmlOptions``.

        Returns:
            The compiled root node and the embedded ``<style>`` stylesheet bundle.

        Raises:
            HtmlParseError: If the HTML cannot be parsed or exceeds configured
                limits.
        """
        parsed = parse_html(html, options=html_options)
        return CompiledHtml(
            node=parsed.node,
            stylesheets=parsed.stylesheets,
        )

    def render_html(
        self,
        html: str,
        *,
        stylesheets: Sequence[str] | None = None,
        keyframes: KeyframesInput | UnsetType | None = UNSET,
        html_options: HtmlOptions | None = None,
        options: RenderOptions | None = None,
        width: int | UnsetType | None = UNSET,
        height: int | UnsetType | None = UNSET,
        format: ImageOutputFormat | UnsetType = UNSET,
        quality: int | UnsetType | None = UNSET,
        lossless: bool | UnsetType | None = UNSET,
        font_size: float | UnsetType = UNSET,
        device_pixel_ratio: float | UnsetType = UNSET,
        draw_debug_border: bool | UnsetType = UNSET,
        time_ms: int | UnsetType = UNSET,
        dithering: DitheringAlgorithm | UnsetType = UNSET,
        images: Sequence[ImageResourceInput] | UnsetType | None = UNSET,
        font_families: Sequence[str] | UnsetType | None = UNSET,
        lang: str | UnsetType | None = UNSET,
    ) -> bytes:
        """Parse HTML and render it to an encoded image or raw RGBA bytes.

        External CSS uses the lossy parser appropriate for browser-authored
        stylesheets. Explicit render keywords override matching fields in
        ``options``.

        Args:
            html: HTML fragment or document source.
            stylesheets: Additional CSS source strings applied in order.
            keyframes: Structured animation rules, ``None`` to clear them, or
                ``UNSET`` to inherit ``options.keyframes``.
            html_options: HTML parsing configuration.
            options: Base render configuration.
            width: Output viewport width, or ``None`` for intrinsic sizing.
            height: Output viewport height, or ``None`` for intrinsic sizing.
            format: Static output format. ``"raw"`` returns row-major RGBA bytes.
            quality: Lossy encoder quality from 0 through 100 where supported.
            lossless: Whether to use lossless WebP encoding.
            font_size: Root font size in CSS pixels.
            device_pixel_ratio: Scale factor applied to raster output dimensions.
            draw_debug_border: Draw Takumi's layout debug borders.
            time_ms: Animation sampling time in milliseconds.
            dithering: Color-dithering algorithm for formats that use it.
            images: Per-render image resources addressable by their ``src`` values.
            font_families: Preferred fallback font-family order.
            lang: Document language used for text shaping and font selection.

        Returns:
            Encoded image bytes, or raw RGBA pixels when ``format="raw"``.

        Raises:
            HtmlParseError: If the HTML cannot be parsed.
            StyleSheetError: If structured keyframes cannot be compiled.
            RenderError: If layout or rendering fails.
            UnsupportedFormatError: If the requested output cannot be encoded.
        """
        compiled = self.compile_html(
            html,
            html_options=html_options,
        )
        compiled_stylesheets = (
            self._compile_html_stylesheets(stylesheets) + compiled.stylesheets
        )
        return self.render_compiled(
            compiled.node,
            stylesheets=compiled_stylesheets,
            keyframes=keyframes,
            options=options,
            width=width,
            height=height,
            format=format,
            quality=quality,
            lossless=lossless,
            font_size=font_size,
            device_pixel_ratio=device_pixel_ratio,
            draw_debug_border=draw_debug_border,
            time_ms=time_ms,
            dithering=dithering,
            images=images,
            font_families=font_families,
            lang=lang,
        )

    def measure_html(
        self,
        html: str,
        *,
        stylesheets: Sequence[str] | None = None,
        keyframes: KeyframesInput | UnsetType | None = UNSET,
        html_options: HtmlOptions | None = None,
        options: RenderOptions | None = None,
        width: int | UnsetType | None = UNSET,
        height: int | UnsetType | None = UNSET,
        font_size: float | UnsetType = UNSET,
        device_pixel_ratio: float | UnsetType = UNSET,
        draw_debug_border: bool | UnsetType = UNSET,
        time_ms: int | UnsetType = UNSET,
        dithering: DitheringAlgorithm | UnsetType = UNSET,
        images: Sequence[ImageResourceInput] | UnsetType | None = UNSET,
        font_families: Sequence[str] | UnsetType | None = UNSET,
        lang: str | UnsetType | None = UNSET,
    ) -> MeasuredNode:
        """Parse and measure HTML without encoding an image.

        External CSS uses the lossy parser appropriate for browser-authored
        stylesheets. Explicit render keywords override matching fields in
        ``options``.

        Args:
            html: HTML fragment or document source.
            stylesheets: Additional CSS source strings applied in order.
            keyframes: Structured animation rules, ``None`` to clear them, or
                ``UNSET`` to inherit ``options.keyframes``.
            html_options: HTML parsing configuration.
            options: Base render configuration.
            width: Layout viewport width, or ``None`` for intrinsic sizing.
            height: Layout viewport height, or ``None`` for intrinsic sizing.
            font_size: Root font size in CSS pixels.
            device_pixel_ratio: Scale factor used during layout.
            draw_debug_border: Enable Takumi's debug-border layout mode.
            time_ms: Animation sampling time in milliseconds.
            dithering: Dithering option passed to the native measurement context.
            images: Per-render image resources addressable by their ``src`` values.
            font_families: Preferred fallback font-family order.
            lang: Document language used for text shaping and font selection.

        Returns:
            An immutable measurement tree with geometry and shaped text runs.

        Raises:
            HtmlParseError: If the HTML cannot be parsed.
            StyleSheetError: If structured keyframes cannot be compiled.
            RenderError: If layout or measurement fails.
            NodeDecodeError: If Takumi returns an invalid measurement payload.
        """
        compiled = self.compile_html(
            html,
            html_options=html_options,
        )
        compiled_stylesheets = (
            self._compile_html_stylesheets(stylesheets) + compiled.stylesheets
        )
        return self.measure_compiled(
            compiled.node,
            stylesheets=compiled_stylesheets,
            keyframes=keyframes,
            options=options,
            width=width,
            height=height,
            font_size=font_size,
            device_pixel_ratio=device_pixel_ratio,
            draw_debug_border=draw_debug_border,
            time_ms=time_ms,
            dithering=dithering,
            images=images,
            font_families=font_families,
            lang=lang,
        )

    def render_template(
        self,
        template_name: str,
        context: Mapping[str, object],
        *,
        template_dir: str | Path = ".",
        stylesheets: Sequence[str] | None = None,
        keyframes: KeyframesInput | UnsetType | None = UNSET,
        html_options: HtmlOptions | None = None,
        options: RenderOptions | None = None,
        width: int | UnsetType | None = UNSET,
        height: int | UnsetType | None = UNSET,
        format: ImageOutputFormat | UnsetType = UNSET,
        quality: int | UnsetType | None = UNSET,
        lossless: bool | UnsetType | None = UNSET,
        font_size: float | UnsetType = UNSET,
        device_pixel_ratio: float | UnsetType = UNSET,
        draw_debug_border: bool | UnsetType = UNSET,
        time_ms: int | UnsetType = UNSET,
        dithering: DitheringAlgorithm | UnsetType = UNSET,
        images: Sequence[ImageResourceInput] | UnsetType | None = UNSET,
        font_families: Sequence[str] | UnsetType | None = UNSET,
        lang: str | UnsetType | None = UNSET,
    ) -> bytes:
        """Render a Jinja template through the HTML pipeline.

        Templates are loaded from ``template_dir`` using Jinja's standard
        filesystem loader and autoescaping rules. Explicit render keywords override
        matching fields in ``options``.

        Args:
            template_name: Template path relative to ``template_dir``.
            context: Values exposed to the Jinja template.
            template_dir: Root directory used to load templates.
            stylesheets: Additional CSS source strings applied in order.
            keyframes: Structured animation rules, ``None`` to clear them, or
                ``UNSET`` to inherit ``options.keyframes``.
            html_options: HTML parsing configuration.
            options: Base render configuration.
            width: Output viewport width, or ``None`` for intrinsic sizing.
            height: Output viewport height, or ``None`` for intrinsic sizing.
            format: Static output format. ``"raw"`` returns row-major RGBA bytes.
            quality: Lossy encoder quality from 0 through 100 where supported.
            lossless: Whether to use lossless WebP encoding.
            font_size: Root font size in CSS pixels.
            device_pixel_ratio: Scale factor applied to raster output dimensions.
            draw_debug_border: Draw Takumi's layout debug borders.
            time_ms: Animation sampling time in milliseconds.
            dithering: Color-dithering algorithm for formats that use it.
            images: Per-render image resources addressable by their ``src`` values.
            font_families: Preferred fallback font-family order.
            lang: Document language used for text shaping and font selection.

        Returns:
            Encoded image bytes, or raw RGBA pixels when ``format="raw"``.

        Raises:
            jinja2.TemplateError: If Jinja cannot load or render the template.
            HtmlParseError: If the rendered HTML cannot be parsed.
            RenderError: If layout or rendering fails.
            UnsupportedFormatError: If the requested output cannot be encoded.
        """
        html = render_template_to_html(
            template_name, context, template_dir=template_dir
        )
        return self.render_html(
            html,
            stylesheets=stylesheets,
            keyframes=keyframes,
            html_options=html_options,
            options=options,
            width=width,
            height=height,
            format=format,
            quality=quality,
            lossless=lossless,
            font_size=font_size,
            device_pixel_ratio=device_pixel_ratio,
            draw_debug_border=draw_debug_border,
            time_ms=time_ms,
            dithering=dithering,
            images=images,
            font_families=font_families,
            lang=lang,
        )

    def render_svg_compiled(
        self,
        node: CompiledNode,
        *,
        stylesheets: Sequence[CompiledStyleSheet] | None = None,
        keyframes: KeyframesInput | UnsetType | None = UNSET,
        options: RenderOptions | None = None,
        width: int | UnsetType | None = UNSET,
        height: int | UnsetType | None = UNSET,
        font_size: float | UnsetType = UNSET,
        time_ms: int | UnsetType = UNSET,
        images: Sequence[ImageResourceInput] | UnsetType | None = UNSET,
        font_families: Sequence[str] | UnsetType | None = UNSET,
        lang: str | UnsetType | None = UNSET,
    ) -> str:
        """Render a compiled node as an SVG document.

        Explicit keyword arguments override matching fields in ``options``;
        raster-only options in ``RenderOptions`` are ignored.

        Args:
            node: Previously compiled node.
            stylesheets: Previously compiled stylesheets applied in order.
            keyframes: Structured animation rules, ``None`` to clear them, or
                ``UNSET`` to inherit ``options.keyframes``.
            options: Base render configuration.
            width: SVG viewport width, or ``None`` for intrinsic sizing.
            height: SVG viewport height, or ``None`` for intrinsic sizing.
            font_size: Root font size in CSS pixels.
            time_ms: Animation sampling time in milliseconds.
            images: Per-render image resources addressable by their ``src`` values.
            font_families: Preferred fallback font-family order.
            lang: Document language used for text shaping and font selection.

        Returns:
            A complete SVG document as Unicode text.

        Raises:
            RenderError: If layout or SVG generation fails.
            ResourceError: If an image resource cannot be decoded.
        """
        render_options = resolve_render_options(
            options,
            width=width,
            height=height,
            font_size=font_size,
            time_ms=time_ms,
            images=images,
            keyframes=keyframes,
            font_families=font_families,
            lang=lang,
        )
        return self._native.render_svg_compiled(
            node,
            self._with_keyframes(stylesheets, render_options.keyframes),
            native_render_settings(render_options, raster=False),
        )

    def render_svg_node(
        self,
        node: NodeInput,
        *,
        stylesheets: Sequence[str] | None = None,
        keyframes: KeyframesInput | UnsetType | None = UNSET,
        options: RenderOptions | None = None,
        width: int | UnsetType | None = UNSET,
        height: int | UnsetType | None = UNSET,
        font_size: float | UnsetType = UNSET,
        time_ms: int | UnsetType = UNSET,
        images: Sequence[ImageResourceInput] | UnsetType | None = UNSET,
        font_families: Sequence[str] | UnsetType | None = UNSET,
        lang: str | UnsetType | None = UNSET,
        validate: bool = False,
    ) -> str:
        """Compile a Python node mapping and render it as SVG.

        Explicit render keywords override matching fields in ``options``.

        Args:
            node: Node mapping accepted by Takumi.
            stylesheets: CSS source strings compiled with strict parsing.
            keyframes: Structured animation rules, ``None`` to clear them, or
                ``UNSET`` to inherit ``options.keyframes``.
            options: Base render configuration.
            width: SVG viewport width, or ``None`` for intrinsic sizing.
            height: SVG viewport height, or ``None`` for intrinsic sizing.
            font_size: Root font size in CSS pixels.
            time_ms: Animation sampling time in milliseconds.
            images: Per-render image resources addressable by their ``src`` values.
            font_families: Preferred fallback font-family order.
            lang: Document language used for text shaping and font selection.
            validate: Validate and normalize ``node`` in Python before compilation.

        Returns:
            A complete SVG document as Unicode text.

        Raises:
            NodeValidationError: If Python-side validation is enabled and fails.
            NodeDecodeError: If the native decoder rejects the node.
            StyleSheetError: If a stylesheet or keyframe rule is invalid.
            RenderError: If layout or SVG generation fails.
        """
        compiled = self.compile_node(node, validate=validate)
        compiled_stylesheets = self._compile_stylesheets(stylesheets)
        return self.render_svg_compiled(
            compiled,
            stylesheets=compiled_stylesheets,
            keyframes=keyframes,
            options=options,
            width=width,
            height=height,
            font_size=font_size,
            time_ms=time_ms,
            images=images,
            font_families=font_families,
            lang=lang,
        )

    def render_svg_html(
        self,
        html: str,
        *,
        stylesheets: Sequence[str] | None = None,
        keyframes: KeyframesInput | UnsetType | None = UNSET,
        html_options: HtmlOptions | None = None,
        options: RenderOptions | None = None,
        width: int | UnsetType | None = UNSET,
        height: int | UnsetType | None = UNSET,
        font_size: float | UnsetType = UNSET,
        time_ms: int | UnsetType = UNSET,
        images: Sequence[ImageResourceInput] | UnsetType | None = UNSET,
        font_families: Sequence[str] | UnsetType | None = UNSET,
        lang: str | UnsetType | None = UNSET,
    ) -> str:
        """Parse HTML and render it as an SVG document.

        External CSS uses the lossy parser appropriate for browser-authored
        stylesheets. Explicit render keywords override matching fields in
        ``options``.

        Args:
            html: HTML fragment or document source.
            stylesheets: Additional CSS source strings applied in order.
            keyframes: Structured animation rules, ``None`` to clear them, or
                ``UNSET`` to inherit ``options.keyframes``.
            html_options: HTML parsing configuration.
            options: Base render configuration.
            width: SVG viewport width, or ``None`` for intrinsic sizing.
            height: SVG viewport height, or ``None`` for intrinsic sizing.
            font_size: Root font size in CSS pixels.
            time_ms: Animation sampling time in milliseconds.
            images: Per-render image resources addressable by their ``src`` values.
            font_families: Preferred fallback font-family order.
            lang: Document language used for text shaping and font selection.

        Returns:
            A complete SVG document as Unicode text.

        Raises:
            HtmlParseError: If the HTML cannot be parsed.
            StyleSheetError: If structured keyframes cannot be compiled.
            RenderError: If layout or SVG generation fails.
        """
        compiled = self.compile_html(
            html,
            html_options=html_options,
        )
        compiled_stylesheets = (
            self._compile_html_stylesheets(stylesheets) + compiled.stylesheets
        )
        return self.render_svg_compiled(
            compiled.node,
            stylesheets=compiled_stylesheets,
            keyframes=keyframes,
            options=options,
            width=width,
            height=height,
            font_size=font_size,
            time_ms=time_ms,
            images=images,
            font_families=font_families,
            lang=lang,
        )

    def render_svg_template(
        self,
        template_name: str,
        context: Mapping[str, object],
        *,
        template_dir: str | Path = ".",
        stylesheets: Sequence[str] | None = None,
        keyframes: KeyframesInput | UnsetType | None = UNSET,
        html_options: HtmlOptions | None = None,
        options: RenderOptions | None = None,
        width: int | UnsetType | None = UNSET,
        height: int | UnsetType | None = UNSET,
        font_size: float | UnsetType = UNSET,
        time_ms: int | UnsetType = UNSET,
        images: Sequence[ImageResourceInput] | UnsetType | None = UNSET,
        font_families: Sequence[str] | UnsetType | None = UNSET,
        lang: str | UnsetType | None = UNSET,
    ) -> str:
        """Render a Jinja template as an SVG document through the HTML pipeline.

        Args:
            template_name: Template path relative to ``template_dir``.
            context: Values exposed to the Jinja template.
            template_dir: Root directory used to load templates.
            stylesheets: Additional CSS source strings applied in order.
            keyframes: Structured animation rules, ``None`` to clear them, or
                ``UNSET`` to inherit ``options.keyframes``.
            html_options: HTML parsing configuration.
            options: Base render configuration.
            width: SVG viewport width, or ``None`` for intrinsic sizing.
            height: SVG viewport height, or ``None`` for intrinsic sizing.
            font_size: Root font size in CSS pixels.
            time_ms: Animation sampling time in milliseconds.
            images: Per-render image resources addressable by their ``src`` values.
            font_families: Preferred fallback font-family order.
            lang: Document language used for text shaping and font selection.

        Returns:
            A complete SVG document as Unicode text.

        Raises:
            jinja2.TemplateError: If Jinja cannot load or render the template.
            HtmlParseError: If the rendered HTML cannot be parsed.
            RenderError: If layout or SVG generation fails.
        """
        html = render_template_to_html(
            template_name, context, template_dir=template_dir
        )
        return self.render_svg_html(
            html,
            stylesheets=stylesheets,
            keyframes=keyframes,
            html_options=html_options,
            options=options,
            width=width,
            height=height,
            font_size=font_size,
            time_ms=time_ms,
            images=images,
            font_families=font_families,
            lang=lang,
        )

    def render_sequence_at_time(
        self,
        scenes: Sequence[AnimationScene],
        time_ms: int,
        *,
        stylesheets: Sequence[str] | None = None,
        keyframes: KeyframesInput | UnsetType | None = UNSET,
        options: RenderOptions | None = None,
        width: int | UnsetType | None = UNSET,
        height: int | UnsetType | None = UNSET,
        format: ImageOutputFormat | UnsetType = UNSET,
        quality: int | UnsetType | None = UNSET,
        lossless: bool | UnsetType | None = UNSET,
        font_size: float | UnsetType = UNSET,
        device_pixel_ratio: float | UnsetType = UNSET,
        draw_debug_border: bool | UnsetType = UNSET,
        dithering: DitheringAlgorithm | UnsetType = UNSET,
        images: Sequence[ImageResourceInput] | UnsetType | None = UNSET,
        font_families: Sequence[str] | UnsetType | None = UNSET,
        lang: str | UnsetType | None = UNSET,
        validate: bool = False,
    ) -> bytes:
        """Render the active scene in a timed sequence at one instant.

        Scene durations define the sequence timeline. Explicit render keywords
        override matching fields in ``options``.

        Args:
            scenes: Ordered nodes and their durations in milliseconds. Nodes may
                already be compiled.
            time_ms: Sequence sampling time in milliseconds.
            stylesheets: CSS source strings compiled with strict parsing.
            keyframes: Structured animation rules, ``None`` to clear them, or
                ``UNSET`` to inherit ``options.keyframes``.
            options: Base render configuration.
            width: Output viewport width, or ``None`` for intrinsic sizing.
            height: Output viewport height, or ``None`` for intrinsic sizing.
            format: Static output format. ``"raw"`` returns row-major RGBA bytes.
            quality: Lossy encoder quality from 0 through 100 where supported.
            lossless: Whether to use lossless WebP encoding.
            font_size: Root font size in CSS pixels.
            device_pixel_ratio: Scale factor applied to raster output dimensions.
            draw_debug_border: Draw Takumi's layout debug borders.
            dithering: Color-dithering algorithm for formats that use it.
            images: Per-render image resources addressable by their ``src`` values.
            font_families: Preferred fallback font-family order.
            lang: Document language used for text shaping and font selection.
            validate: Validate and normalize uncompiled scene nodes in Python.

        Returns:
            Encoded image bytes, or raw RGBA pixels when ``format="raw"``.

        Raises:
            AnimationError: If the sequence is empty or its timeline is invalid.
            NodeValidationError: If Python-side validation is enabled and fails.
            NodeDecodeError: If a native node decoder rejects a scene.
            RenderError: If layout or rendering fails.
            UnsupportedFormatError: If the requested output cannot be encoded.
        """
        render_options = resolve_render_options(
            options,
            width=width,
            height=height,
            format=format,
            quality=quality,
            lossless=lossless,
            font_size=font_size,
            device_pixel_ratio=device_pixel_ratio,
            draw_debug_border=draw_debug_border,
            dithering=dithering,
            images=images,
            keyframes=keyframes,
            font_families=font_families,
            lang=lang,
        )
        return self._native.render_sequence_at_time_compiled(
            self._compile_animation_scenes(scenes, validate=validate),
            time_ms,
            self._with_keyframes(
                self._compile_stylesheets(stylesheets),
                render_options.keyframes,
            ),
            native_render_settings(render_options, time_ms=0),
            render_options,
        )

    def render_animation(
        self,
        scenes: Sequence[AnimationScene],
        *,
        stylesheets: Sequence[str] | None = None,
        keyframes: KeyframesInput | UnsetType | None = UNSET,
        options: RenderOptions | None = None,
        encode_options: AnimationEncodeOptions | None = None,
        width: int | UnsetType | None = UNSET,
        height: int | UnsetType | None = UNSET,
        font_size: float | UnsetType = UNSET,
        device_pixel_ratio: float | UnsetType = UNSET,
        draw_debug_border: bool | UnsetType = UNSET,
        dithering: DitheringAlgorithm | UnsetType = UNSET,
        images: Sequence[ImageResourceInput] | UnsetType | None = UNSET,
        font_families: Sequence[str] | UnsetType | None = UNSET,
        lang: str | UnsetType | None = UNSET,
        fps: int = 30,
        format: AnimationOutputFormat | UnsetType = UNSET,
        quality: int | UnsetType | None = UNSET,
        lossless: bool | UnsetType | None = UNSET,
        loop_count: int | UnsetType | None = UNSET,
        webp_blend: bool | UnsetType = UNSET,
        webp_dispose: bool | UnsetType = UNSET,
        webp_speed: int | UnsetType | None = UNSET,
        validate: bool = False,
    ) -> bytes:
        """Render a timed scene sequence and encode it as an animation.

        Render keywords override fields in ``options``. Encoder keywords override
        fields in ``encode_options``.

        Args:
            scenes: Ordered nodes and their durations in milliseconds. Nodes may
                already be compiled.
            stylesheets: CSS source strings compiled with strict parsing.
            keyframes: Structured animation rules, ``None`` to clear them, or
                ``UNSET`` to inherit ``options.keyframes``.
            options: Base render configuration shared by every frame.
            encode_options: Base animation encoder configuration.
            width: Output viewport width, or ``None`` for intrinsic sizing.
            height: Output viewport height, or ``None`` for intrinsic sizing.
            font_size: Root font size in CSS pixels.
            device_pixel_ratio: Scale factor applied to frame dimensions.
            draw_debug_border: Draw Takumi's layout debug borders.
            dithering: Color-dithering algorithm for formats that use it.
            images: Per-render image resources addressable by their ``src`` values.
            font_families: Preferred fallback font-family order.
            lang: Document language used for text shaping and font selection.
            fps: Number of frames rendered per second: at most 90 for WebP and
                APNG and at most 50 for GIF, whose decoders clamp shorter frame
                delays.
            format: Animation container format.
            quality: Lossy encoder quality from 0 through 100 where supported.
            lossless: Whether to use lossless WebP encoding.
            loop_count: Number of animation repetitions, or ``None`` for the
                format-specific default.
            webp_blend: Blend each WebP frame with the previous canvas.
            webp_dispose: Dispose each WebP frame before drawing the next one.
            webp_speed: WebP encoder speed/effort setting supported by Takumi.
            validate: Validate and normalize uncompiled scene nodes in Python.

        Returns:
            Encoded WebP, APNG, or GIF animation bytes.

        Raises:
            AnimationError: If the timeline or encoder configuration is invalid.
            NodeValidationError: If Python-side validation is enabled and fails.
            NodeDecodeError: If a native node decoder rejects a scene.
            RenderError: If layout or frame rendering fails.
            UnsupportedFormatError: If the animation cannot be encoded.
            ValueError: If ``fps`` exceeds the format's limit or an encoder
                option combination is invalid.
        """
        render_options = resolve_render_options(
            options,
            width=width,
            height=height,
            font_size=font_size,
            device_pixel_ratio=device_pixel_ratio,
            draw_debug_border=draw_debug_border,
            dithering=dithering,
            images=images,
            keyframes=keyframes,
            font_families=font_families,
            lang=lang,
        )
        resolved_encode_options = resolve_animation_encode_options(
            encode_options,
            format=format,
            quality=quality,
            lossless=lossless,
            loop_count=loop_count,
            webp_blend=webp_blend,
            webp_dispose=webp_dispose,
            webp_speed=webp_speed,
        )
        return self._native.render_animation_compiled(
            self._compile_animation_scenes(scenes, validate=validate),
            self._with_keyframes(
                self._compile_stylesheets(stylesheets),
                render_options.keyframes,
            ),
            native_render_settings(render_options, time_ms=0),
            fps,
            resolved_encode_options,
        )

    def encode_frames(
        self,
        frames: Sequence[RawAnimationFrame],
        *,
        encode_options: AnimationEncodeOptions | None = None,
        format: AnimationOutputFormat | UnsetType = UNSET,
        quality: int | UnsetType | None = UNSET,
        lossless: bool | UnsetType | None = UNSET,
        loop_count: int | UnsetType | None = UNSET,
        webp_blend: bool | UnsetType = UNSET,
        webp_dispose: bool | UnsetType = UNSET,
        webp_speed: int | UnsetType | None = UNSET,
    ) -> bytes:
        """Encode pre-rendered raw RGBA frames as an animation.

        Explicit encoder keywords override matching fields in ``encode_options``.
        Each frame's byte length must equal ``width * height * 4``.

        Args:
            frames: Ordered raw RGBA frames with dimensions and durations.
            encode_options: Base animation encoder configuration.
            format: Animation container format.
            quality: Lossy encoder quality from 0 through 100 where supported.
            lossless: Whether to use lossless WebP encoding.
            loop_count: Number of animation repetitions, or ``None`` for the
                format-specific default.
            webp_blend: Blend each WebP frame with the previous canvas.
            webp_dispose: Dispose each WebP frame before drawing the next one.
            webp_speed: WebP encoder speed/effort setting supported by Takumi.

        Returns:
            Encoded WebP, APNG, or GIF animation bytes.

        Raises:
            AnimationError: If the frames have invalid dimensions or byte lengths,
                or the encoder configuration is invalid.
            UnsupportedFormatError: If the animation cannot be encoded.
        """
        resolved_encode_options = resolve_animation_encode_options(
            encode_options,
            format=format,
            quality=quality,
            lossless=lossless,
            loop_count=loop_count,
            webp_blend=webp_blend,
            webp_dispose=webp_dispose,
            webp_speed=webp_speed,
        )
        return self._native.encode_frames(list(frames), resolved_encode_options)

    def _compile_stylesheets(
        self,
        stylesheets: Sequence[str] | None,
    ) -> tuple[CompiledStyleSheet, ...]:
        """Strictly compile node CSS."""
        return tuple(
            self.compile_stylesheet(stylesheet) for stylesheet in stylesheets or ()
        )

    def _compile_html_stylesheets(
        self,
        stylesheets: Sequence[str] | None,
    ) -> tuple[CompiledStyleSheet, ...]:
        """Lossily compile HTML CSS."""
        return tuple(
            self.compile_stylesheet_lossy(stylesheet)
            for stylesheet in stylesheets or ()
        )

    def _with_keyframes(
        self,
        stylesheets: Sequence[CompiledStyleSheet] | None,
        keyframes: KeyframesInput | None,
    ) -> tuple[CompiledStyleSheet, ...]:
        """Append the compiled structured keyframes, if any, to compiled stylesheets."""
        compiled = tuple(stylesheets or ())
        if keyframes is None:
            return compiled
        return (*compiled, self.compile_keyframes(keyframes))

    def _compile_animation_scenes(
        self, scenes: Sequence[AnimationScene], *, validate: bool
    ) -> list[tuple[CompiledNode, int]]:
        """Compile uncompiled animation scene nodes while preserving duration."""
        return [
            (
                self._ensure_compiled_node(scene.node, validate=validate),
                scene.duration_ms,
            )
            for scene in scenes
        ]

    def _ensure_compiled_node(
        self,
        node: NodeInput | CompiledNode,
        *,
        validate: bool,
    ) -> CompiledNode:
        """Return a compiled node, compiling the input only when necessary."""
        if is_compiled_node(node):
            return node
        return self.compile_node(cast(NodeInput, node), validate=validate)


def resolve_render_options(
    options: RenderOptions | None = None,
    *,
    width: int | UnsetType | None = UNSET,
    height: int | UnsetType | None = UNSET,
    format: ImageOutputFormat | UnsetType = UNSET,
    quality: int | UnsetType | None = UNSET,
    lossless: bool | UnsetType | None = UNSET,
    font_size: float | UnsetType = UNSET,
    device_pixel_ratio: float | UnsetType = UNSET,
    draw_debug_border: bool | UnsetType = UNSET,
    time_ms: int | UnsetType = UNSET,
    dithering: DitheringAlgorithm | UnsetType = UNSET,
    images: Sequence[ImageResourceInput] | UnsetType | None = UNSET,
    keyframes: KeyframesInput | UnsetType | None = UNSET,
    font_families: Sequence[str] | UnsetType | None = UNSET,
    lang: str | UnsetType | None = UNSET,
) -> RenderOptions:
    """Apply the explicit keyword overrides, those not ``UNSET``, to ``options``."""
    resolved = apply_overrides(
        RenderOptions() if options is None else options,
        width=width,
        height=height,
        format=format,
        quality=quality,
        lossless=lossless,
        font_size=font_size,
        device_pixel_ratio=device_pixel_ratio,
        draw_debug_border=draw_debug_border,
        time_ms=time_ms,
        dithering=dithering,
        images=images,
        keyframes=keyframes,
        font_families=font_families,
        lang=lang,
    )
    if resolved.dithering == "floyd-steinberg":
        warn_deprecated(
            'dithering="floyd-steinberg"', 'dithering="ordered-bayer"', removal="0.6.0"
        )
    return resolved


def resolve_animation_encode_options(
    options: AnimationEncodeOptions | None = None,
    *,
    format: AnimationOutputFormat | UnsetType = UNSET,
    quality: int | UnsetType | None = UNSET,
    lossless: bool | UnsetType | None = UNSET,
    loop_count: int | UnsetType | None = UNSET,
    webp_blend: bool | UnsetType = UNSET,
    webp_dispose: bool | UnsetType = UNSET,
    webp_speed: int | UnsetType | None = UNSET,
) -> AnimationEncodeOptions:
    """Apply the explicit keyword overrides, those not ``UNSET``, to ``options``."""
    return apply_overrides(
        AnimationEncodeOptions() if options is None else options,
        format=format,
        quality=quality,
        lossless=lossless,
        loop_count=loop_count,
        webp_blend=webp_blend,
        webp_dispose=webp_dispose,
        webp_speed=webp_speed,
    )


_OptionsT = TypeVar("_OptionsT", RenderOptions, AnimationEncodeOptions)


def apply_overrides(options: _OptionsT, **overrides: object) -> _OptionsT:
    """Replace the fields of ``options`` whose override is not ``UNSET``."""
    updates = {name: value for name, value in overrides.items() if value is not UNSET}
    if not updates:
        return options
    return replace(options, **cast(Any, updates))


def is_compiled_node(node: object) -> TypeGuard[CompiledNode]:
    return isinstance(node, _core.CompiledNode)


def _compiled_document(document: Document | CompiledDocument) -> CompiledDocument:
    if isinstance(document, CompiledDocument):
        return document
    if not isinstance(document, Document):
        raise TypeError("expected Document or CompiledDocument")
    return compile_document(document)


def _raster_dimension(value: int | None, scale: float) -> int | None:
    if value is None:
        return None
    scaled = value * scale
    if not math.isfinite(scaled) or scaled > 2**32 - 1:
        raise ValueError("scaled canvas dimension exceeds the native 32-bit limit")
    return math.ceil(scaled)


def _document_options(
    layout: LayoutOptions | None,
    output: RasterOptions | None = None,
) -> RenderOptions:
    if layout is not None and not isinstance(layout, LayoutOptions):
        raise TypeError("layout must be a LayoutOptions value or None")
    if output is not None and not isinstance(output, RasterOptions):
        raise TypeError("output must be a RasterOptions value or None")
    layout = LayoutOptions() if layout is None else layout
    output = RasterOptions() if output is None else output
    return resolve_render_options(
        width=_raster_dimension(layout.width, output.scale),
        height=_raster_dimension(layout.height, output.scale),
        font_size=layout.font_size,
        time_ms=layout.time_ms,
        font_families=layout.font_families,
        lang=layout.lang,
        device_pixel_ratio=output.scale,
        format=output.format,
        quality=output.quality,
        lossless=output.lossless,
        dithering=output.dithering,
        draw_debug_border=output.draw_debug_border,
    )


_PACKAGE_DIR = Path(__file__).resolve().parent


def warn_deprecated(name: str, replacement: str, *, removal: str) -> None:
    """Warn on behalf of the first caller outside ``takumi_py``.

    Public methods call one another, so a fixed ``stacklevel`` would point inside the
    package, where default warning filters hide the warning.
    """
    level = 2
    frame = sys._getframe(1)
    while (
        frame.f_back is not None
        and Path(frame.f_code.co_filename).resolve().parent == _PACKAGE_DIR
    ):
        frame = frame.f_back
        level += 1
    warn(
        f"{name} is deprecated and will be removed in {removal}; "
        f"use {replacement} instead",
        DeprecationWarning,
        stacklevel=level,
    )
