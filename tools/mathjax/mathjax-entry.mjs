import { mathjax } from "@mathjax/src/js/mathjax.js";
import { liteAdaptor } from "@mathjax/src/js/adaptors/liteAdaptor.js";
import { RegisterHTMLHandler } from "@mathjax/src/js/handlers/html.js";
import { TeX } from "@mathjax/src/js/input/tex.js";
import { SVG } from "@mathjax/src/js/output/svg.js";
import { MathJaxMhchemFontExtension } from "@mathjax/mathjax-mhchem-font-extension/js/svg.js";
import { MathJaxNewcmFont } from "@mathjax/mathjax-newcm-font/js/svg.js";

import "@mathjax/src/js/input/tex/ams/AmsConfiguration.js";
import "@mathjax/src/js/input/tex/amscd/AmsCdConfiguration.js";
import "@mathjax/src/js/input/tex/bbox/BboxConfiguration.js";
import "@mathjax/src/js/input/tex/boldsymbol/BoldsymbolConfiguration.js";
import "@mathjax/src/js/input/tex/braket/BraketConfiguration.js";
import "@mathjax/src/js/input/tex/cancel/CancelConfiguration.js";
import "@mathjax/src/js/input/tex/cases/CasesConfiguration.js";
import "@mathjax/src/js/input/tex/centernot/CenternotConfiguration.js";
import "@mathjax/src/js/input/tex/color/ColorConfiguration.js";
import "@mathjax/src/js/input/tex/colortbl/ColortblConfiguration.js";
import "@mathjax/src/js/input/tex/configmacros/ConfigMacrosConfiguration.js";
import "@mathjax/src/js/input/tex/mathtools/MathtoolsConfiguration.js";
import "@mathjax/src/js/input/tex/mhchem/MhchemConfiguration.js";
import "@mathjax/src/js/input/tex/newcommand/NewcommandConfiguration.js";
import "@mathjax/src/js/input/tex/textcomp/TextcompConfiguration.js";
import "@mathjax/src/js/input/tex/textmacros/TextMacrosConfiguration.js";
import "@mathjax/src/js/input/tex/unicode/UnicodeConfiguration.js";
import "@mathjax/src/js/input/tex/units/UnitsConfiguration.js";
import "@mathjax/src/js/input/tex/upgreek/UpgreekConfiguration.js";
import "@mathjax/src/js/input/tex/verb/VerbConfiguration.js";

import "@mathjax/mathjax-newcm-font/js/svg/dynamic/PUA.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/accents-b-i.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/accents.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/arabic.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/arrows.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/braille-d.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/braille.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/calligraphic.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/cherokee.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/cyrillic-ss.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/cyrillic.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/devanagari.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/double-struck.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/fraktur.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/greek-ss.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/greek.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/hebrew.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/latin-b.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/latin-bi.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/latin-i.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/latin.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/marrows.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/math.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/monospace-ex.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/monospace-l.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/monospace.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/mshapes.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/phonetics-ss.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/phonetics.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/sans-serif-b.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/sans-serif-bi.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/sans-serif-ex.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/sans-serif-i.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/sans-serif-r.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/sans-serif.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/script.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/shapes.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/symbols-b-i.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/symbols.js";
import "@mathjax/mathjax-newcm-font/js/svg/dynamic/variants.js";

const adaptor = liteAdaptor();
RegisterHTMLHandler(adaptor);
MathJaxNewcmFont.addExtension(MathJaxMhchemFontExtension);

const DYNAMIC_PREFIX =
  "@mathjax/mathjax-newcm-font/js/svg/dynamic/";
