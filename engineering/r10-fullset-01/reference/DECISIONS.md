# Decision ledger — 2026-10-26

## Explicit user decisions

The next outsourced purchase will be **one complete 7U40 case set**, not another small sample order. Repeated supplier orders cost money; the extra coupon-first stage is rejected. The actual order will be handled after this local Codex implementation produces the files.

The requested outputs are: updated 3D preview, updated documentation, washer STLs, all metal sheet data, and all outsourced 3DP data.

All washer design work is separate from supplier ordering. Washers will be home-printed in black ASA and may be adjusted and reprinted without a new supplier purchase. Preserve the R2 appearance: the exterior washer stays within its connected rectangular pad, rather than protruding as an oval.

The full case uses the accepted fastened lower/vertical guards, 1mm internal panel/bracket protection on both contacting faces, slots lengthened by 3mm total, and the central 1mm + 1mm stepped lap. Keep the merged M5 lid assembly and no lid-to-body lock.

## Reported physical observations, not invented test certificates

The user reported good PA12/black-anodized surface quality, adhesive bonding with an unsatisfactorily loose upper-channel fit, and insufficient slot allowance after inserting internal protection. Thin guard profiles felt acceptable. The concern that rubbing/impacts may eventually detach adhesive-only guards is a predicted failure mode, not a recorded long-duration test result.

## Working defaults selected for this handoff

Use one order profile with 1.0mm thin guard sections and 1.70mm upper groove around nominal t1.5 sheet. Keep 5mm insertion depth. Retain 1mm fastening ears, with 2mm total at the overlap. Use 5.5 x 10.5mm bracket slots, the original ten rail round holes, and a nominal +1mm inward bolt displacement for the new internal shims.

These are candidate dimensions chosen to proceed from the accepted R2 direction. They are not claims of measured printed fit. The 0.8mm thin-wall and 1.5/1.6mm groove comparisons do not enter the supplier set. Local corrections for demonstrated interference or manufacturability are allowed and must be recorded, not used to reopen the coupon-first purchasing strategy.

M5 lid start values follow PR124: hole5.5, pocket AF8.4, usable depth5.5, roof1.5, boss7.0, wall target1.6, edge-to-axis5.5mm. Recalculate its frame and plate against the new guard perimeter and seat.

## Washer baseline, from R2 source inventory

| Type | Shape / mm | Count | Destination |
| --- | --- | ---: | --- |
| Vertical exterior | Rounded rectangle16 x 12 x 1, R1.5, bore5.5 centered | 16 | Home ASA |
| Lower exterior, including lap | Rounded rectangle14 x 16 x 1, R1.5, bore5.5 offset1 toward panel edge | 10 | Home ASA |
| New internal panel/bracket protection | Capsule20 x 12 x 1, bore5.5 | 36 | Home ASA |
| Bottom exterior slot cover | Capsule20 x 12 x 1, bore5.5 | 10 | Home ASA |
| Retained bottom-bracket circular washer | Existing reference; inventory separately | 10 | Reuse/home replacement, not PA12 order |

72 newly modeled washer/pad instances, not 72 unique files. The final assembly also needs an explicit rail-mount/other hardware inventory. Counts come from generated instance lists, never guessed from unique file counts. Keep washer-only parameter changes independent of metal/PA12 regeneration, except when a deliberate interface thickness change requires stack revalidation.

## Remaining technical work, not paid-sample gates

Combine R2 guards, native rails/PCBs, shifted brackets and merged M5 lid. Validate actual STEP/DXF/STL and same-geometry preview. Calculate allowed washer travel and bearing margins without hiding the limited range of compact caps. Maintain truthful status for unknown printed fit, torque, creep and transport durability; these are evaluated on the full prototype rather than used to demand another supplier coupon round.

## Permission

Planning is read-only. The separate local implementation may edit, commit, push, create/update a PR and conditionally merge under current policy. Its final merge commit must include `[skip deploy]` under the current workflow guard. No deployment, release, supplier email/upload, purchase/payment, order submission or production certification is authorized.
