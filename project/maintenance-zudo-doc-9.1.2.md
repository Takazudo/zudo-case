# zudo-doc 9.1.2 upgrade and project-oriented documentation — 2026-11-06

Base: `main` at `00eeb4011b5e8270ed023ec5eacbc1dbb4686e99`. One branch and one PR to `main`, with separate upgrade and restructure commits. No deployment, release, supplier communication, order, CAD regeneration or manufacturing approval is part of this work. The 6.2.0 record (`project/maintenance-120.md`, `.handoff/maintenance-scaffold-6.2.0.json`) and the original setup receipt (`.handoff/setup-record.json`) are unchanged history.

## Selected tuple (frozen at implementation start, 2026-11-06T07:22Z)

| Package | Before | Selected | Range in package.json |
| --- | --- | --- | --- |
| @takazudo/zudo-doc | 6.2.0 | 9.1.2 | `^9.1.2` (dependency, caret kept) |
| @takazudo/zudo-doc-history-server | 6.2.0 | 9.1.2 | exact (devDependency, kept for assetViewer) |
| create-zudo-doc (scaffold source) | 6.2.0 | 9.1.2 | not installed; `scripts/setup.mjs` default |
| @takazudo/zfb | 4.5.0 | 5.2.0 | exact |
| @takazudo/zfb-runtime | 4.5.0 | 5.2.0 | exact |
| @takazudo/zfb-md-wasm | 4.5.0 | 5.2.0 | exact |
| Node.js floor | >=22 | >=24 | `engines.node` |
| pnpm | 10.30.3 | 10.30.3 | `packageManager` |

Evidence (npm registry, read at start):

- dist-tag `latest`: zudo-doc, history-server and create-zudo-doc are 9.1.2.
- create-zudo-doc 9.1.2 `gitHead` is `4b5b54e3e0f383cfbf1e7b6038c6b65ee7c5f9d2`. Integrities for every selected tarball and the installed `@takazudo/zfb-linux-x64-gnu` 5.2.0 binary are in `.handoff/maintenance-scaffold-9.1.2.json` and match `pnpm-lock.yaml`.
- zudo-doc 9.1.2 peers: `@takazudo/zfb`, `zfb-runtime` and `zfb-md-wasm` `^5.2.0`, history-server `^9.0.0`, zod `^4.3.6` (installed 4.6.5). Engines: zudo-doc, create-zudo-doc, zfb and zfb-runtime require Node >=24; zfb-md-wasm requires >=20; zfb requires pnpm >=10. `pnpm install` reported no unmet peer.
- The regenerated official 9.1.2 scaffold pins the zfb family to exact 5.2.0.
- zfb and zfb-runtime 5.2.2 appeared at 07:21Z and zfb-md-wasm 5.2.2 at 07:23Z, around implementation start. They were not adopted: the official scaffold pins 5.2.0 and the three-package family was not complete when the tuple was frozen.
- Published platform binaries were used; no Rust build and no unpublished branch.

Frozen install: a disposable copy containing only the manifest, lockfile, workspace file and `.npmrc` passed `pnpm install --frozen-lockfile` and left the lockfile byte-identical.

## Migration review (7.x, 8.x, 9.x changelog in the published 9.1.2 package)

- 7.0.0 Node 24: engines and the `scripts/setup.mjs` check now require 24; CI already used Node 24.
- 7.0.0 zfb 4.5.2 live `public/assets/` dev serving: the runner's per-run asset synchronization (originally for zudo-front-builder#4233) is retained unchanged; the real-CLI suite still passes with it.
- 8.0.0 optional-peers plugin export removed: the repository contains no registration, so nothing was removed.
- 8.x/9.x zfb floors: engine, runtime and Markdown WASM moved together.
- 9.0.0 default theme pack changed to Graphite: `themePack: "default"` is now explicit in `zfb.config.ts` (Classic look kept; `setup.preset.json` already had it).
- 9.1.0/9.1.1 `categoryMatch` whole-segment and `foo-*` satellite ownership: used when defining the new header sections (no section name is a dash prefix of another).
- Not enabled: Cloudflare adapter, MCP, docHistory, dynamic transitions. Wrangler stays 4.138.0. `noindex`, assetViewer and its index, image enlarge and the chrome bindings are unchanged.

## Scaffold reconciliation

`create-zudo-doc@6.2.0` and `@9.1.2` were generated into a disposable directory with `--preset <checkout>/setup.preset.json --no-install --no-git --yes`. Setup was not run over the checkout.

All eleven copied files (`.npmrc`, both routes, `pnpm-workspace.yaml`, four favicons, `scripts/check-links.js`, `src/styles/global.css`, `tsconfig.json`) are byte-identical in old upstream, the checkout and new upstream. None were replaced. The other generated differences were the manifest (Node and package versions, applied) and `themePack: "default"` in the generated config (applied to the authored config). The generated CLAUDE.md and starter MDX were not imported.

`scripts/setup.mjs` now defaults to 9.1.2, prints the default and the Node floor in `--help`, and rejects Node below 24. `tests/setup.test.mjs` uses 9.1.2 where it intentionally models the current pinned CLI and adds a guard that the default CLI, history-server and Node floor match `package.json`.

## Upgrade checkpoint (before any documentation move)

