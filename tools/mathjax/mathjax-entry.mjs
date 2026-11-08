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
const EX_DIMENSION =
  /^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)ex$/;

function parseFinite(value, label) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error(`${label} must be a finite number`);
  }
  return value;
}

function parseExDimension(value, label) {
  if (value === "0") {
    return 0;
  }
  const match =
    typeof value === "string" ? EX_DIMENSION.exec(value) : null;
  if (!match) {
    throw new Error(`${label} must use an explicit finite ex unit`);
  }
  return parseFinite(Number(match[1]), label);
}

function parseViewBox(value) {
  if (typeof value !== "string") {
    throw new Error("MathJax SVG is missing viewBox");
  }
  const parts = value.trim().split(/[\s,]+/);
  if (parts.length !== 4 || parts.some((part) => !XML_NUMBER.test(part))) {
    throw new Error(`unexpected MathJax viewBox: ${JSON.stringify(value)}`);
  }
  const [x, y, width, height] = parts.map((part) => Number(part));
  for (const [label, number] of [
    ["viewBox x", x],
    ["viewBox y", y],
    ["viewBox width", width],
    ["viewBox height", height],
  ]) {
    parseFinite(number, label);
  }
  if (width <= 0 || height <= 0) {
    throw new Error("MathJax viewBox dimensions must be positive");
  }
  return { x, y, width, height };
}

function approximatelyEqual(left, right, tolerance) {
  return Math.abs(left - right) <= tolerance;
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

    const viewBox = parseViewBox(adaptor.getAttribute(rendered, "viewBox"));
    const widthPx = (viewBox.width * fontSizePx) / 1000;
    const heightPx = (viewBox.height * fontSizePx) / 1000;

    // MathJax writes dimensions rounded to three decimal places in ex. Use
    // the viewBox supplied by MathJax's wrapper BBox for the actual geometry,
    // then verify its rounded presentation attributes against that geometry.
    const widthEx = parseExDimension(
      adaptor.getAttribute(rendered, "width"),
      "MathJax SVG width",
    );
    const heightEx = parseExDimension(
      adaptor.getAttribute(rendered, "height"),
      "MathJax SVG height",
    );
    const verticalAlignEx = parseExDimension(
      adaptor.getStyle(rendered, "vertical-align"),
      "MathJax SVG vertical-align",
    );
    const xHeight = svgJax.font.params.x_height;
    const exTolerancePx = 0.001 * xHeight * fontSizePx + 1e-9;
    const viewBoxTolerancePx = 0.0001 * fontSizePx + 1e-9;
    const roundedWidthPx = widthEx * xHeight * fontSizePx;
    const roundedHeightPx = heightEx * xHeight * fontSizePx;
    const roundedDepthPx = -verticalAlignEx * xHeight * fontSizePx;
    const depthPx = roundedDepthPx;
    const heightAboveBaselinePx = (-viewBox.y * fontSizePx) / 1000;
    for (const [label, number] of [
      ["width", widthPx],
      ["height", heightPx],
      ["depth", depthPx],
    ]) {
      parseFinite(number, label);
    }
    if (
      widthEx <= 0 ||
      heightEx <= 0 ||
      !approximatelyEqual(widthPx, roundedWidthPx, exTolerancePx) ||
      !approximatelyEqual(heightPx, roundedHeightPx, exTolerancePx) ||
      !approximatelyEqual(
        heightPx,
        Math.max(
          heightAboveBaselinePx + depthPx,
          (fontSizePx / 1000) * fontSizePx,
        ),
        exTolerancePx + viewBoxTolerancePx,
      )
    ) {
      throw new Error(
        "MathJax SVG geometry disagrees with its bounding box: " +
          JSON.stringify({
            widthPx,
            roundedWidthPx,
            heightPx,
            roundedHeightPx,
            depthPx,
            roundedDepthPx,
            verticalAlignEx,
            exTolerancePx,
          }),
      );
    }

    adaptor.setAttribute(rendered, "width", `${String(widthPx)}px`);
    adaptor.setAttribute(rendered, "height", `${String(heightPx)}px`);
    adaptor.removeAttribute(rendered, "style");

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
