# First-party maintenance #120 — 2026-10-14

Specification: [#120](https://github.com/Takazudo/zudo-case/issues/120), with [#105](https://github.com/Takazudo/zudo-case/issues/105) retained as migration/rollout history. Base: `a254c89869e73202ce38d750ce738d8a21681848`. One branch: `chore/first-party-maintenance`; one PR to main. No deployment, publication, CAD upgrade or manufacturing approval is part of this work.

## Dependency and scaffold evidence

The public resolver at `Takazudo/claude-settings@f957ad2c293c297bdd8cfefd244f9c5ecf8ca4cb` (`skills/dev-bump-zudo-deps/scripts/resolve-bumps.mjs`) was inspected and run read-only before write-back. It scanned both manifests: root `package.json`/`pnpm-lock.yaml`, and independent `engineering/two-way/tw-01/tests/browser/package.json`/`package-lock.json`. The latter declares only Playwright 1.58.2, was installed with `npm ci`, and its manifest/lockfile are unchanged. Five stable first-party declarations were found; no tag, floating, non-registry, stale-tag or graduation rows.

| Package | Locked old | Resolved stable / installed new | Published impact |
| --- | --- | --- | --- |
| zfb | 2.20.2 | 4.5.0 (exact) | Owned zudo-react/Wind replace Preact/Tailwind; exports/config and CLI contracts reviewed |
| zfb-runtime | 2.20.2 | 4.5.0 (exact) | Owned renderer, exact zfb peer, React peer removed |
| zfb-md-wasm | 2.20.2 | 4.5.0 (exact) | Owned JSX compile target; retired jsxRuntime; new workerd/artifact exports; no direct host calls |
| zudo-doc | 5.27.0 | 6.2.0 (`^6.2.0`) | zfb ^4.5.0 peers; Preact peer and safelist CSS removed; mdxExtras retained; relative TS aliases |
| zudo-doc-history-server | 5.27.0 | 6.2.0 (exact) | Published diff changes package version/changelog only; history remains disabled |
| create-zudo-doc (copied) | 5.27.0 | 6.2.0 | Route/CSS/TS configuration and esbuild install allowlist reconciled |

Names above abbreviate `@takazudo/`, except create-zudo-doc. Each old-to-new published artifact received an `npm diff --diff-name-only` survey and targeted manifest/export/peer/config/TS/scaffold diff. Relevant released changelogs and the released v6 migration guide were read. This was a public-interface assessment, not a full audit of binary/Wasm or all internal implementation changes.

Version-specific npm gitHead was absent for the five runtime packages; fetched exact release tags verified their source endpoints instead: zfb `7c0b46ec46480dc99f8601172245350cc16e019b` → `dcf1e9235882e365a63cee9d551c58c9f0c19107`; zudo-doc `50cbd5c6c9e5a795d72a74a855e105e4939d4eab` → `6542b8300f4a554247563a3bac53e415a63ded51`. Both create-zudo-doc gitHeads exist and match the corresponding tags. Tag provenance does not assert tarball/tree byte equality.

Both pinned official scaffolds were generated outside the checkout with the existing setup preset, no install and no Git initialization. Every originally copied local file matched regenerated 5.27.0. Four copies changed: doc route, global CSS, tsconfig and pnpm workspace. Favicons, index route, .npmrc and check-links were identical and retained. `ZUDO_DEPS_PINS.md` and `.handoff/maintenance-scaffold-6.2.0.json` record the new source and file hashes. `.handoff/setup-record.json` remains historical and unchanged.

Node 24.19.0 / explicitly selected pnpm 10.30.3 were used. TypeScript stays 5.9.3; Wrangler stays 4.138.0. Direct Preact packages were removed after porting both preview-links and two-way-table. Other supporting lock changes include the required zfb-slugify 4.5.0 and smol-toml 1.9.1. A disposable directory with no node_modules passed a frozen install and retained the identical root lockfile.

## Runner decision and upstream workarounds

Retain the unique per-run mirror. Real direct `--scratch-dir`/`--define` invocation preserves origins on separate ports during a concurrent build, but reads mutable checkout inputs; it does not supply the existing build/check code/config snapshot contract. Mock tests retain the snapshot assertions; the real CLI suite additionally edits source during a build and verifies old snapshot output, concurrent-build rejection, three live dev origins, source edits/additions/deletions, config restart, public asset updates/deletion, preview serving and cleanup.

Build output is protected by `.cache/site-build.lock`. Invalid preview-origin overrides still fail before child/run-directory creation. Generated wrapper definitions retain authored defines. Relevant authored-config edits restart the native dev process on the same port and origin. Public preview/download bytes remain live; public Asset Viewer bytes are synchronized into each dev's native asset directory. Explicit scratch selection waits for native readiness/validation before writing there.

Two upstream defects have reduced public-package reports:

- [zfb #4232](https://github.com/Takazudo/zudo-front-builder/issues/4232): multiline MDX table compilation inserts paragraphs between explicit table sections. The generated R9 table is now a JSX expression with the same Japanese text/data and package-equivalent table/overflow classes. Its generator and checked output changed together.
- [zfb #4233](https://github.com/Takazudo/zudo-front-builder/issues/4233): dev's reserved /assets namespace omits live public/assets without a dist seed. Per-invocation asset synchronization is a verified workaround dependent on the pinned native scratch layout. Re-evaluate it when upgrading the engine.

## Baseline and final verification

Baseline frozen install, host check and guarded build passed: native build 73 pages, 53 search entries, 78 HTML files including copied public HTML. Representative overview/current-preview/files screenshots and computed styles were captured at 1440×900, 390×844 and 320×844. The initial broad baseline unit invocation preceded asset preparation: 147 passed and one module-prerequisite failure; after proper preparation the full unit suite passed 151/151.

The following local command ledger and browser record describe observed results; GitHub current-head CI is verified separately in the PR. Non-deploying integration requires current-head CI and review/policy checks, a final main commit containing `[skip deploy]`, and observed skipped deployment. An unmerged draft is not integration; local GETs are not production rollout verification. #105's production/full-GET criteria remain separate.

## Observed command ledger

- `pnpm install --frozen-lockfile` — PASS
- `pnpm test:two-way` — PASS
- `pnpm check:two-way` — PASS
- `pnpm check:docs` — PASS
- `pnpm check:r9` — PASS
- `pnpm check:fitfix` — PASS
- `pnpm check:fit-test-order` — PASS
- `node --test tests/order-map.test.mjs` — PASS
- `pnpm check:r9-ledger` — PASS
- `pnpm check:r9-doc-table` — PASS
- `pnpm test:r9` — PASS
- `node --test tests/preview-links.test.mjs tests/preview-origin-isolation.test.mjs` — PASS
- `pnpm check:tables` — PASS
- `pnpm check:assets` — PASS
- `pnpm test:setup` — PASS
- `pnpm test:ledger` — PASS
- `pnpm check` — PASS
- `pnpm exec zfb wind audit --fail-on error` — PASS
- `node --test tests/prepare-worker-assets.test.mjs tests/verify-deployed-assets.test.mjs` — PASS
- `pnpm build` — PASS
- `pnpm check:built-preview-links` — PASS
- `pnpm check:images` — PASS
- `pnpm prepare:worker-assets` — PASS
- `node --test tests/worker-assets.test.mjs tests/worker-assets-deployment.test.mjs` — PASS
- `node --test tests/*.test.mjs` — PASS
- `pnpm check:preview-isolation` — PASS

The full unit suite passed 151 tests. Wind audit uses the selected CLI’s supported `--fail-on error` gate. Build reports 73 pages and 53 search entries; built preview validation finds 40 production URLs in 53 docs pages. Image validation checks 78 HTML files and 33 local references. Worker tests reconstruct the real chunked R6 HTML and R7 ZIP and match original byte counts/SHA-256, alongside fixture failure tests. Root lockfile is the only dependency lockfile changed.

The untouched CAD workflow was reproduced in a disposable detached worktree using locked Python 3.12.14 / CadQuery 2.7.0. R9 validation/regeneration, package generation/repeatability and unchanged-output Git comparison passed; fitfix 11 tests, disposable fitfix generation/body-DXF comparison, anodizing 9 mutation/regression tests, and all 13 original/revised mesh pairs passed. The guarded aggregate verdict was PASS. No regenerated engineering outputs were committed.

## Browser and preservation evidence

Chromium 151.0.7922.173: 63 host page cells (seven routes × three origins × 1440×900 / 390×844 / 320×844) and 40 interaction/download checks passed, with zero page errors and zero document overflow. Routes: overview/start, overview/status, resources/current-preview, files, design/r9-prototype-01, design/r9-fitfix-01 and two-way/preview. Japanese search, Appearance dark mode, mobile navigation, asset-viewer links, loaded image bytes, iframe origins/border/radius and candidate ZIP download were checked. The body font stays `system-ui, sans-serif`, matching the baseline. Screenshots were captured and inspected. Six additional image-enlargement/Japanese-search-navigation cells (three origins × desktop/narrow) passed: the image dialog opened/closed via Escape and a Japanese search result navigated to its actual route, with no page errors.

Production-built pages ran on a local static server. Their production preview URLs were intercepted to the unchanged local public bytes; this verifies URL selection and rendering, **not deployed production hosts**. Local/override dev used actual local public serving. Eighteen additional standalone preview cells (R6, R8, R9 prototype, R9 fitfix, order-map/anodizing and TW-01 × 1440/390/320) passed with loaded canvases, representative select controls, no page errors and no overflow. Observed renderer: ANGLE Vulkan **SwiftShader**, using WebGL; no hardware GPU pass is claimed.

The existing two-way browser suite passed 59 checks per cell in both forced software fallback and WebGL/ANGLE SwiftShader modes, over local HTTP with unchanged TW-01 HTML. This includes all families/poses, 320/390/768/1200/1600 widths, import/export/keyboard interactions and PNG downloads. The blocked Playwright CDN download was replaced by the available system Chromium through the documented TW_CHROMIUM selection; the browser package stays locked at 1.58.2.

989 protected files were hashed before editing. All public assets, engineering/source geometry, F5, current-spec, release-state and the historical setup receipt remain byte-identical. The only changed protected text is the generated R9 table’s two structural wrapper lines; its text, rows and source data are unchanged. No approval state, G01–G11, quotes or unrelated issues changed.

Two diff-review passes checked host/scaffold interfaces and runner lifecycle/isolation. Review corrected retention of a pending public-asset deletion across a config restart; the final real CLI suite tests config restart plus deletion on default and explicitly selected scratch directories. All current runner assertions pass; the second pass found no remaining actionable defect. Native scratch layout and imported-config restart remain documented compatibility workarounds.
