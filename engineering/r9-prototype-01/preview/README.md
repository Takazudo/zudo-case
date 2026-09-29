# R9-PROTOTYPE-01 preview

The viewer is a standalone offline HTML file built from the generated R9 STEP parts and placement manifests. It also includes the original pinned R6 40HP rail STL at 204 mm. The viewer does not use R8 meshes.

From the repository root, regenerate the geometry data and preview with the pinned CadQuery environment:

```sh
cd engineering/r9-prototype-01
uv run --locked python build.py --only body,slots,guards,lid,preview_data
cd preview
uv run python build.py
```

The generated mesh, section PNGs, section index, and file table live under `engineering/r9-prototype-01/out/preview/`. The built page is `public/previews/r9-prototype-01.html`. The single HTML contains its scripts, styles, mesh, section images, and file table; it makes no network requests. Rebuilding with unchanged inputs writes identical bytes.

## Manager-owned browser check

This workflow intentionally leaves browser launch and screenshot review to the integration manager. Install Playwright and its Chromium build in the local environment, then run:

```sh
uv run --with playwright playwright install chromium
uv run --with playwright python engineering/r9-prototype-01/preview/check_preview.py
```

The script opens only the local HTML, blocks HTTP(S) requests, records console and page errors, checks daily/travel/open states, verifies the 0–150 mm slider and part information, measures horizontal overflow at 390 px, and writes three screenshots to `engineering/r9-prototype-01/preview/shots/` plus `out/preview/browser-check.json`.

The manager should inspect the generated screenshots at desktop 1440 px and mobile 390 px, and confirm the lid lift, two travel bands, transparent envelope, slot section, guard fit/adhesive section, locator clearance section, and click-selected part dimensions. These are visual checks only; they do not validate physical fit, loads, transport, or manufacturing readiness.
