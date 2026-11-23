# 10BOX-v2 R8-LID-LEDGE-01 — connected lid retaining ledges

Current working revision selected by the user on 2026-11-24 (Japan).
Tracking: https://github.com/Takazudo/zudo-case/issues/149
Base: R8 at commit 50f9abe64b66d656d1cfbe3264dc1c7b0fc77b38.

## Current geometry

The two obsolete center gaps in each lid front/back retaining ledge are filled
for the one-piece roof. Front and back remain one common shape, rotated 180° in
the assembly. The two outer L-bracket windows, mounting holes, lower locating
tongue, outer bounds and inherited ledge heights remain unchanged. The roof,
body, rail layout, spacers and all hardware keep their R8 geometry and placement.

The bridges project 3 mm inward and are 5 mm high, with their top at roof underside
Z108 mm. A 0.05 mm overlap into the existing solid ensures a fused union. Each
panel gains 672.377322 mm³. The old source has 1.9444595 mm³ of roof overlap from
ledge tops at Z108.00459; this correction adds no additional roof interference.

The standalone STL approved by the user is preserved byte-for-byte:
`3426afa3086cdee245bb4dfa63387a8576b7d8551d895a982aa2a4b81f03859a`.
It is one closed manifold: 178 vertices / 360 triangles. Nominal part dimensions
are approximately 327.408 × 48.500 × 10.000 mm; diagonal print bounds are
265.801 × 265.801 × 10.000 mm. Units are millimeters, with the broad face down at
Z0 and the previous 45° print placement retained.

## Print and inspect

Current public files use the prefix `tenbox-v2-r8-lid-ledge-01`:

- `-print.zip`: complete set of 15 H2D projects. Print `projects/lid-front.3mf`
  and `projects/lid-back.3mf` once each. These two projects replace the old lid
  meshes; the other 13 projects are byte-identical to R8. The common floor still
  prints twice: 22 stored objects, 23 physical parts and 16 plate runs in total.
- `-review.zip`: complete assembly STEP/STL, exact CAD evidence, current model,
  nominal hardware schedule and standalone 3D viewer.
- `-source.zip`: editable repository-shaped source and all frozen inputs used
  by this incremental builder: R8 assembly/print archives, the three lid STEP
  inputs, two original print projects, renderer, packaging helper and environment
  lock. It rebuilds the complete current set without downloading additional
  geometry. Historical R8 authoring sources remain in the unchanged
  `tenbox-v2-r8-source.zip` archive.
- `/previews/tenbox-v2-r8-lid-ledge-01.html`: current 3D viewer, including a lid
  ledge inspection view and the preserved R7 comparison.

The direct `10box-v2-lid-frontback-connected-r01.stl` and matching `.3mf` in
`public/downloads/candidate/` are alternatives for printing just the lid panels.
Print the common part twice; these are not additional parts beyond the full set.
The print ZIP also contains the same STL under `meshes/`.

H2D / 0.6 mm / PLA settings, filament mapping, saved placement, 5 mm brim with
0.1 mm gap, and support settings remain unchanged. Projects are unsliced.
Native Studio load/slice and physical print/fit/load checks are not performed;
production approval remains false.

## Rebuild the complete current set

Use the exact R5 locked environment: Python3.12.14 / CadQuery2.7.0 /
NumPy2.3.5 / SciPy1.17.0. From the repository or extracted full source package:

```sh
uv sync --locked --project engineering/tenbox-v2/r5
uv run --locked --project engineering/tenbox-v2/r5 python engineering/tenbox-v2/r8-lid-ledge-01/build_current.py --out /path/to/new-output
```

Choose an output directory that does not exist. `--publish-root .` writes the new
versioned downloads, preview and artifact registry into a checkout; it does not
deploy or modify historical R5–R8 sources/packages. `--no-packages` runs geometry,
print-project and preview generation without producing ZIPs.

`pnpm build:tenbox-v2` selects this builder. The existing explicit R8 build/check
commands continue to address the immutable historical revision.

## Regenerate just the common lid part

```sh
uv run --locked --project engineering/tenbox-v2/r5 python engineering/tenbox-v2/r8-lid-ledge-01/build.py --out /path/to/new-lid-output
```

This exports the common STL/3MF, front/back STEP and individual H2D projects,
geometry evidence and a small self-contained `source/` folder. Inside that
small standalone source folder, `python3 build.py --out /path/to/new-output`
works with the same pinned dependencies. The optional `render_preview.py` uses
Matplotlib to produce a precise before/after image.

## Verification

```sh
python3 engineering/tenbox-v2/r8-lid-ledge-01/check_current.py
python3 engineering/tenbox-v2/r8-lid-ledge-01/check_current.py --build /path/to/new-output
```

The standard-library checker inspects actual package bytes and manifests,
source completeness, the unchanged 13 projects, settings/model placement, exact
approved STL hash, the two changed assembly solids, preserved R7 comparison,
and the current preview's topology/world vertices. The CAD builder checks one
valid solid per panel, additive-only geometry within the target regions, five
to three ledge sections, unchanged bounds and roof interference, and separation
from every existing lid hardware envelope. All other 282 current part records
and their meshes are unchanged.

The browser verifier exercises current/R7 switching, desktop/mobile controls,
Canvas/WebGL, closed/lifted/exploded lid states and actual mesh containment at the
former gaps. Native browser checks and software rendering are reported separately.
The current selection is in `project/tenbox-v2/current.json`; generated receipts
are in `project/tenbox-v2/r8-lid-ledge-01.json`.