const PRELOADED_DYNAMIC_FILES = new Set(
  [
    "PUA.js",
    "accents-b-i.js",
    "accents.js",
    "arabic.js",
    "arrows.js",
    "braille-d.js",
    "braille.js",
    "calligraphic.js",
    "cherokee.js",
    "cyrillic-ss.js",
    "cyrillic.js",
    "devanagari.js",
    "double-struck.js",
    "fraktur.js",
    "greek-ss.js",
    "greek.js",
    "hebrew.js",
    "latin-b.js",
    "latin-bi.js",
    "latin-i.js",
    "latin.js",
    "marrows.js",
    "math.js",
    "monospace-ex.js",
    "monospace-l.js",
    "monospace.js",
    "mshapes.js",
    "phonetics-ss.js",
    "phonetics.js",
    "sans-serif-b.js",
    "sans-serif-bi.js",
    "sans-serif-ex.js",
    "sans-serif-i.js",
    "sans-serif-r.js",
    "sans-serif.js",
    "script.js",
    "shapes.js",
    "symbols-b-i.js",
    "symbols.js",
    "variants.js",
  ].map((file) => `${DYNAMIC_PREFIX}${file}`),
);

mathjax.asyncIsSynchronous = true;
mathjax.asyncLoad = (name) => {
  if (!PRELOADED_DYNAMIC_FILES.has(name)) {
    throw new Error(`unsupported asynchronous MathJax load: ${name}`);
  }
};

const XML_NUMBER =
  /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/;
const MIN_BBOX_EM = 0.001;
const F32_MAX = 3.4028234663852886e38;
const SAFE_BORDER_DECLARATION =
  /^border(?:-(?:top|right|bottom|left))?:\s*(?:0|[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:px|pt|pc|in|cm|mm|em|ex))\s+(?:solid|dashed|dotted)(?:\s+(?:[A-Za-z]+|#[0-9A-Fa-f]{3,8}))?$/i;
const SAFE_FRAME_STYLES =
  /^(?:none|solid|dashed|dotted)(?:\s+(?:none|solid|dashed|dotted)){3}$/;

function parseFinite(value, label) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error(`${label} must be a finite number`);
  }
  return value;
}

function geometryPixels(value, fontSizePx, label) {
  const pixels = value * fontSizePx;
  if (!Number.isFinite(pixels) || Math.abs(pixels) > F32_MAX) {
    const error = new RangeError(`${label} exceeds the finite f32 range`);
    error.id = "GeometryLimit";
    throw error;
  }
  return pixels;
}

function polygonPath(value) {
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error("MathJax polygon is missing points");
  }
  const points = value.trim().split(/\s+/).map((point) => {
    const parts = point.split(",");
    if (
      parts.length !== 2 ||
      !XML_NUMBER.test(parts[0]) ||
      !XML_NUMBER.test(parts[1])
    ) {
      throw new Error(`unexpected MathJax polygon point: ${JSON.stringify(point)}`);
    }
    return [parseFinite(Number(parts[0]), "polygon x"), parseFinite(Number(parts[1]), "polygon y")];
  });
  if (points.length < 3) {
    throw new Error("MathJax polygon must contain at least three points");
  }
  return (
    `M${points[0][0]} ${points[0][1]}` +
    points
      .slice(1)
      .map(([x, y]) => `L${x} ${y}`)
      .join("") +
    "Z"
  );
}

function isSafeBorderStyle(value) {
  const declarations = value
    .split(";")
    .map((declaration) => declaration.trim())
    .filter(Boolean);
  return (
    declarations.length > 0 &&
    declarations.every((declaration) =>
      SAFE_BORDER_DECLARATION.test(declaration),
    )
  );
}

