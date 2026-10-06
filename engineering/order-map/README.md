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
