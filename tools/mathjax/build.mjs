// Build-only tool. Wheel and sdist consumers use the checked-in bundle.
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { gzipSync } from "node:zlib";

const root = dirname(fileURLToPath(import.meta.url));
const output = resolve(root, "../../python/takumi_py/math/assets");
const entry = join(root, "mathjax-entry.mjs");
const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex");
if (Bun.version !== "1.4.4") {
  throw new Error(`Expected Bun 1.4.4, got ${Bun.version}`);
}
const packages = [
  ["@mathjax/src", "4.1.3"],
  ["@mathjax/mathjax-newcm-font", "4.1.3"],
  ["@mathjax/mathjax-mhchem-font-extension", "4.1.3"],
  ["mhchemparser", "4.2.1"],
];
const inventory = [];
for (const [name, expected] of packages) {
  const meta = JSON.parse(await readFile(join(root, "node_modules", name, "package.json"), "utf8"));
  if (meta.version !== expected || meta.license !== "Apache-2.0") {
    throw new Error(`Unexpected package version/license: ${name}`);
  }
  inventory.push({ name, version: meta.version, license: meta.license });
}
const built = await Bun.build({
  entrypoints: [entry],
  target: "browser",
  format: "iife",
  minify: true,
  sourcemap: "none",
  throw: true,
});
if (built.outputs.length !== 1) {
  throw new Error("The runtime must be one self-contained bundle");
}
const banner = `/* takumi-py MathJax build. MathJax 4.1.3, NewCM 4.1.3,
 * mhchem font extension 4.1.3, mhchemparser 4.2.1: Apache-2.0.
 * Copyright (c) 2017-2026 The MathJax Consortium.
 * Copyright (c) 2024 MathJax, Inc. (www.mathjax.org).
 * Copyright (c) 2015-2023 Martin Hensel.
 * Modified bundle: LiteDOM, fixed TeX packages, local glyph paths, JSON bridge.
 * See THIRD_PARTY_NOTICES.md and LICENSES in the package distribution.
 */\n`;
const bundle = Buffer.concat([Buffer.from(banner), Buffer.from(await built.outputs[0].arrayBuffer())]);
const source = await readFile(entry);
const fontChunks = [...source.toString().matchAll(/import "(@mathjax\/mathjax-newcm-font\/js\/svg\/dynamic\/[^\"]+)"/g)].map((match) => match[1]);
const manifest = {
  schema_version: 1,
  bundle: {
    file: "mathjax.bundle.js",
    sha256: sha256(bundle),
    bytes: bundle.length,
    gzip_bytes: gzipSync(bundle).length,
  },
  build: {
    bun_version: Bun.version,
    command: "bun install --frozen-lockfile && bun run build",
    target: "browser",
    format: "iife",
    entry: "mathjax-entry.mjs",
    entry_sha256: sha256(source),
    lock_sha256: sha256(await readFile(join(root, "bun.lock"))),
  },
  packages: inventory,
  runtime: {
    package: "mini-racer",
    version: "0.14.1",
    tested_platforms: ["macos-aarch64"],
    linux_glibc_minimum: "2.27",
    isolation: "supervised-python-process",
  },
  font_chunks: fontChunks,
  licenses: ["LICENSES/MathJax-Apache-2.0.txt", "LICENSES/mhchemparser-Apache-2.0.txt"],
};
await mkdir(output, { recursive: true });
await writeFile(join(output, "mathjax.bundle.js"), bundle);
await writeFile(join(output, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
console.log(`Built ${bundle.length} bytes, sha256 ${manifest.bundle.sha256}`);