function normalizeTableRule(rule, kind) {
  const marker = kind === "line" ? "data-line" : "data-frame";
  const allowed = new Set([
    "class",
    "fill",
    "stroke",
    "stroke-width",
    "stroke-thickness",
    "stroke-dasharray",
    "stroke-linecap",
    "transform",
    marker,
    ...(kind === "line" ? ["x1", "y1", "x2", "y2"] : ["x", "y", "width", "height"]),
  ]);
  const unsupported = Object.keys(rule.attributes).filter(
    (name) => !allowed.has(name),
  );
  if (unsupported.length) {
    throw new Error(
      `unsupported MathJax table-rule attributes: ${unsupported.join(", ")}`,
    );
  }

  const markerValue = adaptor.getAttribute(rule, marker);
  if (
    (kind === "line" && !["h", "v"].includes(markerValue)) ||
    (kind === "rect" && markerValue !== "true")
  ) {
    throw new Error(`unexpected MathJax ${marker}: ${JSON.stringify(markerValue)}`);
  }
  const className = adaptor.getAttribute(rule, "class");
  const style = /^mjx-(solid|dashed|dotted)$/.exec(className ?? "")?.[1];
  if (!style) {
    throw new Error(
      `unexpected MathJax table-rule class: ${JSON.stringify(className)}`,
    );
  }

  const strokeWidth = adaptor.getAttribute(rule, "stroke-width");
  const strokeThickness = adaptor.getAttribute(rule, "stroke-thickness");
  if (typeof strokeWidth === "string" && typeof strokeThickness === "string") {
    throw new Error("MathJax table rule has two stroke widths");
  }
  if (typeof strokeThickness === "string") {
    if (
      !XML_NUMBER.test(strokeThickness) ||
      !Number.isFinite(Number(strokeThickness)) ||
      Number(strokeThickness) < 0
    ) {
      throw new Error(
        `invalid MathJax table-rule stroke thickness: ${JSON.stringify(strokeThickness)}`,
      );
    }
    adaptor.setAttribute(rule, "stroke-width", strokeThickness);
  } else if (typeof strokeWidth !== "string") {
    // MathJax's SVG stylesheet supplies this for ordinary table rules.
    adaptor.setAttribute(rule, "stroke-width", "70");
  }

  adaptor.setAttribute(rule, "fill", "none");
  adaptor.removeAttribute(rule, marker);
  adaptor.removeAttribute(rule, "class");
  adaptor.removeAttribute(rule, "stroke-thickness");
  adaptor.removeAttribute(rule, "stroke-dasharray");
  adaptor.removeAttribute(rule, "stroke-linecap");
  if (style === "dashed") {
    adaptor.setAttribute(rule, "stroke-dasharray", "140");
  } else if (style === "dotted") {
    adaptor.setAttribute(rule, "stroke-dasharray", "0,140");
    adaptor.setAttribute(rule, "stroke-linecap", "round");
  }
}

function normalizeDashedColumnRule(line) {
  const allowed = new Set([
    "x1",
    "y1",
    "x2",
    "y2",
    "stroke",
    "stroke-width",
    "stroke-linecap",
    "stroke-dasharray",
    "width",
  ]);
  const unsupported = Object.keys(line.attributes).filter(
    (name) => !allowed.has(name),
  );
  if (unsupported.length) {
    throw new Error(
      `unsupported MathJax dashed-column attributes: ${unsupported.join(", ")}`,
    );
  }
  const width = adaptor.getAttribute(line, "width");
  if (
    typeof width === "string" &&
    (!XML_NUMBER.test(width) ||
      !Number.isFinite(Number(width)) ||
      Number(width) < 0)
  ) {
    throw new Error(
      `unexpected MathJax dashed-column width: ${JSON.stringify(width)}`,
    );
  }
  if (
    adaptor.getAttribute(line, "stroke") !== "" ||
    adaptor.getAttribute(line, "stroke-linecap") !== "square" ||
    typeof adaptor.getAttribute(line, "stroke-dasharray") !== "string" ||
    typeof adaptor.getAttribute(line, "stroke-width") !== "string"
  ) {
    throw new Error("unexpected MathJax dashed-column markup");
  }
  adaptor.removeAttribute(line, "stroke");
  adaptor.removeAttribute(line, "width");
  adaptor.setAttribute(line, "fill", "none");
}

