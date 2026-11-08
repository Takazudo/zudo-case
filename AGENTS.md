# ZUDO CASE: local agent handoff

## Start here

This is a Japanese zudo-doc MDX documentation workspace for several independent case families. Read `README.md`, `project/release-state.json` and `src/content/docs/overview/status.mdx` before making changes, then the rules for the family you touch (for the metal family also `project/current-spec.json` and `src/content/docs/metal-case/status.mdx`). The user develops locally and will prepare physical confirmation and supplier orders. Do not send orders or approve manufacture without explicit authorization.

## Global rules (all families)

- Families are independent: metal case (`metal-case`, R6–R10), home-printed 5mm case (`printed-5mm`, P3–P5), independent two-frame 10BOX-v2 (`tenbox-v2`, R5), 2WAY study (`two-way`, F5/TW-01) and shared parts/source data (`shared`). A candidate in one family never changes another family's geometry, quantities, packages or order records.
- Nothing is production-approved. `engineering/release` has no approved files and `production_approved` stays `false`. Software checks, watertight meshes or browser previews are not physical validation or approval.
- Preserve design semantics, approval state, CAD, binaries, provenance, quantities and history. Keep old source folders/ZIPs and preserved manifests immutable; work in a new revision and record input/output hashes.
- Follow the source precedence order and the price discipline in the metal section; they apply to every family. Do not promote estimates, schematic previews or assistant commentary into measured or tested facts.
- Family-specific rules: metal case below; home-printed case in `engineering/printed-5mm/AGENTS.md`; 10BOX-v2 in `engineering/tenbox-v2/AGENTS.md`; 2WAY in `engineering/two-way/AGENTS.md`.

## Metal case family rules (3U60 / 7U40 / 7U60)

These rules apply to the metal family only. The interlocking-tab prohibition does not apply to the home-printed P5 family, whose J3 tab joints are adopted there (see `engineering/printed-5mm/AGENTS.md`).

### Preserve the adopted design

- Three metal-case models: `3u60`, `7u40`, `7u60`. Priority is `7u40` for backpack transport. 7U means 3U + 3U + 1U in ONE plane.
- Five independent aluminum plates, nominal 1.5mm, candidate A5052 black anodized. No old thick-panel interlocking tabs in the metal family.
- Existing 20×20×16mm metal L brackets. Thickness measured 2mm; 2.2mm is a modeling allowance, NOT a measured value.
- User wants positional tolerance absorbed by slotted holes + clamping. Do not demand exact matching round holes as the only solution. Slot directions and travel still need a manufacturing decision.
- Existing rail STLs: 40HP is 204mm long, 60HP is 305mm. Do not rescale one to make the other.
- Fixer and padder PCB thickness 1.6mm each; M5 flat head 1.4mm; spacer between fixer and case 8mm; outer washer 1mm. Head below padder is confirmed by user. Nut/screw details not otherwise measured are provisional.
- The detachable rail frame stays independent. Front/rear clearance is about 8mm to metal walls. Never fill it with a top bezel.
- Black PA12-HP dyed guards: 5mm cover, main 1.2mm version, 1.0mm comparison. Guards are not structural joints.
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

Use G01–G11 in `project/open-issues.json`: update R8 manufacturing geometry; implement slot tolerances; finalize guard retention and lid fit; confirm actual knob envelope and hardware; price black-anodized aluminum; choose/test straps; test assembly/transport. For the 7U40 R10-FULLSET-01 revision, prepare ONE full prototype set (six aluminum plates and twenty PA12 pieces) before physical evaluation. The 2026-10-26 user decision supersedes the earlier coupon-first workflow: no additional paid supplier samples or home washer tests gate preparation. Black ASA washers are editable home-print parts. Keep other models and families unchanged and preserve undecided items explicitly.

## Other families

- Home-printed 5mm (P3/P4/P5): `engineering/printed-5mm/AGENTS.md`. P5 is current; P4 (Uniform four-wall vents) and P3 (no vents) are history.
- 10BOX-v2 (R5): `engineering/tenbox-v2/AGENTS.md` and `project/tenbox-v2/manifest.json`. Independent two-frame 3U60HP case, not a P5 revision. Accepted geometry and saved print settings are fixed; physical/native validation remains unperformed.
- 2WAY (F5/TW-01): `engineering/two-way/AGENTS.md` and `project/two-way/`. F5 is immutable reference; TW-01 is the maintained workbench. It is separate from R9/R10, not a manufacturing release. Its 72/58 mm patch-gap assumptions do not replace the single-tray lid specification.
- Shared parts: the home-print 8mm spacer in `engineering/home-print-spacer-01/` (10mm OD / 5.5mm hole are provisional R6-derived values).
