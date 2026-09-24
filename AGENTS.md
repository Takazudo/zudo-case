# ZUDO CASE: local agent handoff

## Start here

This is a Japanese zudo-doc MDX documentation workspace for a case family. Read `README.md`, `project/current-spec.json`, `project/release-state.json`, and `src/content/docs/overview/status.mdx` before making changes. The user develops locally and will prepare physical confirmation and supplier orders. Do not send orders or approve manufacture without explicit authorization.

## Preserve the adopted design

- Three models: `3u60`, `7u40`, `7u60`. Priority is `7u40` for backpack transport. 7U means 3U + 3U + 1U in ONE plane.
- Five independent aluminum plates, nominal 1.5mm, candidate A5052 black anodized. No old thick-panel interlocking tabs.
- Existing 20×20×16mm metal L brackets. Thickness measured 2mm; 2.2mm is a modeling allowance, NOT a measured value.
- User wants positional tolerance absorbed by slotted holes + clamping. Do not demand exact matching round holes as the only solution. Slot directions and travel still need a manufacturing decision.
- Existing rail STLs: 40HP is 204mm long, 60HP is 305mm. Do not rescale one to make the other.
- Fixer and padder PCB thickness 1.6mm each; M5 flat head 1.4mm; spacer between fixer and case 8mm; outer washer 1mm. Head below padder is confirmed by user. Nut/screw details not otherwise measured are provisional.
- The detachable rail frame stays independent. Front/rear clearance is about 8mm to metal walls. Never fill it with a top bezel.
- Black PA12-HP dyed guards: 5mm cover, main 1.2mm version, 1.0mm comparison. Guards are not structural joints.
- Adopted lid is a straight lift-off 10BOX-style locating lid, aluminum sheet + PA12 frame. NO lid/body M3 locks, rear hooks, sliders, rotary locks or magnets. Two removable external straps hold it during transport. Plate/frame assembly screws are separate and may remain.
- Lid rise30mm, module panel2mm+knob25mm, cables removed are provisional assumptions, not validation for every module.

## Source precedence and status

1. Explicit user decisions and confirmed measurements: `project/source-notes/user-decisions.md`.
2. Saved source STL / KiCad + pinned source commits.
3. Versioned generated CAD and its manifests.
4. Schematic preview, old commentary, or estimates — do not promote these into measured or tested facts.

`engineering/r6-body` is the existing body geometry starting point. R6 still has nominal round holes and no final guard fit/retention.
`engineering/r8-preview` is the adopted LID CONCEPT only; it does not export current manufacturing STL/STEP/DXF.
R7 in `public/downloads/archive` is an obsolete screw-lock lid. Its added body holes and locking parts are not adopted.
`engineering/release` currently has no approved manufacturing files. Do not populate it merely because a mesh is watertight or a browser preview looks correct.

## Price discipline

Actual user screenshot: old R3 t1.2 body guards12pcs total JPY2264, dyed black. Tax not shown; shipping not included in the screenshot. It is not the current case or lid quote.
Old aluminum prices and 11–13k / 14–17k / 17–21k body budgets were assistant estimates/reports with incomplete evidence. Keep this distinction.
Unquoted current totals are null, not0. Rail unit manufacturing cost is excluded by request; existing stock brackets have zero incremental cash but nonzero product cost when known.

## How to edit

Author Japanese MDX in `src/content/docs`. Every category has a short `index.mdx` with `CategoryNav`. Keep `title`, `description`, and numeric `sidebar_position` frontmatter. No extra H1. Use relative `.mdx` links for docs and `/images` etc for public files.
Five pages are generated: models3 + comparison + BOM. Update `project/current-spec.json`, then `node scripts/sync-reference-tables.mjs`; do not hand-edit generated rows.
This JSON is a DOCUMENT registry, not the input to the CAD generator. Changes must separately reach the CAD, preview, outputs, then be verified.
Keep old source folders/ZIPs immutable where possible. Work in a new revision and record input/output hashes. References inside source manifests can be relative to their original source folder.

## Checks and dependencies

`node scripts/check-docs.mjs` — static content, link existence, dimension/count arithmetic.
`node scripts/verify-assets.mjs` — incoming-source/asset byte identity.
`node --test tests/setup.test.mjs` — mock scaffold integration tests.
After local official setup and installation: `pnpm build` and real browser tests.
Do not claim these static checks constitute MDX compilation, FEA, fit, drop, fatigue, or load testing.
The initial environment could not resolve npm. `scripts/setup.mjs` generates an OFFICIAL fresh scaffold locally then integrates framework files without overwriting authored MDX/config/assets. No fabricated dependency pins are included.

## Next engineering work

Use G01–G11 in `project/open-issues.json`: update R8 manufacturing geometry; implement slot tolerances; finalize guard retention and lid fit; confirm actual knob envelope and hardware; price black-anodized aluminum; choose/test straps; test assembly/transport. Start with small fit pieces and 7u40, then apply proven common changes to other models. Preserve undecided items explicitly.
