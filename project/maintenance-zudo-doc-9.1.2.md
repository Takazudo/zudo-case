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
