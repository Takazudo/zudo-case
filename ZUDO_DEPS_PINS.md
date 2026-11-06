# ZUDO_DEPS_PINS

## zudo-doc scaffold
- repo: zudolab/zudo-doc
- what: official create-zudo-doc scaffold, reconciled against old upstream/current local/new upstream
- files: pages/docs/[[...slug]].tsx, pages/index.tsx, src/styles/global.css, tsconfig.json, pnpm-workspace.yaml, .npmrc, scripts/check-links.js, public/favicon*
- source: packages/create-zudo-doc/templates/base/{pages/,src/styles/global.css,tsconfig.json,scripts/check-links.js,public/favicon*} → the same local paths; src/scaffold.ts generates .npmrc and pnpm-workspace.yaml; src/compose.ts and src/features/ apply setup.preset.json
- track: releases (published create-zudo-doc stable, compatible with the selected zudo-doc/zfb tuple)
- pinned: 4b5b54e3e0f383cfbf1e7b6038c6b65ee7c5f9d2 (v9.1.2; npm gitHead verified)
- previous: 6542b8300f4a554247563a3bac53e415a63ded51 (v6.2.0)
- updated: 2026-11-06
- sync: generate create-zudo-doc@<exact-version> in a disposable directory with --preset <checkout>/setup.preset.json --no-install --no-git --yes; compare previous upstream, current local and new upstream, then check/build/browser-verify before updating this pin
- notes: 9.1.2 reconciliation (2026-11-06): all eleven copied files are byte-identical in regenerated 6.2.0, the checkout and regenerated 9.1.2, so none were replaced. The generated 9.1.2 manifest moves Node to >=24 and the zfb family to exact 5.2.0, and its zfb.config.ts adds themePack "default"; these were applied to the root manifest and authored config. .handoff/maintenance-scaffold-9.1.2.json records hashes and package evidence; project/maintenance-zudo-doc-9.1.2.md records verification. Earlier history: all originally copied files matched the regenerated 5.27.0 output; four changed at 6.2.0 (doc route, CSS, tsconfig, pnpm workspace build allowlist). Copied files have no local customizations. Preserve authored zfb.config.ts, chrome bindings and components, Japanese MDX, public assets, custom runner, two Workers, and disabled history/transitions/MCP/agent exports. Do not run setup over this checkout. The original .handoff/setup-record.json is immutable history; .handoff/maintenance-scaffold-6.2.0.json records this reconciliation. Root package.json retains history-server (assetViewer), Wrangler, checks and TypeScript 5.9, and pins pnpm 10.30.3. The 6.2.0 receipt is immutable history.
