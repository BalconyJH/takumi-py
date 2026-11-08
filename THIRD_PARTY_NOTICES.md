# Third-party notices

## takumi

This project uses `takumi` as a git submodule.

`takumi` is licensed under `MIT OR Apache-2.0`. This project elects to use
`takumi` under the MIT License.

Repository: <https://github.com/kane50613/takumi>

Copyright (c) 2025 Kane Wang

Source and wheel distributions include this notice and the complete selected MIT
license text as package license metadata:

- `takumilib/LICENSE-MIT`

The full repository checkout also retains `takumilib/LICENSE-APACHE` from the
dual-licensed upstream project.

## MathJax and mathematical font data

The optional formula typesetter uses a locally built JavaScript bundle containing
the following pinned npm packages. The bundle and SVG glyph-path data are included
in every wheel; installing the `math` extra additionally installs the JavaScript
runtime. No font or JavaScript download occurs during typesetting.

| Package | Version | License | Source |
| --- | --- | --- | --- |
| `@mathjax/src` | 4.1.3 | Apache-2.0 | <https://github.com/mathjax/MathJax-src> |
| `@mathjax/mathjax-newcm-font` | 4.1.3 | Apache-2.0 | <https://github.com/mathjax/MathJax-fonts> |
| `@mathjax/mathjax-mhchem-font-extension` | 4.1.3 | Apache-2.0 | <https://github.com/mathjax/MathJax-fonts> |
| `mhchemparser` | 4.2.1 | Apache-2.0 | <https://github.com/mhchem/mhchemParser> |

MathJax source includes Copyright (c) 2017-2026 The MathJax Consortium. NewCM and
mhchem font definitions include Copyright (c) 2024 MathJax, Inc. (www.mathjax.org).
mhchemparser is copyright (c) 2015-2023 Martin Hensel. The selected NewCM and mhchem SVG font-data
packages declare Apache-2.0 in their published `package.json`; those npm packages
do not contain separate LICENSE or NOTICE files. This inventory describes the SVG
path-data packages used here, not arbitrary New Computer Modern font binaries.

The complete Apache license texts supplied by MathJax and mhchemparser are shipped
as package license metadata:

- `LICENSES/MathJax-Apache-2.0.txt`
- `LICENSES/mhchemparser-Apache-2.0.txt`

The bundle is a modified build assembled by takumi-py: it selects a fixed TeX input
configuration, SVG output, LiteDOM adaptor, local font chunks, and a bounded JSON
bridge. Its build source and dependency lock live in `tools/mathjax/`; the bundled
manifest records versions, resource inventory, and content hashes. Upstream source
notices are retained with the build assets.

MiniRacer 0.14.1 is installed as a separate optional dependency and is not embedded
in the takumi-py native extension. Its own wheel supplies its runtime and license
notices: <https://github.com/bpcreech/PyMiniRacer>.
