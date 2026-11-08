# 10BOX v2 R5 — floor corners clipped for flat H2D placement

R5 implements the requested corner cuts on both body floor panels. Each floor remains one continuous 5 mm panel, with all four side tabs and all nine fixing slots. Both assembly positions use the same physical shape; print the common floor project twice.

## File-format repair

This reissue repairs file delivery and 3MF importer compatibility. It makes no further geometry changes to R5.

- The earlier distributed ZIP was truncated at 4,527,554 bytes and lacked its central directory and end record. This complete replacement is closed, checked, and atomically installed before saving.
- The earlier generated 3MF files used prefixed `ns0:Relationship` elements in `_rels/.rels`. Although namespace-aware XML validators accepted this, the pinned Bambu Studio importer dispatches on the literal unprefixed element name and did not discover the model. All 15 current projects and the frozen inputs used to rebuild them have been repaired.
- Only `_rels/.rels` changes inside each 3MF. The model mesh, transforms, object and plate configuration, nozzle assignment, and global printer/process settings remain byte-identical.
- The source serializer is fixed, and a separate test reproduces the relevant Studio Expat tag dispatch. This is an importer-contract check, not an actual Bambu Studio application load or slice.

Use `h2d-r5/projects/` for the current complete 3MF set. The standalone corrected files end in `-fixed.3mf`. The `source-r4` CAD directory is retained only as historical input for reproducing the geometry; it is not the revised floor export directory.

## Corner cuts

The rear floor's main rectangular outline is 327.1 ×144.99432 mm. Its joint tabs reach a maximum overall width of 336.8 mm. Only the four convex corners are clipped:

- Two diagonally opposite corners have 12 mm legs.
- The other two have 16 mm legs.
- All four cuts run at 45° to the original edges, through the full 5 mm thickness.

For the rear floor, with local depth coordinate `v = Y −72.49716`, the retained corner halfplanes are `|X + v| ≤224.04716` and `|−X + v| ≤220.04716`. These planes clip the rectangle's corners without clipping the existing tab tips. The front floor uses the same shape rotated 180° about Z and lifted 36 mm, preserving front/back interchangeability.

The removed area is 400 mm² per floor: two 72 mm² triangles and two 128 mm² triangles. Removed volume is 2,000 mm³ per floor, approximately 0.845% of the preceding floor volume. The overall case width, rail spacing, screw axes, tab geometry and receiver geometry are preserved.

## Flat print pose

`body-bottom-common.3mf` is already laid flat and rotated −45° in the bed plane. Its broad face is on the plate, with 5 mm maximum height.

| Quantity | Common floor project |
| --- | --- |
| XY footprint after rotation | 316.850532 ×311.193678 mm |
| X bounds | 4.074734–320.925266 mm |
| Y bounds | 4.403161–315.596839 mm |
| Z bounds | 0–5 mm |
| Selected nozzle | Left only, explicitly assigned |
| Left nozzle's saved area | X0–325, Y0–320 mm |
| Minimum X edge margin | About 4.07 mm |
| Minimum Y edge margin | About 4.40 mm |
| Brim / supports for the new floor | None / none |
| Required floor quantity | Two identical parts |

The rear tip extends beyond Y310 only on the left of the saved wiping exclusion. The actual conservative floor hull is approximately 21.19 mm away from that exclusion. Verification uses the real outline/convex hull; its enclosing rectangle alone would misleadingly overlap the exclusion. The corresponding Studio source behavior is documented in the fit analysis.

The original assembly-coordinate STL may still report 336.8 mm overall width because its tabs stay at their original positions. The supplied 3MF contains the required diagonal orientation and position. Use that project directly; the print-oriented STL provides the same diagonal geometry as an alternative import.

## How the assembled case changes

The four trimmed corners create intentional small triangular openings at each floor's corners. Some original corner retaining-lip contact is removed. The main panel, all four tab engagements, all nine screw slots and their surrounding fixing regions remain. The independent CAD review quantifies the changed corner contacts and verifies the retained fastener lands.

The user-requested 8 mm frame-to-side gap and 337.4 mm exterior width remain. The R4 lid is preserved: one 317 ×290 ×5 mm roof, 5 mm inward side caps, lower bearing shelves, and reduced central fixing count.

## Current project set and validation scope

The package includes the earlier 14 flat projects plus one common floor project. The 15 project files contain 22 stored object instances; printing the common floor twice produces the 23 physical parts in the full assembly. The bill of materials maps the common floor project to both `body-bottom-front` and `body-bottom-back`.

All required assembly parts now have flat geometric placements in the saved H2D nozzle areas. The new floor and the unchanged roof explicitly use the left nozzle. This is a placement and model-integrity result, not a successful physical-print claim.

Projects preserve the saved H2D 0.6 mm/PLA configuration. The new common floor has no brim or support. Existing unaffected project settings remain as previously supplied. All projects are unsliced; actual Studio toolpaths, adhesion, material strength and physical fit remain unverified.

## Review views

Open `10box-v2-r5-preview.html`:

- **Floor on H2D:** the exact diagonally posed floor mesh, selected-nozzle area and rear exclusion.
- **Clipped floor:** the revised panel's actual outline, slots and tabs.
- **Case underside:** the triangular corner openings in the complete body.
- **Previous floor:** the R4 panel with its original uncut corners.
- Existing lid, joint and rail-gap views remain available.

## Editable source and checks

The bundle contains the R5 CadQuery generator and configuration, frozen R4 inputs, STEP and review STL exports, the common floor print project, the complete H2D project set, reproducible package generation and verification, and the preview source.

The changed STL exports are checked directly for closed manifold edges, winding, connectedness and positive volume. Separate checks compare exported STEP solids, retained holes/tabs, front/back equivalence and corner contact changes. Printer checks inspect the actual 3MF meshes and nozzle mapping. The preview's software-renderer and UI-handler checks do not claim browser-layout or WebGL validation.

Recorded results: 82/82 generator checks, 27/27 independent exported-STEP checks, direct integrity checks on both changed STL files and the common posed STL, independent inspection of all 15 project archives, and 36/36 renderer/UI-handler checks. The H2D builder and verifier also passed an isolated rebuild using only the delivered inputs.
