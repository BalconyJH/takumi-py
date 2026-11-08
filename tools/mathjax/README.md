# Local MathJax bundle

This is a build tool, not a runtime requirement. Use Bun 1.4.4:

```bash
cd tools/mathjax
bun install --frozen-lockfile
bun run build
```

Commit the entry, dependency lock, generated bundle and manifest together. The build
checks package versions and licenses, embeds all selected SVG glyph chunks, and
records the source, dependency-lock and output hashes. Wheel and sdist builds use
these prebuilt assets without running Bun or npm.

The SVG bridge supplies no browser, Node loader, file or networking APIs. MiniRacer
runs it in a supervised Python worker. Parent wall-clock timeouts are required even
though V8 also has CPU and heap limits: a runaway Promise microtask can outlive a
MiniRacer Promise wait timeout.

The published npm font-data packages declare Apache-2.0. This bundle includes their
SVG path data, not font binaries. Attribution and complete license texts are in the
repository's `THIRD_PARTY_NOTICES.md` and `LICENSES/`.
