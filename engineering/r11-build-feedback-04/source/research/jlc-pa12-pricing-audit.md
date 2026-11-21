# R11-04 PA12 pricing audit

**Status: no current R11 supplier quote. All prices remain unknown (`null`).**

Checked 2026-11-22. 20 of 20 nylon parts pass the published 250 mm large-part size screen. That screen does **not** establish eligibility for the advertised USD 1 starting price. No numeric volume, envelope-volume, or dimension rule guaranteeing that starting tier was found in the official material page, special-charge rules, price FAQ, or pricing updates reviewed here.

## Evidence and limits

- [S1 — Current special charges](https://jlc3dp.com/help/article/3d-printing-special-charges-case), updated 2026-09-04: a longest bounding-box axis of 250 mm or more incurs an indicative surcharge starting at USD 8 per part, with 1–2 additional business days. Complex structures have a separate review-based surcharge. All fees and lead times remain subject to engineer review.
- [S2 — PA12-HP Nylon](https://jlc3dp.com/help/article/pa12-hp-nylon), updated 2026-07-30: MJF starts at USD 1, with listed wall thickness 1 mm and a maximum build size of 370 × 276 × 360 mm. The maximum build size is a manufacturing limit, not a low-price tier.
- [S3 — Price FAQ](https://jlc3dp.com/help/article/what's-the-price-of-your-3d-printing-parts): volume, process, material, and quantity affect price. The official advice is to upload the actual model for a quote. It publishes no complete formula or guaranteed minimum-price eligibility limits.
- [S5 — Historical rate announcement](https://jlc3dp.com/news/drastic-material-price-cuts-and-adjusted-post-processing-service-fees) announced USD 0.275/g for MJF-PA12, excluding tax, effective 2025-08-13. Its page header is 2025-12-26. This historical rate is not used to invent a current quote, finishing charge, density assumption, minimum, or total.
- [S6 — July 2026 update](https://jlc3dp.com/news/materials-finishing-pricing-update-july2026) changes PAC-HP Nylon and PA12-CF Plastic among other products. Those are different materials/processes from MJF PA12-HP; the reductions cannot be applied to this case.

## Every supplier PA12 part

Exported R11-BUILD-FEEDBACK-04 exact CAD dimensions and material volumes, compared with the saved R11-03 baseline; all 20 STL file hashes verified against the export manifest.

Envelope volume below is simply the product of the three bounding-box dimensions. **It is not an asserted JLC billing metric.** Material volume is the exact CAD solid volume. All parts are quantity 1, MJF PA12-HP Nylon with Dyed Black finishing for the intended quote. All 20 also fit within the published maximum build size.

| Part | Dimensions (mm) | Material (cm³) | R11-03 material (cm³) | Envelope (cm³) | 250 mm screen | USD 1 tier / price |
|---|---|---:|---:|---:|---|---|
| `body-top-front` | 139 × 4.6 × 28 | 3.3066 | 3.3066 | 17.903 | PASS | Unconfirmed / unknown |
| `body-bottom-front` | 139 × 30 × 30 | 5.8467 | 5.8467 | 125.100 | PASS | Unconfirmed / unknown |
| `body-top-back` | 139 × 4.6 × 28 | 3.3066 | 3.3066 | 17.903 | PASS | Unconfirmed / unknown |
| `body-bottom-back` | 139 × 30 × 30 | 5.8467 | 5.8467 | 125.100 | PASS | Unconfirmed / unknown |
| `body-top-right` | 4.6 × 210 × 28 | 4.2793 | 4.2793 | 27.048 | PASS | Unconfirmed / unknown |
| `body-bottom-right` | 30 × 210 × 30 | 7.2567 | 7.2567 | 189.000 | PASS | Unconfirmed / unknown |
| `body-top-left` | 4.6 × 210 × 28 | 4.2793 | 4.2793 | 27.048 | PASS | Unconfirmed / unknown |
| `body-bottom-left` | 30 × 210 × 30 | 7.2567 | 7.2567 | 189.000 | PASS | Unconfirmed / unknown |
| `body-corner--1--1` | 67.2 × 84 × 93 | 11.5891 | 11.5891 | 524.966 | PASS | Unconfirmed / unknown |
| `body-corner--1-1` | 67.2 × 84 × 93 | 11.5891 | 11.5891 | 524.966 | PASS | Unconfirmed / unknown |
| `body-corner-1--1` | 67.2 × 84 × 93 | 11.5891 | 11.5891 | 524.966 | PASS | Unconfirmed / unknown |
| `body-corner-1-1` | 67.2 × 84 × 93 | 11.5891 | 11.5891 | 524.966 | PASS | Unconfirmed / unknown |
| `lid-corner-fl` | 91.06 × 94.05 × 43.8 | 16.8018 | 14.4057 | 375.112 | PASS | Unconfirmed / unknown |
| `lid-corner-fr` | 91.06 × 94.05 × 43.8 | 16.8018 | 14.4057 | 375.112 | PASS | Unconfirmed / unknown |
| `lid-corner-br` | 91.06 × 94.05 × 43.8 | 16.8018 | 14.4057 | 375.112 | PASS | Unconfirmed / unknown |
| `lid-corner-bl` | 91.06 × 94.05 × 43.8 | 16.8018 | 14.4057 | 375.112 | PASS | Unconfirmed / unknown |
| `lid-middle-front` | 89.48 × 14 × 43.8 | 8.1497 | 8.1497 | 54.869 | PASS | Unconfirmed / unknown |
| `lid-middle-right` | 14 × 188.1 × 43.8 | 18.3519 | 12.3548 | 115.343 | PASS | Unconfirmed / unknown |
| `lid-middle-back` | 89.48 × 14 × 43.8 | 8.1497 | 8.1497 | 54.869 | PASS | Unconfirmed / unknown |
| `lid-middle-left` | 14 × 188.1 × 43.8 | 18.3519 | 12.3548 | 115.343 | PASS | Unconfirmed / unknown |

Total material: **207.9455 cm³** (87.7351 cm³ body; 120.2104 cm³ lid). The longest parts are 210 mm, leaving 40 mm below the published 250 mm surcharge trigger.

### Material effect of the four-sided lid guides

R11-04 adds the inside locating skirts to the left and right lid edges, matching the existing front/back concept: 12 mm engagement, 2 mm wall thickness and 0.7 mm nominal clearance to the body guard. Four new side reliefs clear the body upper washers and nuts. The change adds material to four lid corner pieces and two side lid middle spans; the two front/back lid middle spans and all twelve body pieces retain their R11-03 geometry.

Body nylon remains **87.735117 cm³**. Lid nylon changes from **98.631902 to 120.210402 cm³** (**+21.578500 cm³**). Total PA12 changes by **+21.578500 cm³** (**11.58%**). These are CAD material measurements, not a supplier price prediction. The part count stays at twenty; the body inner-ear design and 64 loose washers are retained from R11-03.

## What previous real price records establish

The saved [R10 cart record](../reference/r10-cart-2026-10-26.json) records 20 PA12-HP MJF, Dyed Black, quantity-1 lines on 2026-10-26. Body nylon totaled **JPY 2,872**, lid nylon **JPY 5,068**, total **JPY 7,940**. These were displayed cart prices, not final supplier-reviewed quote or invoice amounts; shipping was excluded and tax treatment was unknown.

| Old R10 part group | Qty | Dimensions (mm) | Displayed JPY per part |
|---|---:|---|---:|
| Upper corner guards | 4 | 115.55 × 167.85 × 6 | 226 |
| Vertical corner guards | 4 | 22.5 × 22.5 × 80.5 | 164 |
| Front/back lower half spans | 4 | 114.45 × 6 × 24 | 164 |
| Side lower half spans | 4 | 6 or 7 × 169.75 × 24 | 164 |
| Lid quadrants | 4 | 115.6 × 167.9 × 43.8 | 1,267 |

A roughly 169.75 mm lower span and a roughly 167.9 mm lid part had very different displayed prices. This directly rules out using length alone as a reliable predictor of the low-price tier. These prices cannot be transferred to the new geometry. The older R3 JPY 2,264 record is for twelve 1.2 mm guards, and does not price the current body or lid. The revision history documents thinner/narrower guards and long-edge splitting in R3, but does not establish an official 200 mm or other unpublished pricing boundary.

## Smallest justified design changes

1. Keep the long spans continuous for now. No current part crosses the published 250 mm trigger. Splitting a 210 mm part solely to avoid that trigger provides no proven saving and adds more parts and overlap material.
2. Retain the four-sided lid guides and the established body inside seats. They are requested locating features. Removing them solely to reduce material would undo the adopted assembly concept. Their actual price effect requires the model-specific calculator.
3. If a live quote shows material volume is dominant, trim unloaded ledges or wall area while retaining the washer bearing areas, fastened laps, locator function, and intended nominal wall thickness. Narrowing a part does not fix a longest-axis violation; here there is no such violation.
4. If actual model-specific quote evidence shows envelope or handling charges dominate, compare the continuous corners first: a body corner occupies about 525.0 cm³ of bounding box but contains about 11.59 cm³ of nylon. This is a candidate for quote comparison, not proof that JLC bills that empty space.
5. Only introduce another split if the actual before/after quote justifies it. Put any new seam at a deliberately fastened shared hole, as required by the user; do not restore free butt joints. No pricing evidence currently requires retaining the unused Y=0 station for a split.

## Loose washers and feet

The Ø15 / Ø5 / t1 washer is a separate home-print black ASA item, **0.157080 cm³ each**, not a JLC PA12 part. The saved export manifests record 64 for R11-03 and **64 for R11-04**: **40 outside body washers + 8 upper inside body washers + 16 lid-wall washers**. The four rubber feet are purchased-part/preview guidance, not exported PA12 print parts. No supplier prices are invented for either category.

## Supplier upload remains unapproved

No R11-04 upload was attempted. The user has not approved transmitting these CAD files to JLC. In the preceding audit, the [public JLC calculator](https://jlc3dp.com/3d-printing-quote) loaded in the cloud browser and exposed its model upload control. The local browser extension was unavailable. The attempted upload of the R11-01 `body-top-right.stl` was rejected by automatic approval review **before the upload occurred**. The reason returned was:

> This uploads a nonpublic CAD/STL artifact to JLC3DP, an external supplier, which is sensitive data egress; the user authorized a pricing audit but did not explicitly authorize sending this specific file to that destination, and the action creates an external copy beyond read-only inspection.

The rejection was not bypassed. **Zero R11 files were uploaded.** No order, cart save, supplier message, or payment was performed. The live calculator tab was preserved for review. Explicit permission is needed to send the following 20 R11-04 STL files to JLC3DP solely to obtain automatic MJF PA12-HP, Dyed Black, quantity-1 prices. That permission would not include order submission, external messages, payment, or acceptance of any new terms.

### Exact intended upload set

Paths are relative to the R11-04 bundle root. All files exist; their SHA-256 hashes are recorded in the companion JSON report.

- `out/pa12/body-top-front.stl`
- `out/pa12/body-bottom-front.stl`
- `out/pa12/body-top-back.stl`
- `out/pa12/body-bottom-back.stl`
- `out/pa12/body-top-right.stl`
- `out/pa12/body-bottom-right.stl`
- `out/pa12/body-top-left.stl`
- `out/pa12/body-bottom-left.stl`
- `out/pa12/body-corner--1--1.stl`
- `out/pa12/body-corner--1-1.stl`
- `out/pa12/body-corner-1--1.stl`
- `out/pa12/body-corner-1-1.stl`
- `out/pa12/lid-corner-fl.stl`
- `out/pa12/lid-corner-fr.stl`
- `out/pa12/lid-corner-br.stl`
- `out/pa12/lid-corner-bl.stl`
- `out/pa12/lid-middle-front.stl`
- `out/pa12/lid-middle-right.stl`
- `out/pa12/lid-middle-back.stl`
- `out/pa12/lid-middle-left.stl`

When uploads are authorized, record file hashes, material/finish, quantity, currency, line price, tax/shipping status, and any manual-review/surcharge flag before comparing variants. A low starting price or a successful size screen must never be substituted for that record.

## Reproducible saved inputs

Run `python research/build_pricing_audit.py` from the R11-04 bundle root after the CAD export completes. The generator requires the final export manifest, every listed STL, and the two saved reference JSON files. It verifies STL hashes before writing this report and makes no network requests. It uses no sibling repository or scratch paths.

- `reference/r11-03-baseline/parts-manifest.json` — SHA-256 `2c15b23fb74c520319610c1eeab62743c2fa47b197f5a1ffa8fc25637df699ae`
- `out/parts-manifest.json` — SHA-256 `561a7b1f42043af87e2a5145bc7b79331310ceabe3c65fdae6408bd6ae3dada6`
- `reference/r10-cart-2026-10-26.json` — SHA-256 `1420d5b8587e89980aa840b4f474e9756284a37900d8a5e320821e05965ad0c4`