# tenbox-v2 family

## Current revision

Independent 10BOX-v2, two 3U60HP frames. **R8 is the latest working revision**, selected by the user on 2026-11-23 (#147). Ongoing prototyping describes the whole 10BOX-v2 project. Do not describe R8 as a separate candidate awaiting selection or restore R5 as current.

Start with `README.md`, `project/tenbox-v2/current.json`, and the six current reader pages in `src/content/docs/tenbox-v2/`. `project/current-selection.json` references this current registry. `project/release-state.json` mirrors R8 under its existing `current_tenbox_v2_candidate` key; the key name does not make R8 selection pending. Preserve geometry, saved print settings, source notices, immutable inputs and receipts. Never change P5/metal/2WAY/shared assets or populate `engineering/release`. `production_approved` remains false.

## Current R8 geometry and printing

Use the native lower elongated aluminium-frame slot (`frameHoleIndex: 1`). Relative to saved R7, retain the enclosure holes, 8mm spacers and rail mounting hardware; raise only the three rails, four frames and four padders by the native slot spacing12.631103mm to rail planeZ88.131103. All23 printed shapes and assembly positions match R7, and all15 H2D archives are copied byte-for-byte from R7. The common floor is printed twice: 15 projects / 22 stored objects / 23 physical parts / 16 plate runs.

Retain the central nuts double rail, matching outer rails, side floor fixers and screw slots, 3mm side bracket clearance, all52 L-bracket nuts inside, 8 independent rail-frame nuts outside, and complete fasteners. The unchanged lid roof underside atZ108 leaves19.868897mm above the rail plane; the prior27mm panel-plus-knob assumption exceeds this by7.131103mm. Report these dimensions without treating them as a pending revision-selection decision. A documentation update does not authorize geometry or print-setting redesign.

## Build and evidence

Use the exact Python3.12.14/CadQuery2.7.0/NumPy2.3.5/SciPy1.17.0 environment locked in `r5/`. `pnpm build:tenbox-v2` runs `r8/build.py` into an absent disposable output directory. Read `r8/README.md` for the generation-time method and `project/tenbox-v2/r8-review.json` for saved artifact hashes, quantities and evidence. Native Studio load/slice and physical print/fit/load remain unperformed; software checks do not change those facts.

R5's `project/tenbox-v2/manifest.json` is the frozen acceptance/input/hash contract consumed by later builders. Its `current_revision: r5` is historical. Keep all R5/R6/R7 sources, receipts and packages, including fixed R4 STEP/model inputs, corrected H2D projects, renderer, native rails and exact print poses. R8 also consumes the saved R7 model and print ZIP. These remain active build dependencies at their existing paths.

Versioned READMEs, ZIP READMEs and `r8-review.json` preserve the generation-time review/pending state. They are provenance records, not the current selection authority. The user decision in `current.json` supersedes their R5-current/R8-confirmation wording without rewriting those receipts or package bytes. Rebuilding historical artifacts must not reset the explicit current registry.

## Reader documentation

Follow `src/content/docs/development/maintenance.mdx`. The six current tenbox-v2 pages, ordinary navigation, download links and primary preview show R8. Superseded R5 reader instructions live in `src/content/docs/archive/tenbox-v2/`, with historical banners and current links. Preserve canonical current routes and historical public asset URLs. Do not invent standalone R1–R4 reader pages or move frozen build dependencies into the reader archive.