function sanitizeRenderedSvg(rendered) {
  for (const polygon of adaptor.tags(rendered, "polygon")) {
    const attributes = new Set(Object.keys(polygon.attributes));
    const allowed = new Set([
      "points",
      "fill",
      "stroke",
      "stroke-width",
      "transform",
    ]);
    const unsupported = [...attributes].filter((name) => !allowed.has(name));
    if (unsupported.length) {
      throw new Error(
        `unsupported MathJax polygon attributes: ${unsupported.join(", ")}`,
      );
    }
    const path = adaptor.node("path");
    adaptor.setAttribute(
      path,
      "d",
      polygonPath(adaptor.getAttribute(polygon, "points")),
    );
    for (const name of ["fill", "stroke", "stroke-width", "transform"]) {
      const value = adaptor.getAttribute(polygon, name);
      if (typeof value === "string") {
        adaptor.setAttribute(path, name, value);
      }
    }
    adaptor.replace(path, polygon);
  }
  for (const line of adaptor.tags(rendered, "line")) {
    if (typeof adaptor.getAttribute(line, "data-line") === "string") {
      normalizeTableRule(line, "line");
    } else if (
      adaptor.getAttribute(line, "stroke") === "" ||
      typeof adaptor.getAttribute(line, "width") === "string"
    ) {
      normalizeDashedColumnRule(line);
    }
  }
  for (const rect of adaptor.tags(rendered, "rect")) {
    if (typeof adaptor.getAttribute(rect, "data-frame") === "string") {
      normalizeTableRule(rect, "rect");
    }
  }
  for (const group of adaptor.tags(rendered, "g")) {
    const style = adaptor.getAttribute(group, "style");
    if (typeof style === "string") {
      if (!isSafeBorderStyle(style.trim())) {
        throw new Error(`unsupported MathJax SVG style: ${JSON.stringify(style)}`);
      }
      adaptor.removeAttribute(group, "style");
    }
    const frameStyles = adaptor.getAttribute(group, "data-frame-styles");
    if (typeof frameStyles === "string") {
      if (frameStyles !== "" && !SAFE_FRAME_STYLES.test(frameStyles.trim())) {
        throw new Error(
          `unexpected MathJax frame styles: ${JSON.stringify(frameStyles)}`,
        );
      }
      adaptor.removeAttribute(group, "data-frame-styles");
    }
    const padding = adaptor.getAttribute(group, "data-padding");
    if (typeof padding === "string") {
      if (padding !== "0") {
        throw new Error(
          `unexpected MathJax frame padding: ${JSON.stringify(padding)}`,
        );
      }
      adaptor.removeAttribute(group, "data-padding");
    }
  }
}

