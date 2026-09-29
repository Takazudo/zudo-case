# R9-PROTOTYPE-01 generator scaffold

7u40 only. This revision begins the unapproved prototype generator. Geometry hooks currently return no parts; future issues add the body, slots, guards, lid, coupons, preview, and validation.

Python 3.12 and uv are required. From this directory:

```sh
uv sync --locked && uv run python build.py
uv run python build.py --only body,slots
uv run python tests/smoke.py
```

`out/` is generated local state. It is ignored. `CONTRACTS.md` defines coordinates, names, shared dimensions, and export methods. The parameters are source-labelled; provisional and unvalidated dimensions need physical confirmation before any production decision. No output here is a manufacturing release.

## Candidate bracket slots

The body plate exports use 36 obround bracket slots (5.5 × 7.5 mm, ±1.0 mm candidate travel), with the long axis perpendicular to the joint bend line. The 10 rail-fix holes stay round φ5.5 because the independent rail frame is located by its fixer PCB. There is no intentional adjustment along the bend line; along-edge positions follow the CAD hole spacing. The nominal datums are the bottom plate's lower face and each wall's exterior face. Assemble by 仮締め → 外形/直角を整える → 本締め.

`out/aluminum/hole-table.json` lists all 46 locations; `slot-checks.json` records edge, ligament, bearing, guard-band, and nominal exterior tool-envelope results. The current provisional 10 mm outer washer fails the specified bearing overlap at 26 wall slots. An OD of at least 11.5 mm is a candidate to check for fit and availability, not a selected part. The slot size, driver envelope, fastening hardware, and physical access need coupon and assembly confirmation before manufacture.
