# Dedicated hanging-hole audit — R11-BUILD-FEEDBACK-02

Audit date: 2026-11-21. Scope: the six Ø4 mm processing holes carried from R10-FULLSET-01 into R11-BUILD-FEEDBACK-01. This is a read-only evidence review; it does not approve a supplier process or record a new supplier instruction.

## Decision and its limit

**Remove all six dedicated Ø4 holes from the R11-02 review design, following the user's preference to omit them unless JLC specifically requires them.** The located explicit requirement to add one hole per item concerned the earlier **13 test coupons**, not the later six full-size enclosure panels. The later engineer-checked answer allowed existing hangable holes instead of an extra hole.

This is **not approval of slot-only anodizing suspension**. After removal, the floor, front and back panels have slots but no round mounting holes. JLC explicitly refused to hang the coupon parts by slots on October 6; the October 7 reply did not expressly withdraw that refusal or approve the revised full-size drawings. The two side panels each retain five round rail mounting holes, and the lid retains eight round mounting holes; suitability of those actual holes for hanging also remains conditional on JLC's process. No new supplier confirmation was sought or received during this audit.

## Supplier chronology

Times below are JST (UTC+09:00); machine-readable UTC timestamps are in the accompanying JSON. Mailbox message references are withheld in this published copy. The first five rows concern the **test-coupon order**; that is the coupon order, even when the user asks a separate question about future full-size panels.

| Date/time (JST) | Sender and scope | Evidence |
|---|---|---|
| 2026-10-06 15:24:51 | JLC; six named items in the coupon order | Requests a through hole of 3.5–5.0 mm before surface treatment. Supplier/user message (mailbox reference withheld). |
| 2026-10-06 18:25:46 | JLC; expands replacement-file request to all 13 coupons | Says one hole is sufficient; 3.5–5 mm applies to the added processing hole; explicitly rejects slots. Supplier/user message (mailbox reference withheld). |
| 2026-10-07 13:37:49 | User; explicitly separates final full-size panels from current test pieces | Asks whether existing Ø3.4/Ø5.5 mounting holes or another method can avoid extra holes, acknowledging that JLC will not use slots. Supplier/user message (mailbox reference withheld). |
| 2026-10-07 14:08:42 | User; approves replacement coupon files | Confirms one Ø4 hole added to each of the 13 test pieces; says the earlier final-panel question must not hold up this test order. Supplier/user message (mailbox reference withheld). |
| 2026-10-07 15:34:47 | JLC; engineer-checked clarification | Says an extra hole is unnecessary if the part already has holes usable for hanging. This is conditional, without approval of particular final drawings or an express exception for slots. Supplier/user message (mailbox reference withheld). |
| 2026-10-26 18:34:46–19:18:01 | JLC and user; different order (the **full-size panel order**), six full-size panels | The located exchange asks about individual part identification/labels; the user says labels are unnecessary and JLC acknowledges. It neither requires dedicated hanging holes nor approves removal of them. Initial message, user reply message, acknowledgment message. |

### Exact relevant supplier wording

October 6, supplier message:

> For the slots, we only want to hang the part using non functional holes, so we will not used the slots.

October 7, supplier message (excerpt):

> as long as the parts have holes that can be hang for surface treatment, you do not need to design an extra holes.

These statements should be read together: the later answer relaxes the need for an **additional** hole when a usable hole already exists; it does not establish that every slot is usable.

## Repository origin and carryover

