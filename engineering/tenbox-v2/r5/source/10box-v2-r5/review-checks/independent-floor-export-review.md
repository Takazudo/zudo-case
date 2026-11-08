# R5 clipped floors — independent exported STEP review

**27/27 checks passed.** The verifier reads the candidate floor STEP exports and the frozen R4 STEP files shipped in `10box-v2-r5/source-r4/step`. It does not import the model generator, candidate parameters, or their validation reports.

| Feature | Independent result |
| --- | --- |
| Floor solids | One valid connected solid each, 5 mm thick |
| New cuts | Four through-thickness 45° corner chamfers per floor; two 12 mm legs and two 16 mm legs |
| Scope of geometry edits | Exactly the four approved corner triangles; no added material |
| Original assembly bounds | 336.8 × 144.99432 × 5 mm, unchanged |
| Floor heights | Rear Z0–5; front Z36–41, unchanged |
| Fixing slots | Nine original closed profiles and axes retained per floor |
| Local fixing material | Every 20 × 20 mm region centered on an original slot is unchanged |
| 凸 tabs | Four original 4.85 × 20 × 5 mm tabs and their inner 5 mm roots retained per floor |
| Front/rear equivalence | Same solid under 180° Z rotation and 36 mm height offset |
| Other parts | All other active STEP files byte-identical to frozen R4 |
| Exterior case width | 337.4 mm, unchanged; original side/frame datums preserved |

## Corner openings and existing lips

Each floor loses **400 mm² of projected area / 2,000 mm³ of material**: two triangular openings of 72 mm² and two of 128 mm². The openings extend 12 or 16 mm along each adjoining original edge, with diagonal edges of 16.97056 or 22.62742 mm. There are two outer-end openings and two center-step openings per floor. These are intentional openings through the floor, not closed corner joints.

The cuts reduce overlap with the small existing corner retaining lips. Both outer side lips lose their floor overlap; the center-side lips retain only small partial areas. Both end-panel corner lips retain more than 45 mm² projected overlap, and the four middle end lips remain unchanged. Exact per-lip before/after areas and the inherited source height offsets are recorded in the JSON. Projection overlap is not a claim of exact physical contact: the source lips have small positive or negative Z offsets relative to the floor top.

The side tab/receiver regions and all fixing regions remain unchanged. The changed floors introduce no additional intersection with the neighboring walls. The intentionally removed corner contacts should not be described as fully preserved.

## Fixing clearance

The closest retained slot profile is **14.579799 mm** from a new diagonal edge. A nominal OD10/ID5.5 washer has at least **14.238374 mm** clearance to the new diagonal at the slot center, or **12.192828 mm** through the nominal slot-center travel. Its contact area is unchanged at the center and both nominal travel ends. These measurements describe geometry; they do not select actual hardware or qualify fastening strength.

Run `python analysis/r5/verify_floor_exports.py` from the package root to reproduce this report. Printer placement and nozzle-area checks are separate; this review does not establish slicing or physical printing success.
