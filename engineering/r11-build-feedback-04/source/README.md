# R11-BUILD-FEEDBACK-04 — four-sided lid guides for the 7U40 metal case

R11-04 extends the lid's inside locating skirts to the **left and right sides**, matching the existing front/back guides. The four edges now locate the lid around the body opening. The additions are fused into the existing lid pieces, so the complete set still contains **20 PA12 pieces: 12 body pieces and eight lid pieces**.

The intended benefit is additional lateral locating support. This is a **CAD review candidate**; improved durability, fastening strength and transport performance have not been physically measured. The lid remains a straight lift-off cover held during transport by two external straps. Its existing screws join the lid's own pieces and aluminum plate.

The source project is [Takazudo/zudo-case](https://github.com/Takazudo/zudo-case), based on commit `b7a9e3cd1fba3a12fa8a625ab4f0f43d4a06674a` and R10-FULLSET-01 / 7u40-t1-groove1p70-m5. This round compares with the saved **R11-BUILD-FEEDBACK-03** exports. Earlier revisions remain immutable; this work applies only to the 7U40 metal case.

## What changes

| Feature | R11-03 | R11-04 |
| --- | --- | --- |
| Inside locating skirts | Front and back | Front, back, left and right |
| Locating engagement below the lid seat | 12 mm on front/back | 12 mm on all four edges, except the deliberate hardware reliefs |
| Skirt thickness | 2 mm | 2 mm |
| Nominal clearance to the inside body guard | 0.7 mm | 0.7 mm |
| Bottom-open hardware reliefs | Four on front/back | Eight total, adding four on left/right |
| Revised printed pieces in this round | — | Four lid corners and two side lid middle spans |
| Total printed pieces | 20 | 20 |

The side locating surfaces are at **X ±111.4 mm**; their 2 mm thickness extends inward to X ±109.4 mm. The front/back locating surfaces remain at **Y ±163.7 mm**. The locating skirt begins at **Z80 mm**, 12 mm below the lid seat at Z92. Its upper connecting bridge runs from Z92 to Z94.5.

The four new side reliefs are centered at **Y ±95 mm**, matching the existing body upper fixing stations. Like the four front/back reliefs at X ±59.5 mm, they are **18 mm wide**, open at the bottom and extend to **Z90.5 mm**. This accommodates the top washers and nuts over their full intended slot travel; the washer envelope reaches Z90, leaving 0.5 mm nominal vertical clearance. The remaining web below the lid seat is 1.5 mm high, joined to the 2.5 mm bridge above it.

The four corner pieces connect the new side skirts with the existing front/back skirts. The side middle spans gain their own skirt sections, with seams at the established screw-clamped overlap stations. No loose locating strips are added.

## What stays in place

All twelve body printed pieces, the two front/back lid middle spans and all six aluminum sheets retain their R11-03 geometry. Hardware definitions, quantities and nominal positions are also retained. The sheet patterns still contain **58 functional cutouts: 40 body slots, ten round rail holes and eight round lid holes**. No new sheet holes are needed for the side guides.

The body retains the inside ears introduced in R11-03: 32 integral seats at bracketed joints plus eight existing upper inside ears. The eight upper inside round washers remain because those nuts have no metal L bracket to spread their load across the long nylon slots. The loose washer total stays at **64: 40 outside body washers, eight upper inside body washers and 16 lid-wall washers**.

Body and lid nuts remain inside. The independent rail-frame-to-case attachment keeps its nuts outside the case, preserving module space. The sixteen metal L brackets, original 204 mm rails, PCB fixers/padders, spacers and rail mounting holes are retained.

## Inspect the 3D preview

Open `out/preview.html` in a browser. Its CAD meshes and renderer are embedded, so it requires no network or web server. Drag to orbit, right-drag to pan and use the wheel to zoom. There are **thirteen views**, including the new **蓋・四辺の内側ガイド** underside view and **側面ガイドのはまり** detail. The first exposes all eight lid frame pieces with the plate and hardware hidden; the second shows how a side guide fits around the body upper joint.

The panel, hardware and source-frame controls expose clearances. Exploded distances are illustrative, and the section cuts used in detail views are display boundaries rather than additional manufacturing seams. The assembled preview includes the original **66 rail-frame, PCB and mounting reference components**.

## Dimensions, hardware and material

The nominal metal body envelope remains **229.4 × 334 × 91 mm**, using 1.5 mm sheets. X runs across the short width, Y along the depth and Z upward; the floor underside is Z0. The printed guards extend beyond that metal envelope.

| Sheet | Flat dimensions, mm | Quantity |
| --- | --- | ---: |
| Bottom | 229.4 × 334 × 1.5 | 1 |
| Front/back | 224.4 × 88.5 × 1.5 | 2 |
| Left/right | 334 × 88.5 × 1.5 | 2 |
| Lid | 227.4 × 332 × 1.5, R3 corners | 1 |

The body slots remain **15.5 × 5.5 mm**, retaining the one-sided 5 mm inward extension. The 0.8 mm nylon separator occupies the 1.0 mm gap between metal edges, with 0.1 mm nominal clearance on each side. The lid retains eight plate screws and eight horizontal wall screws, all modeled as M5 × 12. The eight wall screws are at Z106 and connect lid pieces only.

The exported material totals are **87.7351 cm³ for the body** and **120.2104 cm³ for the lid**, or **207.9455 cm³ overall**. Body volume is unchanged. The lid adds **21.5785 cm³** to the R11-03 lid volume of 98.6319 cm³, increasing the complete set's PA12 volume by **11.58%**.

| Lid printed group | Quantity | Current bounding dimensions, mm | Material per piece, cm³ |
| --- | ---: | --- | ---: |
| Four corners | 4 | 91.06 × 94.05 × 43.8 | 16.8018 |
| Front/back middle spans | 2 | 89.48 × 14 × 43.8 | 8.1497 |
| Left/right middle spans | 2 | 14 × 188.1 × 43.8 | 18.3519 |

The side middle spans are 12 mm taller than in R11-03 because of the added skirt. Their length remains 188.1 mm. Across all twenty printed pieces, the longest dimension remains **210 mm**; each part passes the published 250 mm large-part size screen. The material increase is measured CAD volume, not a price estimate.

The PA12 audit lists each exported part's measured bounds, material volume and STL hash. Printed parts are exported in assembly orientation, translated so minimum XYZ is zero. That is an export datum, not a validated print orientation. The manifest records reversible placement transforms.

The loose OD15 / ID5 / t1 mm washers remain a separate home-print black ASA item reconstructed from the transformed geometry of `washers-spacer-1mm.3mf`. These exports contain no printer settings. The four provisional Ø10 × h6 rubber feet remain purchased-part/preview guidance, outside the twenty supplier PA12 pieces.

## Assembly and lid operation

The **body assembly sequence is unchanged from R11-03**. Its saved check sampled 828 positions over sixteen translations, using 1,098 exact BRep intersection checks without positive-volume collisions. That historical report is preserved as `reference/r11-03-baseline/assembly-path-check.json`. It covers nominal panel/connector sliding with brackets, fasteners, rails and lid absent; it is not a continuous sweep proof or physical assembly trial.

1. Preload each separate wall panel with its central top and bottom spans. Slide the corner pieces onto the two ends of each left/right side panel along Y, making two side subassemblies. Set the right assembly aside.
2. Slide the prepared front and back panels into the left corners along X, then slide in the floor through the open lower channels.
3. Bring the right-side subassembly inward along −X to capture the remaining panel ends and floor edge.
4. After closure, lower the metal L brackets through the open central area and move them outward onto their seats. Start the screws loosely and fit paired wall nuts before floor nuts. Keep the thin nuts at the front/back vertical-corner sites and floor sites.
5. Complete the inner body fasteners before installing the independent rail frame with its original spacers and outside nuts. Bracket insertion and general wrench/socket access were not qualified by the historical sliding check.
6. Assemble the revised lid through its existing eight plate stations and eight horizontal wall joints. Lower it vertically with all four skirts inside the opening and their reliefs aligned with the body upper fasteners. Lift vertically to remove it; use the two external straps for transport retention.

The body upper washer/nut positions, skirt clearance, sheet/coating thickness and actual printed fit remain relevant when evaluating the physical lid. The guides intentionally have clearance; no interference or snap fit is specified.

## CAD verification and its limits

The completed build passed the combined solid, contact, overlap, lid and original-reference clearance checks. All eight lid frames are single connected solids; the four locating faces and eight bottom-open reliefs are present at their intended positions. The existing sixteen body lap pairs, 240 local body bearing contacts and forty extended slots also pass their checks.

The focused lid review checks a **continuous straight vertical translation from 0 to 12.5 mm**, reversible for lowering. The swept geometry clears all 205 body components, all 66 source-frame references and sixteen full-travel envelopes for the eight upper nuts and washers. The upper lid plate and hardware remain above the highest obstruction. At the lifted endpoint, the lowest part of the lid is 0.5 mm above the highest body obstruction. This is a nominal swept-volume check, unlike the inherited sampled body assembly sequence.

The check uses exact nominal CAD for sixty original source items and conservative bounding boxes for six rail meshes. It covers straight vertical motion; tilted removal, manufacturing tolerances, tool access and physical fit are outside its scope. Its geometry input hashes and details are saved in `out/lid-locator-review.json` and repeated under `lid_locator_review` in `out/validation.json`.

The saved-export comparison is against the bundled R11-03 STEP baseline. The complete model retains **262 case/lid components**, plus 66 original references for **328 components in the full assembled preview**. Current validation distinguishes exact candidate BRep checks from source-reference bounds and inherited assembly evidence.

The prior-versus-current hardware check compares saved bounds and rounded volume; it is an envelope invariant, not a historical hardware BRep equality claim. STEP readback checks compare exported dimensions and volume with the CAD. STL checks assess watertightness, positive volume and winding. DXF outlines and cutouts are independently imported and compared with each metal sheet. These checks establish nominal geometry consistency; they do not establish physical durability, tightening torque, fatigue or a load rating. `production_approved` remains `false`.

## Pricing and supplier status

Current pricing is **unquoted**. The updated `research/jlc-pa12-pricing-audit.md` and JSON compare all twenty current PA12 exports with R11-03; every price and total remains `null`.

The published [special-charge rule](https://jlc3dp.com/help/article/3d-printing-special-charges-case), updated September 4, 2026, uses a longest bounding-box axis of **250 mm or more** as a large-part surcharge trigger. The [PA12 material page](https://jlc3dp.com/help/article/pa12-hp-nylon) advertises a USD 1 starting price without a numeric size or volume rule guaranteeing it. The [price FAQ](https://jlc3dp.com/help/article/what's-the-price-of-your-3d-printing-parts) identifies volume, process, material and quantity as pricing factors. Passing a size screen does not establish a final price tier.

The historical R10 cart totaled JPY 2,872 for body PA12 and JPY 5,068 for lid PA12. Those were displayed cart lines, excluding shipping with tax treatment unknown, and do not price this geometry. The saved record and original evidence remain in `reference/` and `research/`.

No R11-04 files have been sent to JLC. In an earlier round, automatic approval review rejected the first attempted upload before transmission because explicit authorization to send the CAD to that supplier was required. That rejection was not bypassed. A quote-only file set is prepared for a later authorized calculation; no supplier message, order, payment or new terms acceptance is included.

The earlier processing-hole audit remains applicable: no specific request for the six full-size dedicated holes was found, so their removal is retained. The floor, front and back have only joining slots, and JLC's anodizing hanging method for those sheets is still unconfirmed. See `research/hanging-hole-audit.md` for the distinction between the earlier coupon order and the full-size sheets.

## Files and rebuilding

The separately delivered `zudo-case-r11-04-changed-lid-parts.zip` contains only the **six revised lid STEP/STL pairs**, quantity one each: four corners and the left/right middle spans. The unchanged front/back middle spans complete the eight-piece lid. The complete design package and twenty-part PA12 quote set are also retained.

- `out/preview.html`: complete interactive preview with embedded assets.
- `out/pa12/`: twenty printed-part STEP/STL pairs.
- `out/aluminum/`: six sheet STEP/STL/DXF sets.
- `out/home-print/round-washer.*`: reusable circular washer model, quantity 64 in the manifest.
- `out/assembly-shell.step`: named assembly of the twenty printed pieces and six sheets.
- `out/parts-manifest.json`: dimensions, quantities, hashes, readback checks and placement transforms.
- `out/validation.json`: solid validity, component intersections, bearing/slot checks and lid review.
- `out/reference-clearance.json`: original rail-frame clearance, with exact-versus-bounds scope.
- `out/lid-locator-review.json`: four-sided guide geometry and continuous vertical lift clearance, with its source hashes.
- `out/revision-delta.json`: saved-CAD comparison against R11-03.
- `out/pa12-size-audit.json` and `.csv`: measured dimensions, volumes and price status.
- `research/`: pricing evidence and the retained processing-hole audit.
- `parameters.json`, `revision/*.py`, `build.py`: editable CAD and export source.
- `reference/r11-03-baseline/`: immutable previous-round STEP, manifest, scene and body assembly evidence. Manufacture from current `out/` files when a physical candidate is selected, not the historical comparison inputs.

With Python, CadQuery 2.7, NumPy and ezdxf installed, run from this revision directory:

```sh
python3 build.py --verify
python3 revision/review_followup.py
python3 research/build_pricing_audit.py
```

`python3 build.py --preview-only` builds the preview without manufacturing exports; `--out /absolute/path` selects a different output directory. The pricing generator expects a complete final default export, verifies all twenty STL hashes and makes no network requests. The commands do not upload, order, print or modify earlier revisions.

## Artifact saving

Save this round's complete package, preview and reports to the owner's private artifact storage, separate from earlier rounds (the storage location is withheld in this published copy). Report a successful save only after observing the upload complete.