Local environment: Node 24.22.2, pnpm 10.30.3, Chromium from the preinstalled Playwright. `tests/fitfix-pcb-materials.test.mjs` was run with Python 3.12, as in CI; the default Python 3.13 changes gzip headers and fails that byte comparison regardless of this change.

Baseline before the upgrade (zudo-doc 6.2.0): 66 MDX documents, native build 86 pages, 66 search entries, 96 HTML files in `dist/`.

After the upgrade, before restructuring: identical 96 HTML paths, 86 pages and 66 search entries. Passed: `check:docs`, `check:tables`, `check:r9-doc-table`, `check:fullset`, `check:assets`, `test:ledger`, preview-link and preview-origin tests, `check:printed-5mm`, `test:printed-5mm`, `test:two-way`, `check:two-way`, `check:r9`, `check:fitfix`, `check:lid-m5`, `check:r9-ledger`, `test:r9`, fitfix materials, order-map, `check:fit-test-order`, `test:fullset`, `test:setup`, `check` (tsc), `check:wind`, `check:preview-isolation` (installed real CLI), asset-preparation and deployed-verification fixtures, `build`, `check:built-preview-links`, `check:images`, `prepare:worker-assets`, worker-asset and deployment tests.

Browser checkpoint on `pnpm dev`, desktop 1440×900 and iPhone 13 emulation: 14 representative pages (overview, status, 7U40, R10, current preview, files, printed P5/P3, 2WAY, `/files/`, maintenance) returned 200 with one H1, no console or page errors, no failed local requests and no mobile horizontal overflow. Japanese search for 金属, 蓋 and 家庭印刷 returned results on both viewports. The asset viewer rendered an SVG, a document image loaded, and the P5 preview iframe loaded its standalone viewer with a canvas.

## Documentation restructure (Phase B)

The 66 baseline documents were reorganised into six top-level sections that match the header: `overview` (全体案内), `metal-case` (金属ケース), `printed-5mm` (家庭印刷ケース), `two-way` (2WAY 実験設計), `shared` (共通部品・元データ) and `development` (開発・保守). `/files/` is unchanged. `overview/start` stays the entry document and is now the family chooser; `overview/status` is a cross-family summary and its metal detail moved to `metal-case/status`.

- Ownership and migration map: `project/doc-routes.json` (76 canonical pages: 66 baseline sources accounted for plus 10 new pages; treatments `retained`, `moved`, `moved-historical`, `split`, `new`; old heading anchors and their targets).
- Old URLs: 45 compatibility pages generated by `scripts/sync-doc-routes.mjs`. Each is `unlisted: true` (out of the sidebar, search and prev/next), links to its canonical page, and keeps the old heading anchors as `<span id>` stubs with a table of where each one went. The ownership table in `development/doc-structure.mdx` is generated from the same map.
- Printed family: P3/P4/P5 leaf URLs are retained; a new `printed-5mm/history` hub and the explicit sidebar in `src/sidebars.js` group 現行 P5 / 履歴 P4 / 履歴 P3. Two-way leaf URLs are retained.
- Metal family: real category landing pages, R9 material under `design/history`, `manufacturing/history` and `verification/history`, R10 listed first.
- Stale content corrected: R9 described as current, P4 called unvented, the P4 label on the overview, R8/R6 presented as universal starting points, coupon-first steps presented as current, and ambiguous "three models" wording now scoped to the metal family.
- Generators now write canonical paths: `sync-reference-tables.mjs` (five metal pages), `sync-r9-doc-table.mjs`, `sync-fullset.mjs`. The preview host index from `prepare-worker-assets.mjs` links to `/docs/overview/start/`.
- Checks: `check-docs.mjs` requires an index in every category, rejects duplicate `sidebar_position` among siblings (a category index is ordered among its parent's siblings, unlisted pages ignored) and validates the route map. New `check:doc-routes`, `test:doc-structure` and, after build, `check:built-doc-routes` (old and canonical routes built, compatibility links and anchors, search exclusion, crawl of every internal docs link and fragment) run in CI.
- `engineering/README.md` now covers every family (artifact-manifest hash updated); root `AGENTS.md` is split into global and metal-family rules, with the interlocking-tab prohibition scoped to metal and P5 tabs governed by `engineering/printed-5mm/AGENTS.md`.

Not changed: design semantics, approval state (`production_approved` false), CAD, binaries, quantities, provenance, order records, and hash-preserved engineering tools. `engineering/r9-fitfix-01/tools/check_preview.cjs` and `engineering/r10-fullset-01/tests/docs-browser.cjs` still open the old `/docs/design/...` URLs; they are covered by preservation manifests, are not in CI, and those URLs now resolve to compatibility pages that link to the canonical page.

Results after the restructure: `check:docs` reports 121 MDX (76 canonical, 45 compatibility), 22 categories and 641 internal links; native build 141 pages with no warnings; 76 search entries, no compatibility page indexed; `check:built-doc-routes` resolves 10273 internal links and fragments across 121 built docs pages. Every command in the verification list above passed again, plus the frozen install. Browser checks against the built site at 1440×900 and 390×844 covered 18 routes (chooser, status pages, family entries, nested metal categories, printed history, two-way, shared, development, three compatibility pages, `/files/`): all 200, one H1, no horizontal overflow, no console errors, breadcrumbs and prev/next follow the new tree, the printed sidebar shows the three groups, and an old status anchor resolves on its page.
