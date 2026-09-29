# R9-PROTOTYPE-01 7U40 candidate generator

This directory contains the independent 7U40 candidate generator and its recorded CAD outputs. The candidate uses the R6 7U40 geometry as its starting point and rebuilds the adopted R8 lift-off lid as editable R9 geometry. It is not a manufacturing release; all physical fit, hardware, finish, and transport gates remain open.

Python 3.12 and uv are required. From this directory, install the locked environment, regenerate the candidate, and run its validation:

```sh
uv sync --locked
uv run python build.py
uv run python build.py --validate
uv run python tests/smoke.py
```

For a focused regeneration, pass a comma-separated module list such as `uv run python build.py --only body,slots`. The complete module order is body, slots, guards, lid, coupons, preview data, and checks. `out/outputs-manifest.json` records the generator inputs and output byte hashes; `project/release-state.json` and `project/artifact-manifest.json` register the unapproved candidate files.

The committed `out/` files are the generated evidence for this revision. Scratch builds and parameter-change checks use temporary directories. Review generated geometry and its manifest together when intentionally refreshing a candidate; a hash update by itself does not validate a geometry change.

## Candidate bracket slots

The body plate exports use 36 obround bracket slots (5.5 × 7.5 mm, ±1.0 mm candidate travel), with the long axis perpendicular to the joint bend line. The 10 rail-fix holes stay round φ5.5 because the independent rail frame is located by its fixer PCB. There is no intentional adjustment along the bend line; along-edge positions follow the CAD hole spacing. The nominal datums are the bottom plate's lower face and each wall's exterior face. Assemble by 仮締め → 外形/直角を整える → 本締め.

`out/aluminum/hole-table.json` lists all 46 locations; `slot-checks.json` records edge, ligament, bearing, guard-band, and nominal exterior tool-envelope checks. The provisional 10 mm outer washer does not meet the specified bearing overlap at 26 wall slots. An OD of at least 11.5 mm is a candidate to check for fit and availability, not a selected part. Slot size, driver envelope, fastening hardware, and physical access need coupon and assembly confirmation before manufacture.

## Current recorded validation

See [VALIDATION.md](VALIDATION.md) for the stored validation summary and flags. It records 156 passes, 14 flags, and zero failures for the current candidate. CAD checks do not validate physical fit, loads, guard retention, anodizing allowance, strap strength, module clearances, or transport. The open physical checks and blank result sheets are documented in the project verification pages.
