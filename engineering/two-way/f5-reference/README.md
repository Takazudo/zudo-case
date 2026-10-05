# Zudo Case F5 — original rail/frame integration

A, B and C now use the zudo-case source rail/frame arrangement in both populated trays.
**This is an interactive dimensional study, not production CAD or a durability approval.**

Open `zudo-case-F5.html` directly in a modern browser. It is self-contained and needs no network.
Start with **Rail frame → A / B / C**, then use **Separate side layers**. `Closed`, `Play · 45°`, `Closure joint`, `Trunk`, and the previous accessory views remain available.

## What changed

| Family | Per tray | Frame now used | Lid rear depth |
|---|---|---|---:|
| A | 3U / 60HP | One original 3U frame | 48 mm |
| B | 6U / 60HP | Two original 3U frames, 1 mm apart | 48 mm |
| C | 7U / 40HP | Original full-depth 7U fixer and 3U + 3U + 1U padders | **70 mm** |

The original 7U board is up to 60.015381 mm deep. With its mounting datum below the module front, it reaches 61.950925 mm behind that front. The previous 48 mm lid cannot hold it unchanged. C's source board was **not shortened**. Its 70 mm lid leaves 6.549075 mm to the modeled inside back plate.

B's shell row-direction dimension becomes 290 mm, not 289 mm, to retain a 1 mm gap between the two original 3U assemblies. The collar seat is moved outward to clear the real side-board stack. Exterior nut-cover envelopes are counted in the new transport width.

## Fidelity

* The 40HP and 60HP rail JSONs are byte-identical upstream Git blobs. Every source triangle is retained; only proper rigid transforms are applied.
* PCB outside vertices, padder rectangles, layer thicknesses, source row/fastener datums, and padder offsets follow the pinned KiCad design. **Rounded cutouts are simplified for visualization.** Do not manufacture PCBs or drill parts from GLBs.
* The source 1.6 + 1.6 mm PCB stack, 8 mm side spacers, 1 mm outer washers, and 1.4 mm fastener-head study are retained. Unspecified hardware dimensions, guard details, mounting bores and fastener lengths remain provisional.
* Both trays use the same selected frame arrangement. The rail-frame inspection shows one tray's frame, with the shell omitted.

Source: `Takazudo/zudo-case` at `6a13d80d816b0247ab9eee761c29c1fb786b76cc`. See [frame integration](docs/RAIL-FRAME-INTEGRATION.md) and [provenance](reference/PROVENANCE.md).

## Files

`models/` contains 15 F5 setup JSONs and six viewing-only GLBs: a frame view and a playing view for each family. Setup/geometry coordinates use mm/Z-up; GLBs use metres/Y-up. `docs/` includes dimensional tables, frame-part counts and nominal mounting datums. `docs/archive-F4/` contains superseded background documents; its old dimensions and validation results do not apply to F5.

See [validation and limitations](docs/VALIDATION.md): 117 numerical/source tests, 69 browser checks, and six GLB round-trip checks passed. The browser run used the software renderer, not WebGL.

## Build and test

```sh
python build.py                       # standard library; offline baked reference geometry
node --test tests/frame.test.cjs      # source / geometry / regression checks
python tests/browser-f5.py            # Playwright + /usr/bin/chromium
node export-models.cjs
python export-glb.py                  # numpy + trimesh; exports six GLBs
```

Only regenerating the baked frame-data file requires `python scripts/prepare-frame-data.py` (Shapely 2.1). Normal HTML builds do not need Shapely or a CAD kernel.

No GitHub repository was modified. No load test, manufacturing release, actual hinge-fit approval, complete interference sweep or fixed-length cable simulation is included.
