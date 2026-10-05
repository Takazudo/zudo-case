# Frame provenance and fidelity

Pinned repository: `Takazudo/zudo-case`
Commit: `6a13d80d816b0247ab9eee761c29c1fb786b76cc`
Source directory: `engineering/r6-body/source-data/`
Assembly logic: `engineering/r6-body/build_geometry.py`

| Upstream path relative to source-data | Git blob SHA | Included form |
|---|---|---|
| rail40/rail_mesh.json | 178fd2e720d83b92f2430603e5592c5854ca2087 | Byte-identical JSON at zudo-case/rail40_mesh.json |
| rail60/rail_mesh.json | 0233c8735a777e0081f2a9e347ed887668588208 | Byte-identical JSON at zudo-case/rail60_mesh.json |
| panels/zb-side-frame-3u/zd-side-frame-3u.kicad_pcb | d09df0a92b4cf1a0d0d17d55f597961143e092b2 | Derived display geometry; original outside vertices; rounded cutouts simplified |
| panels/zb-side-frame-7u/zd-side-frame-7u.kicad_pcb | b267d494d9ec8bb34248429d3064aa35c06f5b78 | Derived display geometry; original outside vertices; rounded cutouts simplified |
| panels/zb-side-frame-pad-3u/3u-padder.kicad_pcb | 6140e916babd58829474dfe0c07db702c8702b2b | Source rectangle / polygon coordinates, extruded 1.6 mm |
| panels/zb-side-frame-pad-1u/1u-padder.kicad_pcb | 574d4711accfa4d0854c2c5ad125d842aa30bd0b | Source polygon coordinates, extruded 1.6 mm |

Only the two rail JSON files are byte-identical upstream copies. A derivative PCB record's `sourceBlobSHA` identifies its source file; it is not the derivative's own hash or a claim of exact hole contours. Original PCB files remain in the repository and are not bundled. Local artifact hashes are listed in FILE-MANIFEST.json at the package root.

Rail geometry is transformed using the original alternating proper rotations. Every source index remains, including source duplicate/non-manifold surfaces. The PCB derivation preserves outside vertices, original padder positions and mounting axes, but uses capsule/ellipse approximations for rounded cutouts. These are intentionally not exact PCB manufacturing solids. No error bound or fastener-fit tolerance is asserted for the simplified curves.

The generation script `scripts/prepare-frame-data.py` documents every source coordinate and approximation, verifies both source Git blob hashes, and uses constrained triangulation (Shapely 2.1) to preserve open holes in the display solid. Its baked output is included, so normal HTML rebuilds require only the Python standard library. Test environment used Shapely 2.1.2.

The original repository documents the underlying sources as rail commit `0f7316ad9000b7906e5769aa89aff2dc18c661c8` and PCB commit `b4db88ce5c93709f3f2f0a031f75190081f02443`. No input source part was shortened or stretched to make F5 fit. The enclosure—not the 7U board—was deepened for C.

The supplied hinge dimension image is the user's reference attachment, retained from F4. Its unspecified details and all protective hardware envelopes remain provisional.