1. [Issue #116](https://github.com/Takazudo/zudo-case/issues/116), created 2026-10-06 16:41:19 UTC, requests traceable replacement of the **13 R9 aluminum test coupons** following the supplier's then-current instruction. Its original source pin is `541eca7f8ebc2e6da4375108b0d66773a0868b00`; its implementation base is `9bd8e65071cb32535db5c68f41c7cca19af3e9dd`. It predates the October 7 clarification.
2. [PR #117](https://github.com/Takazudo/zudo-case/pull/117), merged 2026-10-06 18:30:51 UTC, implements one Ø4 hole in each coupon. Head: `76ac0f724fbc0c630984c0dfcab419926aceb016`; merge: `d63eb70084a502746eb9a8593fa087e6fdd5a51c`. This establishes coupon provenance, not a six-panel requirement.
3. [PR #125](https://github.com/Takazudo/zudo-case/pull/125), merged 2026-10-25 17:39:54 UTC, introduces the complete R10 prototype set and six dedicated Ø4 holes. Head: `6b787310eb5011d6c989fde086aa4f0aac257f60`; merge: `a5e002870109b18d63431aed5654bb04b11d604c`. Its description distinguishes the six processing holes from functional mounting holes and says hanging locations/fixture marks are awaiting supplier approval.
4. The R10 `parameters.json` defines all six positions; `build.py` explicitly cuts radius-2 mm disks after the five body panels' functional geometry is built, and separately cuts the lid. R10's base `fullset/geometry.py` does not put those dedicated holes into `panel_holes()`. R11-01 repeats the five body positions in `revision/body.py` and imports/cuts the lid hole in `revision/lid.py`.

**Inference, not a documented instruction:** the dedicated-hole practice appears to have carried over from the coupon revision into the full-size R10 implementation. The located R10 user-decision records do not require six dedicated holes, and no matching supplier instruction for those six full-size holes was found.

Relevant repository records:

- [`engineering/r10-fullset-01/parameters.json`](../../r10-fullset-01/parameters.json), key `hanging_holes`.
- [`engineering/r10-fullset-01/build.py`](../../r10-fullset-01/build.py), panel/lid Ø4 cuts and `supplier confirmation pending` fixture-mark note.
- [`engineering/r10-fullset-01/fullset/geometry.py`](../../r10-fullset-01/fullset/geometry.py), `FACES`, `panel_holes`, `panel`.
- `engineering/r10-fullset-01/reference/DECISIONS.md` and `project/source-notes/user-decisions.md`, recorded R10 user decisions.
- `src/content/docs/metal-case/design/r10-fullset-01.mdx`, states the Ø4 processing holes are not supplier-approved locations.
- `project/order-records/r10-fullset-01-jlc-cart-2026-10-26.md`, distinguishes ordering remarks from approved DFM/fixture-mark conditions.
- `engineering/r11-build-feedback-01/revision/body.py` (`panel_rows`) and `revision/lid.py` (`_reference` and the lid plate cut), immediate R11-01 carryover.

## Six holes being removed

All are **Ø4 mm through holes**. Local coordinates are the face-local CAD coordinates in R10 `hanging_holes`, retained by R11-01. World positions are axis intersections with the body exterior datum planes, and with the lid underside for the lid; they are not sheet mid-plane positions. X spans the 229.4 mm width, Y the 334 mm depth, Z points upward, and the floor underside is Z=0.

| Panel | Local coordinates, mm | World datum position [X,Y,Z], mm | Round functional holes remaining after removal |
|---|---:|---:|---|
| Floor | [0, 0] | [0, 0, 0] | None; panel joints use slots |
| Front | [0, 45] | [0, −167, 45] | None; panel joints use slots |
| Back | [0, 45] | [0, 167, 45] | None; panel joints use slots |
| Left | [65, 26] | [−114.7, −65, 26] | Five rail mounting holes |
| Right | [65, 26] | [114.7, 65, 26] | Five rail mounting holes |
| Lid | [0, 0] | [0, 0, 122] | Eight perimeter mounting holes |

## Search limits

Reviewed relevant JLC hanging/anodizing/holes correspondence, the coupon order, later supplier order-issue messages, and the six-panel order; also reviewed the linked GitHub issue/PR records and local code/docs. The local checkout is shallow, so PR/issue metadata and file patches were checked through read-only GitHub access. No later contrary instruction was found in those searches. This is not a claim that every possible supplier communication was exhaustively inspected. Historical R9/R10 evidence remains historical; the R11-02 removal decision must not be described as retroactive supplier approval.
