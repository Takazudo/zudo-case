# 10BOX v2 R5 — flat H2D projects, import compatibility fixed

This set supplies a flat placement for every required printed assembly part:
**15 projects, 22 stored object instances, and 23 physical parts.** The common
floor file contains one floor; print that plate twice. The spacer file contains
eight spacers; print that plate once. Every other file contains one part.

These are configured, **unsliced** Bambu Studio projects. The actual 3MF meshes,
transforms, nozzle areas, exclusion clearance, settings preservation, and part
counts have been checked. No Studio load/slice or physical print has been
performed, and there are no generated toolpaths.

## Import compatibility correction

The earlier R5 files had a real compatibility defect: `_rels/.rels` used
`ns0:Relationship` tags. The pinned Bambu Studio importer compares the raw
element name to `Relationship`, so it ignored that entry and could not find
the main model. Our earlier namespace-aware XML checks did not catch this.

All 15 current projects and all 14 frozen rebuild inputs now use unprefixed
`Relationship` tags with the correct default OPC namespace. Only `_rels/.rels`
changed inside those archives. The model/mesh/build XML, object and plate
configuration, and global printer settings payloads are byte-identical to
their pre-repair versions. The floor and roof positions are unchanged.

The serializer is corrected, and a new verifier uses namespace-unaware Expat
with the pinned importer's exact tag names. It reproduces the old failure and
passes all 29 corrected archives. It also checks the model, configuration,
content-type declarations, UUID prefixes, object/part/plate references, and
filament-map structure. This is a focused source-compatible import check;
it does not claim that the full Studio application has loaded or sliced them.
See [`sources/studio-import-repair.md`](sources/studio-import-repair.md).

## New common floor

Open `projects/body-bottom-common.3mf` to preserve the intended nozzle assignment
and exact diagonal placement. It already lies on its broad face at −45 degrees;
its thickness is 5 mm. Print it twice for the front and rear floor positions.
The front assembly placement is the rear part rotated 180 degrees about Z and
raised 36 mm. The CAD assembly retains both named placements, while the print
set uses this one common part.

The R5 floor removes four small triangular corners from the main rectangle:
two opposite corners have 12 mm legs, and the other two have 16 mm legs. All four
side joint tabs and all nine screw slots remain. The overall assembly-coordinate
bounding box is still 336.8 ×144.99432 ×5 mm because the tabs are retained; the
clipped outline is what permits the diagonal flat placement.

| Floor placement check | Result |
|---|---:|
| Rotation on the bed | −45° |
| Centre of the original main rectangle | X162.5, Y160 mm |
| Posed model footprint | 316.850532 ×311.193678 mm |
| Printed height | 5 mm |
| X bounds | 4.074734–320.925266 mm |
| Y bounds | 4.403161–315.596839 mm |
| Minimum left/right nozzle-edge clearance | 4.074734 mm |
| Minimum front/rear nozzle-edge clearance | 4.403161 mm |
| Conservative hull clearance to rear exclusion | 21.194489 mm |
| Brim | None |
| Supports | Disabled |

The model's bounding rectangle overlaps the rear exclusion rectangle, but the
actual material does not: everything above Y310 is left of X115.027. The checked
exclusion is X145–256, Y310–326. The independent verifier intersects the actual
posed mesh's convex hull with this rectangle and measures their separation.
It does not use the overlapping bounding rectangle as an exclusion failure.
The relevant Studio implementation is documented in
[`sources/studio-exclusion-check.md`](sources/studio-exclusion-check.md).

`meshes/body-bottom-common-print.stl` is exported from the same verified posed
mesh as the 3MF. It preserves the diagonal orientation and has been checked for
closed edges, consistent winding, positive volume, and one connected component.
STL does not retain printer settings or the nozzle assignment, and Studio may
reposition an imported STL. Use the 3MF for the verified placement.

The assembly-coordinate STEP and STL exports remain in the adjacent
`10box-v2-r5` CAD folder. `body-bottom-common` is an alias of the rear floor,
not an additional physical part.

## Complete project set

