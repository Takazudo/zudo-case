# tenbox-v2 family

## Current revision

Independent 10BOX-v2, two 3U60HP frames. **R8-LID-LEDGE-01 is the latest working revision**, selected after the user approved the connected lid ledges on 2026-11-24 (#149). Ongoing prototyping describes the whole 10BOX-v2 project. Do not restore the disconnected R8 lid or describe this accepted revision as awaiting selection.

Start with `README.md`, `project/tenbox-v2/current.json`, and the six current reader pages in `src/content/docs/tenbox-v2/`. `project/current-selection.json` references this current registry. `project/release-state.json` mirrors the current revision under its existing `current_tenbox_v2_candidate` key; the key name does not make selection pending. Preserve saved print settings, source notices, immutable inputs and receipts. Never change P5/metal/2WAY/shared assets or populate `engineering/release`. `production_approved` remains false.

## Current geometry and printing

The current case retains the R8 native lower elongated aluminium-frame slot (`frameHoleIndex: 1`), enclosure holes, 8mm spacers, rail mounting hardware and rail plane Z88.131103. Relative to R7, the three rails, four frames and four padders remain raised by the native slot spacing 12.631103mm.

Only the two central retaining-ledge gaps in each front/back lid panel change from R8. Fuse the approved bridges into the panel; preserve the outer L-bracket windows, mounting holes, lower locating tongue, original material and overall bounds. Front and back are one common shape rotated 180° around Z; the common STL/3MF is printed twice. The complete set keeps separately named `lid-front.3mf` and `lid-back.3mf`, each printed once.

Two lid H2D projects have replacement meshes, preserving their existing settings, filament mapping, brim/support overrides and placement. The remaining 13 projects are byte-identical to R8. All other 21 printed assembly parts and all assembly positions remain unchanged. The common floor is printed twice: 15 projects / 22 stored objects / 23 physical parts / 16 plate runs.

Retain the central nuts double rail, matching outer rails, side floor fixers and screw slots, 3mm side bracket clearance, all 52 L-bracket nuts inside, 8 independent rail-frame nuts outside, and complete fasteners. The retained roof underside at Z108 leaves 19.868897mm above the rail plane; the prior 27mm panel-plus-knob assumption exceeds this by 7.131103mm. The lid correction does not increase the inherited roof overlap. Preserve these measurements and distinguish software checks from physical confirmation.

## Build and evidence

Use the exact Python3.12.14/CadQuery2.7.0/NumPy2.3.5/SciPy1.17.0 environment locked in `r5/`. `pnpm build:tenbox-v2` runs the current full-set builder in `r8-lid-ledge-01/` into an absent disposable output directory. Read its README and `project/tenbox-v2/r8-lid-ledge-01.json` for regeneration, saved artifact hashes, quantities and evidence. Native Studio load/slice and physical print/fit/load remain unperformed; software checks do not change those facts.

R5's `project/tenbox-v2/manifest.json` is the frozen acceptance/input/hash contract consumed by later builders. Its `current_revision: r5` is historical. Keep all R5/R6/R7/R8 sources, receipts and packages, including fixed R4 STEP/model inputs, corrected H2D projects, renderer, native rails and exact print poses. The current incremental builder consumes the frozen R8 model and packages; do not overwrite them to make the current downloads look updated.

Versioned READMEs, ZIP READMEs and historical review records preserve their generation-time state. They are provenance records, not the current selection authority. The explicit decision in `current.json` selects the current connected lid without rewriting historical receipts or package bytes. Rebuilding historical artifacts must not reset this registry.

## Reader documentation

Follow `src/content/docs/development/maintenance.mdx`. The six current tenbox-v2 pages, ordinary navigation, direct lid downloads, full-set download links and primary preview show R8-LID-LEDGE-01. Superseded reader instructions and download links belong in `src/content/docs/archive/tenbox-v2/`, with historical banners and current links. Preserve canonical current routes and historical public asset URLs. Do not invent standalone R1–R4 reader pages or move frozen build dependencies into the reader archive.
