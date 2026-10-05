# F5 validation record

2026-10-05 · **Software and nominal geometry only; not manufacturing approval.**

## Final checks

| Check | Result | Evidence |
|---|---:|---|
| Node source / frame / geometry suite | 117 passed, 0 failed | `tests/frame-results.tap` |
| Offline Chromium UI and responsive suite | 69 passed | `tests/browser-results.json` |
| GLB export and reload | 6 of 6 bounds and geometry-group comparisons passed | `models/manifest.json` |
| Final reference renders | No JavaScript errors | `previews/preview-render.json` |

Commands are in the root README. The final HTML was built with all three preview thumbnails embedded. Browser checks made no HTTP(S) requests. The tested renderer was the **software Canvas renderer**; WebGL was unavailable and its rendering path was not exercised.

The numerical suite verifies byte-identical Git blob identities for the two rail JSON copies, all source rail vertices and triangles, rigid transforms, PCB outside dimensions and layer thicknesses, source mounting datums, A/B/C component counts, the unchanged 7U board's old-48-mm lid failure, the new 70 mm C lid clearance, nominal locator clearances, finite geometry in eight views, configured closed envelopes, stand packing and export provenance. It also verifies the retained distinction between independent poses and a solved opening motion.

The browser suite exercises all three families and eight views, the side-layer separation control, the C lid error/recovery, display toggles, camera controls, keyboard orbit, expanded view, JSON save/load and rejection of the old F4 schema, PNG export, and page widths 320, 390, 768, 1200 and 1600 pixels. It checks visible warnings for inadequate patch clearance, removed retention straps and undersized trunk inputs.

The six GLBs are one source-frame inspection and one playing arrangement for each family. Reload comparisons check scene bounds and geometry-group counts. They do not establish watertightness, manufacturability or structural correctness.

## Known limitations

The exact source rail meshes retain the upstream duplicated/non-manifold surfaces. PCB outer vertices, mounting datums and padder coordinates follow the source, but rounded fixer cutouts are display approximations. Most hardware, protective covers and the tray's final bores remain schematic. Tests compare the geometry that is actually modeled, not unspecified future hardware.

There is no physical load, drop, retention, stability, thermal or electrical test. There is no complete continuous interference sweep, fixed-length cable simulation or validation that the purchased hinges fold the mounted spacer profiles flat. Numeric fit checks do not incorporate manufacturing tolerances, PCB bow, actual module protrusions or tool access.

`docs/archive-F4/` is historical background. Its dimensions and test counts do not apply to F5. No GitHub repository was modified.
