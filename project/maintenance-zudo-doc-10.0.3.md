# zudo-doc 10.0.3 / zfb 6.0.1, Graphite and site imagery — 2026-11-12

Tracker: https://github.com/Takazudo/zudo-case/issues/134. Base: `main` at `6efb8ec0aacdb981327cef2ae00b7be40e6585d7`. One branch and one PR to `main`. No CAD regeneration, supplier communication, order or manufacturing approval is part of this work; `production_approved` stays `false`. Earlier records (`project/maintenance-zudo-doc-9.1.2.md`, `project/maintenance-120.md`, `.handoff/*`) are unchanged history.

## Selected tuple (frozen at implementation start, 2026-11-12T11:50Z)

| Package | Before (lockfile) | Selected | Spec |
| --- | --- | --- | --- |
| @takazudo/zudo-doc | 9.1.2 | 10.0.3 | `^10.0.3` (caret kept) |
| @takazudo/zudo-doc-history-server | 9.1.2 | 10.0.3 | exact (devDependency, assetViewer) |
| create-zudo-doc (scaffold source) | 9.1.2 | 10.0.3 | not installed; `scripts/setup.mjs` default |
| @takazudo/zfb, zfb-runtime, zfb-md-wasm | 5.2.0 | 6.0.1 | exact |

Resolved with `resolve-bumps.mjs` from `Takazudo/claude-settings` `skills/dev-bump-zudo-deps` at `c541f4984e4da43b4fb5d60b3d348b36988e43ee` (cloned outside the checkout): 3 manifests scanned, 5 bumps, no floating tag, non-registry spec, stale tag or graduation. All targets are `latest` stable. TypeScript 5.9, Wrangler 4.138.0, zod and `@types/node` are unchanged. Integrities and provenance are in `.handoff/maintenance-scaffold-10.0.3.json`.

Provenance: only create-zudo-doc and the zfb platform binary publish an npm `gitHead`. create-zudo-doc 10.0.3 `gitHead` `c7210d5c…` equals the commit that tags `v10.0.3`, `zudo-doc-v10.0.3` and `zudo-doc-history-server-10.0.3` peel to in `zudolab/zudo-doc`. zfb 6.0.1 is tag `v6.0.1` (`e6bd0a7c…`) in `Takazudo/zudo-front-builder`, matching `@takazudo/zfb-linux-x64-gnu` 6.0.1 `gitHead`.

## Upstream impact

