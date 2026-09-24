# Offline Three.js bundle

- Runtime: Three.js **0.169.0** (MIT).
- Included addons: `OrbitControls`, `RoomEnvironment` from the same release.
- Build tool: esbuild **0.25.10** (not loaded at runtime).
- Source entry: `entry.js`.
- Browser output: `three-bundle.js` (IIFE / classic script, ES2020).
- Browser globals: `window.THREE`, `window.OrbitControls`, `window.RoomEnvironment`.

Load `three-bundle.js` with an ordinary `<script src="vendor/three-bundle.js"></script>`.
The bundle makes no network requests and does not require a local server.
Three.js licensing is preserved in `THREE-LICENSE.txt` and the output bundle.

## Rebuild

In this directory:

```sh
npm install --no-save --no-audit --no-fund three@0.169.0 esbuild@0.25.10
npx esbuild entry.js --bundle --format=iife --target=es2020 --minify --legal-comments=inline --outfile=three-bundle.js
```

Sources:
- https://github.com/mrdoob/three.js/tree/r169
- https://www.npmjs.com/package/three/v/0.169.0

The reference preview uses the same Three.js version via CDN:
https://github.com/Takazudo/zudo-blanks/tree/main/panels/art-strip-mine/preview
