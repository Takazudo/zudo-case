# F5 rail/frame integration

2026-10-05 · Source-based viewing geometry · **Not a fabrication release**

## 1. What F4 actually contained

F4 retained nominal footprints and family dimensions, but drew its rails as rectangular bars and its side frames as solid rectangular placeholders. That did not reproduce the saved rail mesh or the PCB side-frame design. F5 replaces those stand-ins in **both trays**.

The surrounding enclosure is still the two-way F4/F5 study. Reusing its frame does not mean the entire R9 metal enclosure, guard geometry or manufacturing release has been imported.

## 2. Source and fidelity

The source snapshot is `Takazudo/zudo-case@6a13d80d816b0247ab9eee761c29c1fb786b76cc`. Assets are from `engineering/r6-body/source-data/`, with the assembly convention in `engineering/r6-body/build_geometry.py`. The source project records upstream rail commit `0f7316ad9000b7906e5769aa89aff2dc18c661c8` and PCB commit `b4db88ce5c93709f3f2f0a031f75190081f02443`.

| Component | Fidelity in this package |
|---|---|
| 204 mm / 40HP rail | Original full JSON, verified against Git blob; every mesh triangle retained |
| 305 mm / 60HP rail | Original full JSON, verified against Git blob; every mesh triangle retained |
| 3U / 7U fixer outside shape | Source Edge.Cuts vertices in the correct normalized coordinate system |
| 3U / 1U padder outside and rectangular cutouts | Source polygon coordinates, including original offsets |
| Rounded fixer holes and slots | Display approximations to source contour bounds; **not exact manufacturing contours** |
| Mounting axes, row spacing, layer placement | Source assembly datums; no symmetry correction or hole recentering |
| Screws, nuts, washer diameters, protective covers | Provisional viewing geometry; not purchase dimensions or a drilling plan |

Only the two rail JSON copies are byte-identical upstream files. `sourceBlobSHA` in a derivative PCB record identifies its upstream source, not a claim that its triangulation is identical to that source. The full original KiCad files remain in the repository and are not bundled here. Use them for production work.

The original rail mesh has source duplicate/non-manifold surfaces. They are deliberately not repaired or simplified in F5. The GLBs are viewing meshes, not watertight printable rail replacements. Sliding/threaded inserts and real module hardware are not manufacturing-defined by these models.

## 3. Per-tray arrangements

A uses a single original 3U/60HP assembly: two rails, two fixer boards and two padder boards, with four side mounting stacks.

B uses **two independent original 3U/60HP assemblies**, one per row. Their PCB exteriors are 1 mm apart. There is no newly stretched or invented 6U side PCB. The common metal shell is a new enclosure integration, not a new frame component. Its row-direction outside dimension changes to 290 mm.

C uses the original 7U/40HP fixer on each side. Each side also has two 3U padders and one 1U padder; six 40HP rails span the three rows. There are five side mounting stacks per side. The deep, chamfered 7U fixer remains intact.

The same arrangement is repeated in the upper tray. Counts in FRAME-PART-COUNTS.csv show per-tray and two-tray totals; they are not a complete case BOM.

## 4. Coordinate conventions and fixed stack

F5 local coordinates: X runs along the rail, Y along the rows, and Z points out from the modules. The visible module-front face is Z=0; its illustrative 2 mm panel occupies Z=-2 to 0.

The source rail raw long axis is Z. The original proper rotation is retained: alternating rails reverse raw long/transverse axes together, with determinant +1. No scale operation is used. Source `cx=14.930564880371094` and `cy=6.7535858154296875` locate the screw axis within the rail cross-section.

PCB normalization uses the source 3U U/V axes, and swaps raw X/Y for the 7U source board. Extrusion thickness is 1.6 mm. Padder starts at the rail end; fixer starts a further 1.6 mm outward. Thus:

```
rail L + 2 × (padder 1.6 + fixer 1.6) = frame outside width
305 + 6.4 = 311.4 mm (60HP)
204 + 6.4 = 210.4 mm (40HP)
```

Outside each fixer is the specified 8 mm side spacer, then the metal wall, then the 1 mm outer washer and schematic nut. Frame mounting heads occupy the source 1.4 mm study height. Existing slight hole and padder offsets are intentionally not recentered.

The 7U padder placements remain (U,V) = (0,0), (134.531860,0), and (269.039027,-0.025081). The corresponding reference rectangles are not normalized to force their holes into ideal centers.

## 5. The 7U depth correction