async function typeset(
  texSource,
  display,
  fontSizePx,
  exRatio,
  color = null,
  mhchemEnabled = false,
) {
  if (typeof texSource !== "string") {
    throw new TypeError("texSource must be a string");
  }
  if (typeof fontSizePx !== "number" || !Number.isFinite(fontSizePx)) {
    throw new TypeError("fontSizePx must be a finite number");
  }
  if (typeof exRatio !== "number" || !Number.isFinite(exRatio)) {
    throw new TypeError("exRatio must be a finite number");
  }
  if (typeof display !== "boolean") {
    throw new TypeError("display must be a boolean");
  }
  if (typeof mhchemEnabled !== "boolean") {
    throw new TypeError("mhchemEnabled must be a boolean");
  }
  if (
    color !== null &&
    (typeof color !== "string" || color.length === 0 || color.length > 128)
  ) {
    throw new TypeError("color must be null or a non-empty string");
  }

  try {
    // A new input and output jax per conversion keeps \def and \newcommand
    // isolated while reusing the immutable, preloaded font tables.
    const tex = new TeX({
      packages: [
        "base",
        "ams",
        "amscd",
        "bbox",
        "boldsymbol",
        "braket",
        "cancel",
        "cases",
        "centernot",
        "color",
        "colortbl",
        "configmacros",
        "mathtools",
        "newcommand",
        "textcomp",
        "textmacros",
        "unicode",
        "units",
        "upgreek",
        "verb",
        ...(mhchemEnabled ? ["mhchem"] : []),
      ],
      maxBuffer: 65536,
      tags: "none",
      macros: {
        label: "\\TAKUMIUnsupportedLabel",
        ref: "\\TAKUMIUnsupportedRef",
        eqref: "\\TAKUMIUnsupportedEqref",
        tag: "\\TAKUMIUnsupportedTag",
      },
      formatError: (_jax, error) => {
        throw error;
      },
    });
    const svgJax = new SVG({
      fontData: MathJaxNewcmFont,
      fontCache: "none",
      linebreaks: {
        inline: false,
      },
    });
    const html = mathjax.document("", {
      InputJax: tex,
      OutputJax: svgJax,
    });

    const container = await mathjax.handleRetriesFor(() =>
      html.convert(texSource, {
        display,
        em: fontSizePx,
        ex: fontSizePx * exRatio,
        containerWidth: 1000000,
      }),
    );
    const renderedSvgs = adaptor.tags(container, "svg");
    if (renderedSvgs.length !== 1) {
      throw new Error(
        `MathJax produced ${renderedSvgs.length} SVG roots; exactly one is required`,
      );
    }
    const rendered = renderedSvgs[0];
    if (color !== null) {
      const foreground = adaptor.tags(rendered, "g")[0];
      if (!foreground) {
        throw new Error("MathJax SVG has no foreground group");
      }
      adaptor.setAttribute(foreground, "fill", color);
      adaptor.setAttribute(foreground, "stroke", color);
    }

    const bbox = svgJax.getBBox(svgJax.math, html);
    const widthEm = parseFinite(bbox.w, "MathJax BBox width");
    const heightAboveBaselineEm = parseFinite(
      bbox.h,
      "MathJax BBox height",
    );
    const depthEm = parseFinite(bbox.d, "MathJax BBox depth");
    const rawHeightEm = heightAboveBaselineEm + depthEm;
    if (!Number.isFinite(rawHeightEm)) {
      const error = new RangeError(
        "MathJax BBox total height exceeds the finite range",
      );
      error.id = "GeometryLimit";
      throw error;
    }
    const heightEm = parseFinite(rawHeightEm, "MathJax BBox total height");
    if (widthEm < 0 || heightEm < 0) {
      throw new Error("MathJax BBox dimensions must not be negative");
    }
    const renderedWidthEm = Math.max(widthEm, MIN_BBOX_EM);
    const renderedHeightEm = Math.max(heightEm, MIN_BBOX_EM);
    const widthPx = geometryPixels(renderedWidthEm, fontSizePx, "width");
    const heightPx = geometryPixels(renderedHeightEm, fontSizePx, "height");
    const depthPx = geometryPixels(depthEm, fontSizePx, "depth");
    for (const [label, value] of [
      ["viewBox y", -heightAboveBaselineEm * 1000],
      ["viewBox width", renderedWidthEm * 1000],
      ["viewBox height", renderedHeightEm * 1000],
    ]) {
      const checked = parseFinite(value, label);
      if (Math.abs(checked) > F32_MAX) {
        throw Object.assign(
          new RangeError(`${label} exceeds the finite f32 range`),
          { id: "GeometryLimit" },
        );
      }
    }
    for (const [label, number] of [
      ["width", widthPx],
      ["height", heightPx],
      ["depth", depthPx],
    ]) {
      parseFinite(number, label);
    }

    adaptor.setAttribute(rendered, "width", `${String(widthPx)}px`);
    adaptor.setAttribute(rendered, "height", `${String(heightPx)}px`);
    adaptor.setAttribute(
      rendered,
      "viewBox",
      [
        0,
        -heightAboveBaselineEm * 1000,
        renderedWidthEm * 1000,
        renderedHeightEm * 1000,
      ].join(" "),
    );
    adaptor.removeAttribute(rendered, "style");
    adaptor.removeAttribute(rendered, "data-mjx-viewBox");
    sanitizeRenderedSvg(rendered);

    return {
      svg: adaptor.outerHTML(rendered),
      widthPx,
      heightPx,
      depthPx,
    };
  } catch (error) {
    const id = typeof error?.id === "string" ? error.id : "MathJaxError";
    const message =
      typeof error?.message === "string" ? error.message : String(error);
    throw `${id}: ${message}`;
  }
}

globalThis.TakumiMathJax = Object.freeze({ typeset });
