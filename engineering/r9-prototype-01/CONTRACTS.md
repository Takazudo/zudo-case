# R9-PROTOTYPE-01 frozen generator contracts

Scope: 7u40 prototype only. These interfaces govern the implemented geometry modules; no part is approved for manufacture.

## Coordinates and units

All dimensions and mesh coordinates are millimetres. X runs along the 204 mm 40HP rails (case width), Y runs front to rear (case depth), and Z runs bottom to top. The origin is the center of the bottom plate's lower face. Positive X is right, positive Y is rear, positive Z is up. The 7U row stack (3U + 3U + 1U) is laid out along Y in one plane. Part solids and preview meshes use assembly coordinates. DXF contours use the part's local 2-D flat pattern in XY; document any transform in a part manifest.

## Module API and ownership

`build(ctx: r9.types.BuildContext) -> list[r9.types.Part]` is the hook in each of `body`, `slots`, `guards`, `lid`, `coupons`, `preview_data`, and `checks`. `Part` has `id`, CadQuery `solid`, `category`, `material`, `qty`, and `export_kinds` (`step`, `stl`, or `dxf`). `ctx.value(namespace, key)` reads the five parameter namespaces. The orchestrator calls hooks in that order. `--only MODULE[,MODULE...]` runs one or more hooks in the supplied order; unknown or duplicate names are rejected. For `dxf`, the `Part` also carries `dxf_outline` (XY polygon), `dxf_holes` (x, y, radius), and `dxf_slots` (x, y, overall length, width, angle in degrees). Angle 0 is horizontal and positive angles rotate counterclockwise in local XY. Each slot is exactly two LINE and two ARC entities on SLOTS. DXF cannot be inferred safely from a 3-D solid. Each module should return unique part IDs and write module-specific metadata under `out/` only.

IDs use uppercase `7U40-R9-<MATERIAL>-<ROLE>`: e.g. `7U40-R9-AL-BOTTOM`, `7U40-R9-PA12-GUARD-TOP-A`, `7U40-R9-LID-PLATE`, `7U40-R9-CPN-C1-03`. Repeated physical instances share a part ID and use `qty`; separate geometry gets a separate ID. The orchestrator uses part category for its output directory; guard, lid, and C2 hooks export nested files and register their hashes in module manifests. No spaces or underscores in IDs.

## Outputs

`out/{aluminum,pa12,hardware-envelopes,coupons,assembly,preview}/` is the generated tree. CAD filenames are `{part-id-lowercase}-qty{N}-mm.{step|stl|dxf}`. `out/build-log.json` lists revision, model, selected modules, parts, and SHA-256 hashes of delivered bytes. Preview geometry goes in `out/preview/model-data.js`; assembly metadata goes in `out/assembly/assembly.json`. The generated candidate packages have these destination names relative to the repository root:

- `public/downloads/candidate/7u40-r9-prototype-01-aluminum-NOT-APPROVED.zip`
- `public/downloads/candidate/7u40-r9-prototype-01-pa12-NOT-APPROVED.zip`
- `public/downloads/candidate/7u40-r9-prototype-01-coupons-NOT-APPROVED.zip`

ZIP entry names are sorted relative paths by `common.write_zip`. The package generator verifies contents, hashes, sizes below 25 MiB, and unapproved labeling. The packages are quote and prototype candidates, not manufacturing release files.

## Preview mesh schema

`model-data.js` assigns `window.ZUDO_SIMPLE_MODEL_GZIP` to a base64 string of gzip JSON, following R8 (gzip `mtime=0`). After decompression, root JSON has `revision`, `model`, `units: "mm"`, and `parts: []`. Every part has `partId`, `name`, `category`, `positions` (flat XYZ float array), and `indices` (flat triangle index array). Coordinates are in the assembly frame above. Stable part order is ascending `partId`; mesh vertices and triangles follow deterministic exporter ordering. A module may add properties but must retain these fields.

## Frozen top-edge interface

`params/guards.json` is the single source for `top_edge_guard_opening_x/y`, `top_edge_guard_exterior_x/y`, `top_edge_seated_guard_z`, and `top_edge_adhesive_allowance`. `params/lid.json` mirrors those keys for review only; lid code must read guard values through `ctx.value("guards", key)` and assert its mirrors match. `top_edge_lid_locator_clearance` belongs to `params/lid.json`. The guard and lid generators consume this interface and must coordinate a change instead of redefining a dimension locally. R6/R8 values are provisional nominal references, not fit validation. The unset top-edge adhesive allowance remains a manufacturing decision; the candidate guard's separate adhesive-layer parameter is provisional.

## Determinism

`common.export_step` normalizes OCC's `FILE_NAME` header record, replacing timestamp, author, originating system, and filename with fixed values. It also normalizes OCC's incrementing translator product suffix to zero. Other geometric DATA records are preserved. `common.export_dxf` uses R2010/mm, fixed ezdxf metadata, and OUTLINE/HOLES/SLOTS layers. `common.export_stl` writes a fixed 80-byte header and sorted binary triangle records. `common.write_zip` uses sorted names and 1980-01-01 ZIP timestamps. Ledger hashes always hash actual delivered bytes. The smoke test checks repeated exports on the pinned toolchain; geometry changes may change bytes and hashes.
