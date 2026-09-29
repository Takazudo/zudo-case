# R9-PROTOTYPE-01 generator scaffold

7u40 only. This revision begins the unapproved prototype generator. Geometry hooks currently return no parts; future issues add the body, slots, guards, lid, coupons, preview, and validation.

Python 3.12 and uv are required. From this directory:

```sh
uv sync --locked && uv run python build.py
uv run python build.py --only body,slots
uv run python tests/smoke.py
```

`out/` is generated local state. It is ignored. `CONTRACTS.md` defines coordinates, names, shared dimensions, and export methods. The parameters are source-labelled; provisional and unvalidated dimensions need physical confirmation before any production decision. No output here is a manufacturing release.
