# 10BOX v2 — R5 flat floor panels

Revision: `10BOX-V2-R5-FLAT-FLOORS`. Millimetres; X is width, Y is front/back and Z is up.

Both body floor panels now have four small corner chamfers for flat diagonal placement on the H2D. The case is not resized or split. All four side-connection tabs and all nine screw slots in each floor are retained.

## Corner cuts

The rear/common floor defines the manufacturing shape. Its main rectangle remains327.10 ×144.99432 mm, its tab-tip span remains336.8 mm, and its thickness remains5 mm.

| Rear-floor corner | Leg length along each original edge | Cut endpoints, X/Y mm |
| --- | ---: | --- |
| NE: +X, +Y | 12 mm | (163.55,132.99432) to (151.55,144.99432) |
| SW: −X, −Y | 12 mm | (−163.55,12) to (−151.55,0) |
| NW: −X, +Y | 16 mm | (−163.55,128.99432) to (−147.55,144.99432) |
| SE: +X, −Y | 16 mm | (163.55,16) to (147.55,0) |

Each diagonal cut face is at45°. The four cuts remove exactly **400 mm² / 2,000 mm³ per floor**, or **0.844705%** of the original floor material.

The CAD intersects the original floor with four diagonal halfplanes. It does not replace the outline with a simple octagon, which would incorrectly trim the projecting tab tips. In local coordinates u=X and v=Y−72.49716, the retained limits are:

- |u+v| ≤224.04716 mm
- |−u+v| ≤220.04716 mm

## One common printed part, quantity two

`body-bottom-common.step` and `body-bottom-common.stl` are exact copies of the new rear-floor exports. Print this common shape **twice**.

The front assembly instance is the same physical part rotated180° around global Z and translated upward36 mm. The proper rotation has determinant+1; no mirrored print is required. The independently aligned front/back STEP solids have zero Boolean difference in both directions.

The front and rear named exports remain available for assembly and traceability; the common file is an alias, not a third assembly part.

## Flat H2D placement

The reviewed pose uses the rear/common shape flat at Z0–5 mm, yaw−45°, centered at printer X162.5/Y160 after subtracting its source Y center72.49716 mm. The expected part bounds are:

- X **4.074734–320.925266 mm**
- Y **4.403161–315.596839 mm**
- Z **0–5 mm**

This fits the single left-nozzle area. The small region above Y310 remains to the left of the rear wipe exclusion; a bounding rectangle alone would incorrectly flag that region. Use the separately verified H2D project and its exact placement. This geometry is intended to print flat, not upright.

These are geometric/structural results. A generated3MF or valid mesh does not establish sliced toolpaths or a successful physical print.

## Retained features and deliberate corner openings

The independent STEP review confirms:

- All **nine closed slots** per floor retain their original profile and position.
- All **four complete tabs** and their root regions remain unchanged;4.7 mm engagement is retained.
- A20 ×20 mm region around each original slot axis remains unchanged.
- Minimum new chamfer-to-slot web is approximately **14.5798 mm**.
- A nominal Ø10 washer has at least **14.2384 mm** clearance to the new diagonal cut at the slot center, and at least **12.1928 mm** through nominal slot travel.
- All other active STEP exports remain byte-identical to R4.

The corner cuts intentionally leave small triangular openings in the assembled floor. Some former side-corner lip projection onto the floor is removed; not every old corner support region is preserved. The end-corner lip projected overlap remains approximately45.914–57.892 mm², and all four middle end-lip projection regions are unchanged. These are geometric projection measurements, not measured load-bearing capacity. The retained tab and fixing regions remain the assembly constraints.

The R4 flat lid, supported side flanges, body sides/front/back, rail spacing, mounting heights, other joints, spacers and stand are unchanged.

## Verification

**82 /82 focused generator checks pass.** They cover the changed floor solids, exact chamfers, retained slots/tabs, subtraction-only material changes, front/back equivalence, copied exports, and the two changed standalone STL files.

**27 /27 independent exported-STEP checks pass.** The source inputs are frozen under `source-r4/step`, and the independent reports are included under `review-checks/`.

The standalone STL files were checked directly, independently of3MF:

| Check | Each changed floor STL |
| --- | ---: |
| Triangles | 1,064 |
| Welded vertices | 516 |
| Vertex welding tolerance | 0.00001 mm |
| Maximum actual weld distance | 0.0 mm |
| Boundary / non-two-manifold edges | 0 /0 |
| Inconsistently wound edges | 0 |
| Nonmanifold vertex fans | 0 |
| Degenerate / duplicate triangles | 0 /0 |
| Connected components | 1 |
| Signed volume | Positive,234,769.0771 mm³ |
| Difference from STEP volume | Approximately0.00724 mm³,3.08×10⁻⁸ relative |

The mesh Euler characteristic is−16, consistent with one closed solid containing nine through-holes. Stored facet normals agree with triangle winding. The common print STL is byte-identical to the validated rear STL.

## Files and rebuilding

- `build_geometry.py` and `design-config.json`: editable R5 source, including standalone STL verification.
- `source-r4/`: frozen R4 geometry and model inputs.
- `step/` and `stl-review/`: active R5 exports and the common floor alias.
- `model_data.json`: candidate meshes, R4 comparison parts and all checks.
- `jointScenes["floor-joint"]`: regenerated from the actual R5 floor and unchanged side receiver.
- `jointScenes["floor-top"]`: the actual complete rear/common floor for top inspection.
- `parameters.json`, `geometry-checks.json`, `source-receipts.json`: dimensions, checks and source hashes.
- `review-checks/stl-integrity.json`: detailed mesh results and exact file hashes.

From this directory:

```bash
python -m pip install -r requirements.txt
python build_geometry.py
```

Prior revisions are preserved. No repository was modified and no printer was started.