The source 3U padder is 30 mm deep; the 3U fixer is 29.990042 mm deep. Aligning the actual rail top to the underside of the 2 mm module panel places the PCB front edge at Z=-1.900247 mm. The assembly reaches **31.900247 mm** behind the panel front.

The 7U fixer reaches **60.015381 mm** from its own front edge. Its front-edge datum is Z=-1.935544 mm, so the actual rear reach is **61.950925 mm**. This is board depth, not a module-depth assumption.

```
Old C lid: 48 - 1.5 back plate - 61.950925 frame = -15.450925 mm
New C lid: 70 - 1.5 back plate - 61.950925 frame =  +6.549075 mm
```

The viewer does not trim the source frame when a shallower lid is selected. It displays a warning and keeps the original board dimensions. The 6.55 mm clearance is to a flat inside back plate, not a guarantee against unknown wiring, fasteners, power boards, print tolerance, bow or support details.

A and B retain 48 mm lids and have 14.599753 mm nominal frame-to-back clearance. Their provisional module-body depth remains a separate budget: 48 - 1.5 - 2 - 10 = 34.5 mm before local obstructions. C's corresponding body budget is 56.5 mm, but this does not certify any particular module or power layout.

## 6. Collar interference corrected around the real frame

At 1.5 mm metal, the outer frame edge is 9.5 mm inward of the outer case wall: 1.5 mm metal + 8 mm spacer. F4's inward locator extent was 12.1 mm, which reaches into the real frame envelope. F4 checked dummy panel edges rather than the complete source side frame.

F5 moves the fixed seating return and collar inner tongue toward the outside. With the default 0.6 mm fit input, the inward extent is 7.1 mm. This yields **2.4 mm side clearance** to the PCB-frame envelope. Nominal end clearances are 2.6341 mm (A), 2.8681 mm (B) and 2.5228 mm (C). These are envelope comparisons, not full continuous collision analysis or a tolerance release.

The seating land is now 3.5 mm wide. Its structural suitability and fabrication as bends or separate stock angles are not established by this correction. Do not infer durability from cleared geometry alone. Extreme thicker-sheet / larger-fit-gap inputs can reduce source-frame clearance below 1 mm; the viewer warns instead of shrinking the frame.

## 7. Hardware and packing corrections

The actual source mounting locations are represented on both sides and both trays. Small rounded protective-cover envelopes conceal the external nut/shaft study. Each can project up to 8 mm beyond the metal side. This replaces the earlier 5 mm generic outside allowance, adding 6 mm to the reported closed width. Cover hollowness, retention, material and exact nut clearance still need design; these are not printable cover files.

| Family | Metal W × D | Base / lid rear | Closed instrument W × D × H |
|---|---|---|---|
| A | 330.4 × 154 mm | 80 / 48 mm | 346.4 × 176 × 208 mm |
| B | 330.4 × 290 mm | 80 / 48 mm | 346.4 × 312 × 208 mm |
| C | 229.4 × 334 mm | 91.5 / 70 mm | 245.4 × 356 × 241.5 mm |

These default dimensions use the 72 mm patch-gap study and include modeled guards, guides, covers and feet. No outer trunk is included in the instrument dimensions. The trunk control example is 420 × 420 × 330 mm **inside**, not a selected retail product. Stand and padding budgets remain explicit in the viewer.

Nominal mounting axes are supplied in MOUNT-DATUMS.json. They are not drill sizes, countersink locations, edge-distance approval or finished sidewall CAD. The viewing shell does not subtract final bores; fastener shafts intentionally pass through that schematic sheet.

## 8. What did not change

The trays remain mechanically independent during play. No loaded-lid hinge, linkage or lifting mechanism was added. The upper tray sits on the flat-pack 45° stand. The removable collar locates the packed trays; captured non-elastic strap concepts retain seating. The assembly is intended for a suitably restrained padded trunk. Strap ratings, seam retention, frame strength, case distortion, stand stability, electrical bonding, heat and real cable turnover remain physical engineering tasks.

## 9. Review before making parts

Measure actual rail length, PCB layer thickness, the complete 7U side-board rear reach and the available shallow-lid space. Trial the specified 8 mm spacer stack and real fasteners. Check the new collar at a frame corner and alongside actual module screws. Check assembly/tool access, stand/trunk fit and fixed-length cross-tray leads with restrained dummy loads.

The source meshes and successful browser checks are not a manufacturing release. No repository files were changed during this prototype update.