| Project | Stored objects | Plate runs | Required parts |
|---|---:|---:|---:|
| `body-bottom-common.3mf` | 1 | 2 | 2 |
| `body-left.3mf` | 1 | 1 | 1 |
| `body-right.3mf` | 1 | 1 | 1 |
| `body-front.3mf` | 1 | 1 | 1 |
| `body-back.3mf` | 1 | 1 | 1 |
| `lid-top-single.3mf` | 1 | 1 | 1 |
| `lid-left.3mf` | 1 | 1 | 1 |
| `lid-right.3mf` | 1 | 1 | 1 |
| `lid-front.3mf` | 1 | 1 | 1 |
| `lid-back.3mf` | 1 | 1 | 1 |
| `stand-left.3mf` | 1 | 1 | 1 |
| `stand-right.3mf` | 1 | 1 | 1 |
| `stand-connector-front.3mf` | 1 | 1 | 1 |
| `stand-connector-back.3mf` | 1 | 1 | 1 |
| `spacers-8.3mf` | 8 | 1 | 8 |
| **Total** | **22** | **16** | **23** |

All 14 R4 flat projects retain their geometry, placement, and printer/process
configuration bytes. Their archives differ from R4 only in the repaired root
relationship XML. The single roof remains flat at 317 ×290 ×5 mm, with
X4–321, Y10–300 bounds and no brim. Its two wider side lid parts also retain
their flat outer-face-down placement and no brim. The older body, lid-end,
stand, and spacer projects retain their existing gapped 5 mm brim settings;
the existing lid-end support settings are also preserved.

## Saved printer/profile preservation

Every project's `Metadata/project_settings.config` is byte-identical to the
bundled saved H2D template (SHA256
`99b34023dcf3d8142abb119f426ca54d499a4d07026c7e406e2b062147c7a356`).
This retains the H2D 0.6 mm hardware, the existing PLA filament slots, and the
saved process profile. No printer reach, exclusion, nozzle mapping value, or
global temperature/material setting is enlarged or changed.

The floor and roof use the actual left nozzle area X0–325, Y0–320 mm. Their
plates explicitly select supported `filament_map_mode=Manual` with the existing
`filament_maps=1 1`. Object `extruder=1` selects filament slot 1. Logical nozzle
mapping and physical extruder mapping are separate; the preserved mapping is
explained in [`sources/left-nozzle-mapping.md`](sources/left-nozzle-mapping.md).

Other projects fit the common nozzle area X25–325, Y0–320 mm. The generic helper's
common-area layout flag is not claimed for the wider roof or diagonal floor.
Those two packages receive structural validation plus independent validation
against their explicitly selected left nozzle and the saved exclusion geometry.

## Rebuild and verification

Keep `h2d-r5` and `10box-v2-r5` beside one another. Install Python 3, CadQuery,
NumPy, and SciPy. Run from the bundle root:

```bash
python3 h2d-r5/build_flat_projects.py --output-dir h2d-r5/projects-rebuilt
python3 h2d-r5/verify_flat_packages.py
python3 h2d-r5/verify_studio_import_contract.py --include-frozen
```

The output directory must be new; the builder preserves existing projects.
It writes its report to point at the newly generated folder. The verifier reads
that report and validates those actual packages. UUIDs and archive timestamps
can differ on rebuild. The 14 copied projects match the bundled corrected
frozen inputs byte for byte; they do not match the old R4 archives byte for byte.
The builder automatically runs the new import-contract check.

All required inputs are bundled: the empty template, helper scripts, frozen
flat R4 geometry projects with repaired relationships and provenance, the frozen
roof pose, and the adjacent R5 CAD
source exports. No external R3/R4 workspace directory or downloaded source is
needed. An isolated rebuild has been checked using only these delivered inputs.

Useful records:

- `assembly-bom.csv`: maps the 15 project files to all 23 assembly IDs.
- `h2d-project-report.json`: geometry provenance, placement, counts, hashes.
- `independent-package-review.json`: actual archive validation results.
- `import-repair-report.json`: original/repaired hashes and exact changed members.
- `studio-import-contract-review.json`: all 29 current/frozen source-dispatch checks.
- `floor-print-pose.json` and `roof-print-pose.json`: exact preview poses.
- `validation/`: per-project structural and retained-layout checks.

Open and slice the selected plate in Bambu Studio before printing. Inspect its
first layer and any retained brim/support paths. The new floor and the roof
use no brim, so confirm adhesion and flatness with the chosen build plate and
PLA before committing to a full case set.
