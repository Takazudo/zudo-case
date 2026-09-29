# R9-PROTOTYPE-01 verification and handoff

**Status:** unapproved 7U40 candidate. This record confirms repository evidence; it does not approve manufacture or record physical test success.

**Basis:** merged R9 base containing #94, #95, and the R9 image-ledger integration. The full clean-clone regeneration and central documentation build are still pending the integration manager's guarded run.

## Requirement coverage

| #80 completion item | Evidence and outcome |
|---|---|
| Independent candidate and regeneration steps | `engineering/r9-prototype-01/` contains a separate R9 generator, parameters, revisioned outputs, and input/output hashes. [README](./README.md) gives the locked-environment regeneration commands. The manager's stored CAD validation is available in [VALIDATION.md](./VALIDATION.md). **Deferred:** this worker did not run a fresh clone/worktree regeneration and byte-for-byte comparison; record that result after the manager's clean regeneration. |
| Slot roles, orientation, and range | [README](./README.md), `out/aluminum/hole-table.json`, `out/aluminum/slot-checks.json`, and `params/slots.json` record 36 bracket slots at 5.5 × 7.5 mm with ±1.0 mm candidate travel, their direction perpendicular to the joint bend line, and 10 round φ5.5 mm rail-fix holes. Final range, washer bearing, driver access, and hardware fit remain physical checks. |
| Guard and lid decisions | [Candidate design page](../../src/content/docs/design/r9-prototype-01.mdx), `params/guards.json`, and `params/lid.json` record the 1.2 mm primary guard, 1.0 mm comparison, separate fit and adhesive allowances, straight lift-off locating lid, and separate transport straps. Fit, adhesion, strap contact, and deflection are not established by the model. |
| Coupon files, quantities, comparisons, and records | `out/coupons/coupon-manifest.json` registers 14 labeled C1 guard/edge, C2 lid/top-edge, and C3 bracket-slot configurations (16 declared pieces; 31 STEP, 24 STL, 13 DXF files) with quantities, parameter comparisons, and SHA-256 values. The bundle is `public/downloads/candidate/7u40-r9-prototype-01-coupons-NOT-APPROVED.zip`. The comparison variants include guard clearance/thickness/adhesive, lid locator clearance, and slot length versus a round hole. The result fields remain null. [Fit procedure](../../src/content/docs/verification/fit-test.mdx), the blank [coupon record](../../src/content/docs/verification/coupon-record.mdx), and [measurement record](../../src/content/docs/verification/measurements.mdx) hand physical checks to the user. |
| BOM, CAD, preview, and ledger use one revision | `project/current-spec.json`, `project/release-state.json`, `out/outputs-manifest.json`, `out/validation.json`, `out/bom.json`, `out/coupons/coupon-manifest.json`, and the standalone preview all identify `R9-PROTOTYPE-01`. The output manifest records 217 generated files; the candidate ledger registers 141 CAD/package/preview files and hashes. `node scripts/sync-r9-ledger.mjs --check` verifies ledger agreement. |
| Mesh, dimensions, holes, interference, and lift path | Stored CAD validation reports **156 pass, 14 flags, 0 fail** in `out/validation.json` and [VALIDATION.md](./VALIDATION.md). It records five independent body plates plus one lid plate, 46 hole locations (36 slots and 10 round holes), 56 R9 STL checks against STEP, 64 STEP reimports, 17 DXF reimports, and two temporary parameter-change checks. Flags document the provisional 10 mm washer's bearing failure at 26 wall slots, partial solid-pair interference and lift-path coverage, unvalidated physical fastener access, and schematic strap contact/deflection. See the validation record for the full scope and all unverified areas. |
| Repository checks | Worker checks: see the results recorded below after the focused docs, tables, assets, setup, ledger, R9 manifest, and confirmation checks. **Pending:** the integration manager's guarded `pnpm build`, built-preview-link check, and full worker-assets suite. They are not reported as passed here. |
| Physical tests and supplier handoff | C1/C2/C3 result fields and the record sheets are blank. No supplier order, paid prototype order, or manufacture approval was made. Physical coupon fit, one-case assembly, real module/knob clearance, strap selection/tension, and transport checks remain with the user. |
| No fabricated results or approvals | G01–G11 remain `open` with `result: null`; `production_approved` is `false`; `published_release_files` is empty; `engineering/release/` contains only its README. Candidate prices remain unquoted/null. No physical result is represented as passed. |

## Preservation and file checks

- The protected R6, R8, archived R7, and release paths have no changes relative to `main`. All pre-existing `project/artifact-manifest.json` entries are unchanged; only candidate records are appended.
- The `3u60` and `7u60` objects in `project/current-spec.json` and their generated model pages are byte-for-byte unchanged from `main`.
- The preview rail is the saved 40HP source STL: SHA-256 `88a153fe717f582f80656fe10c74df5ec1717f53e6b202fff078532b00b06c5a`, 29,684 bytes, with a measured source long axis of 204 mm. The R9 preview does not rescale it.
- The generated R9 preview is a single HTML file with inline scripts and no external script or stylesheet references. The manager's browser record reports `passed`, `noNetworkRequests: true`, an empty network request list, no console/page errors, and successful daily, travel, lid-open, and 390 px viewport checks. I visually reviewed the saved daily, travel, and lid-open mobile screenshots; they show the intended states without an obvious rendering issue. Screenshots are listed by hash in `out/outputs-manifest.json`. This is a preview review, not a physical-fit result.
- Every R9 candidate output and every file added or changed on the R9 branch is below 25 MiB. The largest changed file is `out/hardware-envelopes/7u40-r9-pcb-fixer-qty2-mm.step` at 12,774,700 bytes. Existing unchanged legacy assets are outside this R9 file-size check.

## Pending manager integration correction

`CONTRACTS.md` still describes geometry modules and candidate ZIPs as future/reserved work. That prose is stale now that the modules and ZIPs exist. Its current SHA-256 (`b4555a85df738324e8f6b3e85c45ea9f8cbee40e8569d4f672396fab85ff80e0`) is recorded as a generator input in `out/outputs-manifest.json`, so this worker left it unchanged. The integration manager will update the wording after this commit, regenerate the package/output manifest, sync the artifact ledger, and run the affected checks on the shared base.

## Check results

| Check | Result |
|---|---|
| `pnpm check:docs` | Passed: 45 MDX pages, 8 categories, 165 internal links. Generated navigation/static-check records were restored in this topic worktree for the manager's integration commit. The command does not compile MDX. |
| `pnpm check:tables` | Passed: generated model and comparison tables match `project/current-spec.json`. |
| `pnpm check:assets` | Passed: 465 assets, 262,917,773 bytes, SHA-256 identity matched. |
| `pnpm test:setup` | Passed: 7 tests. |
| `pnpm test:ledger` | Passed: 100 tests. |
| `pnpm check:r9` and `pnpm check:r9-ledger` | Passed: all 217 generated output hashes verified; 141 candidate ledger entries match, including 11 lid files. |
| `pnpm test:r9` | Passed: 1 manifest mutation test. |
| `node --test tests/preview-links.test.mjs tests/preview-origin-isolation.test.mjs` | Passed: 8 tests. |
| `pnpm check:r9-confirm` | Passed: preserved protected paths and pre-existing artifact entries; confirmed other-model state, revision/gate/release state, rail provenance, preview evidence, and sub-25 MiB changed files. |
| `CONTRACTS.md` input hash and output-manifest refresh | Pending integration manager correction after this topic commit. |
| Clean worktree regeneration, guarded docs build, built-link check, and worker-assets suite | Pending integration manager run. |
