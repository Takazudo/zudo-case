# ZUDO CASE: local agent handoff

## Start here

This is a Japanese zudo-doc MDX documentation workspace for several independent case families. Read `README.md`, `project/current-selection.json` (the per-project current revision; never pick by highest number or newest date), `project/release-state.json` and `src/content/docs/overview/status.mdx` before making changes, then the rules for the family you touch (for the metal family also `project/current-spec.json` and `src/content/docs/metal-case/status.mdx`). The user develops locally and will prepare physical confirmation and supplier orders. Do not send orders or approve manufacture without explicit authorization.

## Global rules (all families)

- Families are independent: metal case (`metal-case`, R6–R11; 7U40 current R11-BUILD-FEEDBACK-04, 3U60/7U60 current R6 body + R8 lid concept), home-printed 5mm case (`printed-5mm`, current P5; P4/P3 archived), independent two-frame 10BOX-v2 (`tenbox-v2`, R5), 2WAY study (`two-way`, F5/TW-01) and shared parts/source data (`shared`). A candidate in one family never changes another family's geometry, quantities, packages or order records.
- Nothing is production-approved. `engineering/release` has no approved files and `production_approved` stays `false`. Software checks, watertight meshes or browser previews are not physical validation or approval.
- Preserve design semantics, approval state, CAD, binaries, provenance, quantities and history. Keep old source folders/ZIPs and preserved manifests immutable; work in a new revision and record input/output hashes.
- Follow the source precedence order and the price discipline in the metal section; they apply to every family. Do not promote estimates, schematic previews or assistant commentary into measured or tested facts.
- Documentation lifecycle: ordinary docs and discovery show only the current state from `project/current-selection.json`; superseded reader content lives in `src/content/docs/archive/<family>/` (see the canonical policy's 「現行とアーカイブ」). Current-version inputs (10BOX-v2 fixed R4 inputs, 2WAY F5, shared rails/PCB) are not archived for being old.
- Family-specific rules: metal case below; home-printed case in `engineering/printed-5mm/AGENTS.md`; 10BOX-v2 in `engineering/tenbox-v2/AGENTS.md`; 2WAY in `engineering/two-way/AGENTS.md`.

## Metal case family rules (3U60 / 7U40 / 7U60)

These rules apply to the metal family only. The interlocking-tab prohibition does not apply to the home-printed P5 family, whose J3 tab joints are adopted there (see `engineering/printed-5mm/AGENTS.md`).

### Preserve the adopted design

- Three metal-case models: `3u60`, `7u40`, `7u60`. Priority is `7u40` for backpack transport. 7U means 3U + 3U + 1U in ONE plane.
- Five independent aluminum body plates plus the lid sheet (six sheets in the 7U40 R11 set), nominal 1.5mm, candidate A5052 black anodized. No old thick-panel interlocking tabs in the metal family.
- Existing 20×20×16mm metal L brackets (16 retained in the current 7U40 R11 set). Thickness measured 2mm; 2.2mm is a modeling allowance, NOT a measured value.
- User wants positional tolerance absorbed by slotted holes + clamping. Do not demand exact matching round holes as the only solution. Slot directions and travel still need a manufacturing decision.
- Existing rail STLs: 40HP is 204mm long, 60HP is 305mm. Do not rescale one to make the other.
- Fixer and padder PCB thickness 1.6mm each; M5 flat head 1.4mm; spacer between fixer and case 8mm; outer washer 1mm. Head below padder is confirmed by user. Nut/screw details not otherwise measured are provisional.
- The detachable rail frame stays independent. Front/rear clearance is about 8mm to metal walls. Never fill it with a top bezel.
- Black PA12-HP dyed guards, 5mm cover. R6–R10 history (keep in that context only): main 1.2mm version with a 1.0mm comparison, and "guards are not structural joints".
- Current 7U40 R11-BUILD-FEEDBACK-04 (`engineering/r11-build-feedback-04/`, read its README and `source/parameters.json`): 1.0mm nominal PA12 guard/connector wall; nylon locating/overlap connectors set panel positions (0.8mm separator in the 1.0mm sheet-edge gap) while the 16 metal L brackets are retained as reinforcement; 40 body slots 15.5×5.5mm (one-sided 5mm inward extension); 64 OD15/ID5/t1 black ASA washers; 20 PA12 pieces (12 body + 8 lid) with four-sided lid locating skirts. This is a nominal-CAD review candidate, not a structural-strength claim, physical validation or manufacturing approval. R10-FULLSET-01 and earlier 7U40 candidates are history.
- Adopted lid is a straight lift-off 10BOX-style locating lid, aluminum sheet + PA12 frame. NO lid/body M3 locks, rear hooks, sliders, rotary locks or magnets. Two removable external straps hold it during transport. Plate/frame assembly screws are separate and may remain.
- Lid rise30mm, module panel2mm+knob25mm, cables removed are provisional assumptions, not validation for every module.

### Source precedence and status (general order; metal examples)

1. Explicit user decisions and confirmed measurements: `project/source-notes/user-decisions.md`.
2. Saved source STL / KiCad + pinned source commits.
3. Versioned generated CAD and its manifests.
4. Schematic preview, old commentary, or estimates — do not promote these into measured or tested facts.

`engineering/r6-body` is the existing body geometry starting point. R6 still has nominal round holes and no final guard fit/retention.
`engineering/r8-preview` is the adopted LID CONCEPT only; it does not export current manufacturing STL/STEP/DXF.
R7 in `public/downloads/archive` is an obsolete screw-lock lid. Its added body holes and locking parts are not adopted.
`engineering/release` currently has no approved manufacturing files. Do not populate it merely because a mesh is watertight or a browser preview looks correct.

### Price discipline

Actual user screenshot: old R3 t1.2 body guards12pcs total JPY2264, dyed black. Tax not shown; shipping not included in the screenshot. It is not the current case or lid quote.
Old aluminum prices and 11–13k / 14–17k / 17–21k body budgets were assistant estimates/reports with incomplete evidence. Keep this distinction.
Unquoted current totals are null, not0. Rail unit manufacturing cost is excluded by request; existing stock brackets have zero incremental cash but nonzero product cost when known.

## How to edit the docs

Before adding a page, changing its role, or changing categories, read `src/content/docs/development/maintenance.mdx`, the one canonical editorial policy. It owns the readers/tasks, category boundaries, placement questions, structure-review procedure, generated ownership and URL/navigation exceptions. Typo, wording and formatting fixes skip the structure check. README and CLAUDE point to this same policy; do not add a competing AUTHORING.md or duplicate it here.

Preserve the family engineering instructions above and below. Generated content is edited through its declared source and generator, including `project/doc-routes.json` for compatibility pages and ownership. A document registry is not a CAD generator input: geometry, preview, outputs and verification require their own work. References inside source manifests can remain relative to their original source folder.

## Checks and dependencies

`node scripts/check-docs.mjs` — static content, link existence, sibling ordering, route map, dimension/count arithmetic.
`node scripts/sync-doc-routes.mjs --check` and `node --test tests/doc-structure.test.mjs` — compatibility pages and section ownership; after `pnpm build`, `pnpm check:built-doc-routes` crawls the built HTML.
`node scripts/verify-assets.mjs` — incoming-source/asset byte identity.
`node --test tests/setup.test.mjs` — mock scaffold integration tests.
After local official setup and installation: `pnpm build` and real browser tests.
Do not claim these static checks constitute MDX compilation, FEA, fit, drop, fatigue, or load testing.
The initial environment could not resolve npm. `scripts/setup.mjs` generates an OFFICIAL fresh scaffold locally then integrates framework files without overwriting authored MDX/config/assets. No fabricated dependency pins are included.

## Next metal engineering work

Use G01–G11 in `project/open-issues.json`; those holds remain open: update R8 manufacturing geometry; implement slot tolerances; finalize guard retention and lid fit; confirm actual knob envelope and hardware; price black-anodized aluminum; choose/test straps; test assembly/transport.

For 7U40 the current candidate is R11-BUILD-FEEDBACK-04 (six aluminum sheets, twenty PA12 pieces, 64 home-printed ASA washers, 16 retained metal L brackets). Its checks are nominal-CAD and data/hash checks only: physical build, fit, tightening, load and transport remain open, and all prices are unquoted (null). Do not upload, request quotes or order from any supplier without the user's explicit authorization. The 2026-10-26 user decision still applies: no coupon-first workflow, no additional paid supplier samples or home washer tests gate preparation; black ASA washers are editable home-print parts. Keep other models and families unchanged and preserve undecided items explicitly.

R10 history (context only): the earlier plan was to prepare ONE R10-FULLSET-01 prototype set (six aluminum plates and twenty PA12 pieces) before physical evaluation; that set and its JLC cart record are archived and superseded by R11-BUILD-FEEDBACK-04.

## Other families

- Home-printed 5mm (P3/P4/P5): `engineering/printed-5mm/AGENTS.md`. P5 is current; P4 (Uniform four-wall vents) and P3 (no vents) are archived reader history (`src/content/docs/archive/printed-5mm/`), with their sources and payloads preserved.
- 10BOX-v2 (R5): `engineering/tenbox-v2/AGENTS.md` and `project/tenbox-v2/manifest.json`. Independent two-frame 3U60HP case, not a P5 revision. Accepted geometry and saved print settings are fixed; physical/native validation remains unperformed.
- 2WAY (F5/TW-01): `engineering/two-way/AGENTS.md` and `project/two-way/`. F5 is immutable reference; TW-01 is the maintained workbench. It is separate from the metal family (including the current 7U40 R11 candidate), not a manufacturing release. A/B/C are all current comparisons; F5 is TW-01's input, not a competing current version. Its 72/58 mm patch-gap assumptions do not replace the single-tray lid specification.
- Shared parts: the home-print 8mm spacer in `engineering/home-print-spacer-01/` (10mm OD / 5.5mm hole are provisional R6-derived values).