- **zfb 6.0.0/6.0.1** (changelog + `npm diff`): esbuild removed; every bundling path, including `zfb.config.ts`, uses native Rolldown. `ZFB_BUNDLER` and `ZFB_ROLLDOWN_PROTOTYPE` now abort every command; `ZFB_ESBUILD_BIN` is ignored. None of the three is referenced by scripts, workflows or docs, and none was set in this environment (checked by name only). zudo-wind template-literal fixes. The npm package diff is version pins only. `scripts/run-site.mjs` needed no change: per-run config generation, authored-config import, scratch mirroring (#3318 workaround), `public/assets` dev sync (#4233 workaround) and preview-origin injection all pass `pnpm check`, `pnpm build`, dev and `pnpm check:preview-isolation`. The workarounds were retained because removing them was not necessary. `onlyBuiltDependencies: esbuild` stays because zudo-doc and Wrangler still depend on esbuild.
- **zfb-runtime / zfb-md-wasm 6.0.1**: client-router and WASM rebuilds; peer coupling to zfb 6.0.1 satisfied.
- **zudo-doc 10.0.0–10.0.3**: `themePack: "default"` now aliases Graphite; Classic is `"classic"`. ZFB `^6.0.1` and history-server `^10.0.0` peers. Theme CLI and docHistory binding fixes; `diff` peer widened. Tarball diff touches theme-pack registry/CSS, the routes plugin (docHistory meta seed, off here) and type declarations; no change to `logo`, `metaTags`, robots or home routes. 9.1.3–9.1.5 entries are included in this range (zfb 5.2.2 floor, docHistory binding).
- **history-server 9.1.3–10.0.3**: no package-specific changes.
- **create-zudo-doc 9.1.3–10.0.3**: generated `AUTHORING.md`/`AGENTS.md`/`README.md` (not imported), `--theme-pack default` rejected, TypeScript `^7.0.2` pin (not adopted), MCP-only Wrangler pin.

## Scaffold reconciliation

Generated 9.1.2 (checkout preset) and 10.0.3 (preset copy with `themePack: "graphite"`, since 10.x rejects `"default"`) into disposable directories. Of the eleven copied files, only `pages/docs/[[...slug]].tsx` changed upstream, in a comment; the checkout had no local edit there, so the 10.0.3 file was taken. Authored `zfb.config.ts`, chrome bindings and components, Japanese MDX, navigation, public assets, custom runner, both Workers and disabled features are untouched. `ZUDO_DEPS_PINS.md`, `scripts/setup.mjs` `defaultCliVersion` and `development/setup.mdx` now name 10.0.3.

## Theme and imagery

- `themePack: "graphite"` in `zfb.config.ts` and `setup.preset.json`. The previous `"default"` rendered Classic on 9.1.2; this change intentionally adopts Graphite. Appearance toggle and preference storage are unchanged.
- `public/img/zudo-case-logo.svg` (decorative case-frame and rails illustration, transparent, CSS-mask friendly; not a drawing of an approved design) and `public/img/ogp.png` (1200×630). Source and steps: `project/site-imagery/README.md`.
- `siteUrl`, `logo` and `metaTags` (description, ogImage, ogSiteName, `summary_large_image`) in `zfb.config.ts`. `siteUrl` also makes every doc page emit `<link rel=canonical>` and `og:url` on `https://zudo-case.zudolab.dev`, including builds served from other hosts. `noindex: true` is kept, so every page still has `noindex, nofollow` and `robots.txt` stays `Disallow: /`. Preview services that respect robots.txt may not fetch the card; that is not changed here. The header has no brand icon (`headerBrand` is off); the logo renders only in the home hero.

## Verification (Node 24.22.1, pnpm 10.30.3, 2026-11-12)

All passed: `pnpm install --frozen-lockfile`, `check:docs` (128 MDX, 682 links), `check:doc-routes`, `test:doc-structure`, `check:assets` (700 assets), `test:setup`, `check` (tsc), `check:wind`, `check:preview-isolation`, `prepare-worker-assets`/`verify-deployed-assets` fixture tests, `preview-links`/`preview-origin-isolation` tests, `build` (148 pages, 83 search entries), `check:built-doc-routes` (11180 links), `check:built-preview-links` (68 production preview URLs), `check:images`, `prepare:worker-assets`, `worker-assets`/`worker-assets-deployment` tests. `dist/img/ogp.png` and the logo are in the docs Worker directory.

Built HTML for `/` and `/docs/tenbox-v2/` contains, without JavaScript: `og:image` and `twitter:image` `https://zudo-case.zudolab.dev/img/ogp.png`, `og:image:width` 1200, `og:image:height` 630, `twitter:card` `summary_large_image`, `data-theme-pack="graphite"`, `/theme-packs/graphite/pack.css`, `noindex, nofollow`. The PNG decodes as 1200×630 RGB.

Chromium (Playwright 1.63) against the built site and `pnpm dev`, at 1440×900 and 390×844, light and dark system schemes: 152 checks, all passing after correcting two selectors in the check script. Fresh visit gets Graphite and follows the system scheme; Graphite pack CSS loads; light/dark/system choices persist across reload; a saved preference from an older visit (`zudo-doc-theme=light`, stale `zudo-doc-theme-pack=default`) still applies; home logo renders as a 320×168 mask of the illustration; seven representative docs across all families render with no horizontal overflow; header case menu, desktop and mobile sidebar, Japanese search (「天板」, 10 hits), `/files/` image view, and preview iframes (production host in the build, local `public/` in dev) work; no console errors or failed local requests.

This is software and browser verification only, not physical validation.
