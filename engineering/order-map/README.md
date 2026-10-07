# Ordered fit-test map

English supplier-facing companion to the R9-FITFIX-01 preview for order W2026100405546498. The self-contained published entry is `/previews/r9-order-map.html`; select a design with `#part=c2-01-frame` (or another exact order-plan part ID).

`build.mjs` reads the existing saved scene and order plan, embeds the existing Three.js vendor bundle, and emits the standalone page plus provenance. It never regenerates CAD. `app.js` uses original mesh coordinates; raised-lid and separated-detail offsets affect presentation only. C1 is a representative shared cross-section; C2/C4/C5 use the source-confirmed clip locations in `fitfix/coupons.py`. Counts come from the PA12 order manifest: 13 designs / 15 pieces. Aluminum meshes are mating references, not part of that print quantity.

```sh
node engineering/order-map/build.mjs
node engineering/order-map/build.mjs --check
node --test tests/order-map.test.mjs
```

For browser checks, serve `public/` over HTTP, provide Playwright via `PLAYWRIGHT_MODULE` if not installed in the repository, then run `node engineering/order-map/browser.cjs`. `PREVIEW_ORIGIN` defaults to `http://127.0.0.1:8765`; `SCREENSHOT_DIR` chooses evidence output. Chrome is selected by channel. Tests cover 1440/390 widths, all IDs, markers, selection links, assembly modes, visibility controls and the original preview. Screenshots require visual inspection in addition to assertions. The order map requires WebGL; failure points users to the unchanged normal preview's Canvas fallback.

The link in the normal preview is maintained in `engineering/r9-fitfix-01/fitfix/preview.py`. Its saved HTML and the existing fitfix manifests were updated without modifying their embedded mesh payload. `node scripts/sync-fitfix.mjs --check` verifies those established manifests.

No manufacturing orientation, new tolerance, production release or model revision is implied by this view.

## Anodizing revision review (issue 118)

The material selector separates the **13 aluminum plates** from the unchanged **13 PA12 designs / 15 pieces**. `#part=c5-01-left&revision=revised` opens an individual revised plate; `revision=original` opens its original geometry. Existing PA12 `#part=c2-01-frame` links remain valid. The default aluminum geometry is R9-ANODIZING-01; the same selection controls metal mating references in the PA12 detail view. C2 comparison frames reuse the one ordered C2-01 metal pair.

The aluminum detail is one actual manufacturing plate, with no explanatory assembly offsets. C3 STEP/STL exports are flat XY even for wall coupons; they are deliberately not placed at their case marker. The left panel is unchanged full-case context. No hanging holes are applied to full-size case plates.

`aluminum_meshes.py` reads the original/revised STL vertices without changing them. Original C3 has no STL, so its original STEP is tessellated with the locked CAD toolchain. Each mesh records the source SHA-256 and path. Rebuild and verify with:

```sh
uv run --locked --project engineering/r9-prototype-01 python engineering/order-map/aluminum_meshes.py
node engineering/order-map/build.mjs
node --test tests/order-map.test.mjs
uv run --locked --project engineering/r9-prototype-01 python engineering/order-map/aluminum_meshes.py --check
```

Browser checks raycast the displayed mesh through the manifest hole center in all 13 plates, checking an open revised hole, solid original sheet, and nearby retained material. They also exercise both view widths, both revisions, direct links, refresh, hash changes and the original engineering preview. `CHROME_PATH` optionally selects an installed Chromium executable. Use the machine's heavy/browser guards when required.
