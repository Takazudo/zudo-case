"""Build deterministic, explicitly unapproved R9 quote/fit packages."""
from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile

from r9.common import sha256_file, write_zip


R9_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = R9_ROOT.parents[1]
OUT = R9_ROOT / "out"
CANDIDATE = REPO_ROOT / "public" / "downloads" / "candidate"
LIMIT_BYTES = 25 * 1024 * 1024
TOTAL_NEW_FILE_LIMIT_BYTES = 40 * 1024 * 1024

PACKAGE_NAMES = {
    "aluminum": "7u40-r9-prototype-01-aluminum-NOT-APPROVED.zip",
    "pa12": "7u40-r9-prototype-01-pa12-NOT-APPROVED.zip",
    "coupons": "7u40-r9-prototype-01-coupons-NOT-APPROVED.zip",
}

OUTPUT_MANIFEST = OUT / "outputs-manifest.json"
SIZE_INVENTORY = OUT / "SIZE-INVENTORY.json"

# Keep this list explicit so a clean checkout and a dirty working tree report
# the same inventory. Every entry is a file added by this packaging issue.
NEW_COMMITTED_FILES = (
    "engineering/r9-prototype-01/r9/package.py",
    "engineering/r9-prototype-01/tests/test_package.py",
    "engineering/r9-prototype-01/out/bom.json",
    "engineering/r9-prototype-01/out/bom.csv",
    "engineering/r9-prototype-01/out/DIFF-FROM-R6-R8.md",
    "engineering/r9-prototype-01/out/outputs-manifest.json",
    "engineering/r9-prototype-01/out/SIZE-INVENTORY.json",
    *(f"public/downloads/candidate/{name}" for name in PACKAGE_NAMES.values()),
)


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _readme(category: str) -> bytes:
    shared = """ZUDO CASE R9-PROTOTYPE-01 / 7U40

製作候補・未承認・参考見積用のファイルです。発注、製造承認、または製作リリースではありません。
G01–G11 は未完了です。形状が出力されていても、製造可否を承認したことにはなりません。

単位は mm です。寸法・材料・公差・金具の適合を加工先と現物で確認してください。
本データは現物嵌合、強度、落下、疲労、接着保持、バンド強度、運搬試験を証明しません。
必要な小片試作と組立・持ち運び確認が終わるまで、最終品の発注や製造に使わないでください。

"""
    scopes = {
        "aluminum": """収録範囲: 7U40 本体５枚と蓋板の STEP/DXF、穴テーブル、長穴チェック。
材料は A5052・t1.5 mm・黒アルマイトの候補です。加工先、材質証明、表面処理、板取りは未確定です。
長穴36か所は 5.5 × 7.5 mm、移動量±1.0 mmの候補です。レール固定穴10か所はφ5.5 mm丸穴です。
現在の10 mm外径ワッシャー案は壁側の複数箇所で必要な受け代を満たしません。必要外径11.5 mm以上は確認候補で、選定済み寸法ではありません。
長穴方向、ワッシャー、ねじ、加工公差と工具アクセスを確認してください。アルミ板の STL、金具包絡、レール、PCB はこのZIPに含めません。
""",
        "pa12": """収録範囲: PA12 ガード t1.2 mm（主候補）、t1.0 mm（比較候補）、および４分割の蓋フレームの STEP/STL と数量表。
ガードの被覆幅は5 mm候補です。保持・接着・嵌合・材料公差は現物で未確認です。t1.0 mmは比較用で、t1.2 mmと同等の採用判断ではありません。
ガードは保護カバーであり、構造接合部として使う部品ではありません。
蓋は直線的な載せ蓋候補です。蓋と本体を固定するロックは含みません。フレームと蓋板のねじは組立部品ですが、ねじ長さ・ナット・工具アクセスは未確定です。
蓋上がり30 mm、モジュール板2 mm＋ノブ25 mm、ケーブルを外す前提は表示上の仮定です。各モジュールのノブ・ケーブルとの隙間を確認したものではありません。
蓋のガード座面干渉と接着層が未解決です。蓋フレームの塗装・染色条件も加工先と確認してください。
""",
        "coupons": """収録範囲: ガード断面・蓋位置決め・長穴/ブラケットの C1、C2、C3 候補クーポンと、パッケージ内相対パスに直した coupon-manifest.json。
これらは小片の寸法・組立を現物で確認するための候補データです。印刷や切削を行った結果、保持力、量産公差、製品全体の安全性が確認済みになるわけではありません。
クーポン数量は比較条件ごとの試験片数です。各ファイルの用途と個数は manifest を確認してください。
""",
    }
    return (shared + scopes[category]).encode("utf-8")


def _package_manifest(category: str, entries: dict[str, bytes]) -> bytes:
    files = []
    for name in sorted(entries):
        raw = entries[name]
        if len(raw) >= LIMIT_BYTES:
            raise ValueError(f"package entry exceeds 25 MiB: {category}/{name}")
        files.append({"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    return _json_bytes({
        "schema": "zudo-case-r9-candidate-package-v1",
        "revision": "R9-PROTOTYPE-01",
        "model": "7u40",
        "package": category,
        "units": "mm",
        "status": "unapproved_prototype",
        "manufacturingApproved": False,
        "files": files,
        "manifestNote": "This manifest lists every other ZIP entry; its own hash is not self-embedded.",
    })


def _add_file(entries: dict[str, bytes], zip_path: str, source: Path,
              *, expected_sha256: str | None = None,
              expected_bytes: int | None = None) -> None:
    if zip_path in entries:
        raise ValueError(f"duplicate package path: {zip_path}")
    raw = source.read_bytes()
    if len(raw) >= LIMIT_BYTES:
        raise ValueError(f"source file exceeds 25 MiB: {source}")
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError(f"source hash mismatch: {source}")
    if expected_bytes is not None and len(raw) != expected_bytes:
        raise ValueError(f"source byte count mismatch: {source}")
    entries[zip_path] = raw


def _resolve_repo_or_r9(relative_path: str) -> Path:
    rel = Path(relative_path)
    candidates = (R9_ROOT / rel, REPO_ROOT / rel)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(relative_path)


def _load_and_verify_build_log() -> dict:
    path = OUT / "build-log.json"
    if not path.is_file():
        raise FileNotFoundError("Run the complete R9 generator first; out/build-log.json is missing.")
    build_log = _load_json(path)
    if build_log.get("revision") != "R9-PROTOTYPE-01" or build_log.get("model") != "7u40":
        raise ValueError("packaging requires the R9-PROTOTYPE-01 7u40 build log")
    if build_log.get("geometryStatus") != "unapproved prototype candidate":
        raise ValueError("build log is missing the unapproved-prototype status")
    for record in build_log.get("outputs", []):
        name = record.get("path", "")
        if not name.startswith("out/"):
            continue
        source = R9_ROOT / name
        if not source.is_file():
            raise FileNotFoundError(f"build-log output missing: {name}")
        if source.stat().st_size != record.get("bytes") or sha256_file(source) != record.get("sha256"):
            raise ValueError(f"build-log output hash mismatch: {name}")
    return build_log


def _plate_entries() -> tuple[dict[str, bytes], list[dict]]:
    current_spec = _load_json(REPO_ROOT / "project" / "current-spec.json")
    model = current_spec["models"]["7u40"]
    body_manifest = _load_json(OUT / "hardware-envelopes" / "body-manifest.json")
    lid_manifest = _load_json(OUT / "pa12" / "lid" / "manifest.json")
    expected = {
        "7U40-R9-AL-BOTTOM": ("底板", "bottom"),
        "7U40-R9-AL-FRONT-BACK": ("前後板", "front_back"),
        "7U40-R9-AL-LEFT-RIGHT": ("左右板", "left_right"),
    }
    current = {str(plate["role"]): plate for plate in model["plates"]}
    components = {component["id"]: component for component in body_manifest["components"]}
    entries: dict[str, bytes] = {}
    table = []
    for part_id, (label, role) in expected.items():
        component = components.get(part_id)
        plate = current.get(role)
        if component is None or plate is None:
            raise ValueError(f"missing aluminum plate definition: {part_id}")
        quantity = int(component["quantity"])
        if quantity != int(plate["quantity"]):
            raise ValueError(f"plate quantity mismatch: {part_id}")
        table.append({
            "partId": part_id,
            "name": label,
            "quantity": quantity,
            "dimensionsMm": plate["size_mm"],
            "material": "A5052 t1.5 mm; black anodizing (candidate)",
            "status": "candidate; not approved for manufacture",
            "holeCountPerPlate": plate["holes_each"],
        })
        for extension in ("step", "dxf"):
            file_name = f"{part_id.lower()}-qty{quantity}-mm.{extension}"
            source = OUT / "aluminum" / file_name
            _add_file(entries, f"plates/{file_name}", source)

    lid_id = "7U40-R9-LID-PLATE"
    if lid_id not in lid_manifest["parts"]:
        raise ValueError("lid plate is missing from the R9 lid manifest")
    lid_params = _load_json(R9_ROOT / "params" / "lid.json")
    lid_thickness = float(lid_params["plate_thickness"]["value"])
    lid_size = [*model["lid_preview"]["lidPlateMm"][:2], lid_thickness]
    lid_row = {
        "partId": lid_id,
        "name": "蓋板",
        "quantity": 1,
        "dimensionsMm": lid_size,
        "material": "A5052 t1.5 mm; black anodizing (candidate)",
        "status": "candidate; R8-derived lid dimensions remain provisional",
        "holeCountPerPlate": 8,
    }
    table.append(lid_row)
    for extension in ("step", "dxf"):
        file_name = f"{lid_id.lower()}-qty1-mm.{extension}"
        _add_file(entries, f"plates/{file_name}", OUT / "aluminum" / file_name)

    table.sort(key=lambda item: item["partId"])
    _add_file(entries, "hole-table.json", OUT / "aluminum" / "hole-table.json")
    _add_file(entries, "slot-checks.json", OUT / "aluminum" / "slot-checks.json")
    return entries, table


def _guard_table() -> tuple[dict[str, bytes], dict]:
    entries: dict[str, bytes] = {}
    variants = []
    for variant, label, thickness, directory in (
        ("t1p2", "main candidate", 1.2, "main-t1p2"),
        ("t1p0", "comparison only", 1.0, "comparison-t1p0"),
    ):
        manifest = _load_json(OUT / "pa12" / "guards" / variant / "manifest.json")
        parts = []
        for part in manifest["parts"]:
            file_records = []
            for record in sorted(part["files"], key=lambda entry: Path(entry["path"]).suffix):
                source = _resolve_repo_or_r9(record["path"])
                zip_path = f"guards/{directory}/{source.name}"
                _add_file(entries, zip_path, source,
                          expected_sha256=record["sha256"], expected_bytes=record["bytes"])
                file_records.append({"format": source.suffix.lstrip("."), "path": zip_path})
            parts.append({
                "partId": part["id"],
                "quantity": part["quantity"],
                "dimensionsMm": part["mesh"]["dimensionsMm"],
                "files": file_records,
            })
        variants.append({
            "variant": variant,
            "role": label,
            "thicknessMm": thickness,
            "coverMm": 5,
            "material": "PA12-HP dyed black candidate",
            "quantity": sum(part["quantity"] for part in parts),
            "retention": manifest["retention"],
            "parts": parts,
        })

    lid_manifest = _load_json(OUT / "pa12" / "lid" / "manifest.json")
    lid_parts = []
    for record in sorted(lid_manifest["deliverables"], key=lambda entry: (entry["partId"], entry["path"])):
        source = _resolve_repo_or_r9(record["path"])
        zip_path = f"lid-frame/{source.name}"
        _add_file(entries, zip_path, source,
                  expected_sha256=record["sha256"], expected_bytes=record["bytes"])
        lid_parts.append({
            "partId": record["partId"],
            "quantity": 1,
            "format": source.suffix.lstrip("."),
            "path": zip_path,
        })
    quantity_table = {
        "schema": "zudo-case-r9-pa12-quantities-v1",
        "revision": "R9-PROTOTYPE-01",
        "model": "7u40",
        "units": "mm",
        "status": "unapproved_prototype",
        "guards": variants,
        "lidFrame": {
            "material": "PA12-HP; lid-frame finish not confirmed",
            "quantity": 4,
            "parts": lid_parts,
            "fitStatus": "candidate; physical fit and screw access unvalidated",
        },
        "manufacturingApproved": False,
    }
    entries["quantities.json"] = _json_bytes(quantity_table)
    return entries, quantity_table


def _coupon_entries() -> tuple[dict[str, bytes], dict]:
    source_path = OUT / "coupons" / "coupon-manifest.json"
    source_manifest = _load_json(source_path)
    package_manifest = copy.deepcopy(source_manifest)
    entries: dict[str, bytes] = {}
    families = set()
    for coupon in package_manifest.get("coupons", []):
        coupon_id = str(coupon["id"])
        family = coupon_id.split("-", 1)[0]
        if family not in {"C1", "C2", "C3"}:
            raise ValueError(f"unexpected coupon family: {coupon_id}")
        families.add(family)
        rewritten = []
        for record in coupon.get("fileHashes", []):
            source_rel = record["path"]
            source = _resolve_repo_or_r9(source_rel)
            zip_path = f"coupons/{family}/{coupon_id}/{source.name}"
            _add_file(entries, zip_path, source,
                      expected_sha256=record["sha256"], expected_bytes=record["bytes"])
            updated = dict(record)
            updated["path"] = zip_path
            rewritten.append(updated)
        coupon["fileHashes"] = rewritten
    if families != {"C1", "C2", "C3"}:
        raise ValueError(f"coupon manifest families are incomplete: {sorted(families)}")
    package_manifest["packagePathRoot"] = "."
    package_manifest["packageScope"] = ["C1", "C2", "C3"]
    package_manifest["packageNote"] = (
        "fileHashes paths are relative to this ZIP root; source inputs remain provenance references."
    )
    entries["coupon-manifest.json"] = _json_bytes(package_manifest)
    return entries, package_manifest


def _write_package(category: str, entries: dict[str, bytes]) -> Path:
    entries = dict(entries)
    entries["READ-BEFORE-ORDER.txt"] = _readme(category)
    entries["package-manifest.json"] = _package_manifest(category, entries)
    destination = CANDIDATE / PACKAGE_NAMES[category]
    write_zip(destination, entries)
    if destination.stat().st_size >= LIMIT_BYTES:
        raise ValueError(f"candidate ZIP exceeds 25 MiB: {destination}")
    with zipfile.ZipFile(destination) as archive:
        names = archive.namelist()
        if names != sorted(names) or len(names) != len(set(names)):
            raise ValueError(f"ZIP paths are not unique and sorted: {destination}")
        if any(info.file_size >= LIMIT_BYTES for info in archive.infolist()):
            raise ValueError(f"candidate ZIP has a file >= 25 MiB: {destination}")
        bad = archive.testzip()
        if bad:
            raise ValueError(f"ZIP CRC failure in {destination}: {bad}")
    return destination


def _bom_rows() -> tuple[dict, list[dict]]:
    build_log = _load_json(OUT / "build-log.json")
    body = _load_json(OUT / "hardware-envelopes" / "body-manifest.json")
    lid_manifest = _load_json(OUT / "pa12" / "lid" / "manifest.json")
    body_component = {part["id"]: part for part in body["components"]}
    body_spec = _load_json(REPO_ROOT / "project" / "current-spec.json")["models"]["7u40"]
    plate_spec = {plate["role"]: plate for plate in body_spec["plates"]}

    items: list[dict] = []
    for part_id, role, name in (
        ("7U40-R9-AL-BOTTOM", "bottom", "底板"),
        ("7U40-R9-AL-FRONT-BACK", "front_back", "前板・後板"),
        ("7U40-R9-AL-LEFT-RIGHT", "left_right", "左右板"),
    ):
        component = body_component[part_id]
        plate = plate_spec[role]
        if int(component["quantity"]) != int(plate["quantity"]):
            raise ValueError(f"BOM body plate quantity mismatch: {part_id}")
        items.append({
            "id": part_id, "section": "aluminum", "name": name,
            "quantity": component["quantity"], "unit": "piece",
            "dimensionsMm": plate["size_mm"],
            "material": "A5052 t1.5 mm; black anodizing (candidate)",
            "status": "candidate; not approved for manufacture",
            "unitPriceJpy": None, "lineTotalJpy": None,
            "costTreatment": "unquoted",
            "notes": "R6-body-derived R9 candidate geometry; verify material, finish, tolerances, and flat pattern with the fabricator.",
        })

    lid_params = _load_json(R9_ROOT / "params" / "lid.json")
    lid_dims = [*body_spec["lid_preview"]["lidPlateMm"][:2], lid_params["plate_thickness"]["value"]]
    if "7U40-R9-LID-PLATE" not in lid_manifest["parts"]:
        raise ValueError("R9 lid manifest has no aluminum lid plate")
    items.append({
        "id": "7U40-R9-LID-PLATE", "section": "aluminum", "name": "蓋板",
        "quantity": 1, "unit": "piece", "dimensionsMm": lid_dims,
        "material": "A5052 t1.5 mm; black anodizing (candidate)",
        "status": "R8-derived candidate; dimensions and assembly fit remain provisional",
        "unitPriceJpy": None, "lineTotalJpy": None,
        "costTreatment": "unquoted",
        "notes": "Aluminum lid sheet paired with the separate PA12 locating frame; not a locking lid.",
    })

    for variant, section, thickness, note in (
        ("t1p2", "pa12_guard_main", 1.2, "Main candidate"),
        ("t1p0", "pa12_guard_comparison", 1.0, "Comparison only; separate from the main candidate"),
    ):
        manifest = _load_json(OUT / "pa12" / "guards" / variant / "manifest.json")
        for part in manifest["parts"]:
            role = part["id"].split(f"GUARD-{variant.upper()}-", 1)[-1]
            part_name = {
                "TOP-A": "上端コーナーガード A",
                "TOP-B": "上端コーナーガード B",
                "LOWER-WIDTH-HALF": "前後下辺ガード・半分",
                "LOWER-DEPTH-A": "左右下辺ガード・半分 A",
                "LOWER-DEPTH-B": "左右下辺ガード・半分 B",
                "VERTICAL-CORNER": "縦辺コーナーガード",
            }.get(role, role)
            items.append({
                "id": part["id"], "section": section, "name": part_name,
                "quantity": part["quantity"], "unit": "piece",
                "dimensionsMm": part["mesh"]["dimensionsMm"],
                "thicknessMm": thickness, "coverMm": 5,
                "material": "PA12-HP dyed black candidate",
                "status": note.lower(), "unitPriceJpy": None, "lineTotalJpy": None,
                "costTreatment": "unquoted",
                "notes": "Protective cover only; not a structural joint. Retention, adhesion, material tolerance, and fit are unvalidated.",
            })

    for part_id in lid_manifest["parts"]:
        if not part_id.startswith("7U40-R9-PA12-LID-FRAME-"):
            continue
        items.append({
            "id": part_id, "section": "pa12_lid_frame", "name": f"蓋フレーム {part_id.rsplit('-', 1)[-1]}",
            "quantity": 1, "unit": "piece", "dimensionsMm": None,
            "material": "PA12-HP; lid-frame finish not confirmed",
            "status": "candidate; physical fit not validated",
            "unitPriceJpy": None, "lineTotalJpy": None,
            "costTreatment": "unquoted",
            "notes": "Four separate locating-corner parts. Assembly screws/nuts are listed below.",
        })

    coupon_source = _load_json(OUT / "coupons" / "coupon-manifest.json")
    coupons = []
    for coupon in coupon_source["coupons"]:
        coupons.append({
            "id": coupon["id"], "section": "coupon", "name": coupon["purpose"],
            "quantity": coupon["quantity"], "unit": "coupon units per source manifest",
            "fileCount": len(coupon.get("fileHashes", [])),
            "files": [Path(record["path"]).name for record in coupon.get("fileHashes", [])],
            "quantityMeaning": ("one candidate scenario assembly; component CAD files are listed separately"
                                if str(coupon["id"]).startswith("C2-") else
                                "physical coupon count recorded by the source manifest"),
            "status": "candidate physical-fit coupon; result not tested",
            "unitPriceJpy": None, "lineTotalJpy": None,
            "costTreatment": "unquoted",
            "notes": "Coupon manifest distinguishes the comparison setup from the count of CAD component files.",
        })

    quantities = {item["id"]: item["qty"] for item in build_log["parts"]}
    params = _load_json(R9_ROOT / "params" / "body.json")
    bracket = body["brackets"]
    hardware = [
        {
            "id": "existing-stock-bracket-20x20x16", "section": "hardware", "name": "在庫L字ブラケット",
            "quantity": bracket["count"], "unit": "piece", "dimensionsMm": bracket.get("dimensionsMm", [20, 20, 16]),
            "measuredThicknessMm": body["parameters"]["bracket_thickness"]["value"],
            "material": "Existing metal stock; alloy unconfirmed",
            "status": "existing stock; thickness 2.0 mm measured",
            "unitPriceJpy": None, "lineTotalJpy": None, "incrementalCashJpy": 0,
            "productCostJpy": None, "costTreatment": "existing stock; no incremental cash; product cost unknown",
            "notes": "2.2 mm is a separate CAD allowance, not the measured thickness.",
        },
        {
            "id": "m5-case-mount-bolt", "section": "hardware", "name": "M5 本体固定ねじ",
            "quantity": quantities["7U40-R9-HW-CASE-MOUNT-BOLT"], "unit": "piece", "dimensionsMm": None,
            "material": "Unselected; provisional fastener envelope",
            "status": "provisional; length and head diameter unconfirmed; 1.4 mm head height confirmed",
            "unitPriceJpy": None, "lineTotalJpy": None, "costTreatment": "unquoted",
            "notes": "M5 flat-head height 1.4 mm is user-confirmed; seated below the padder.",
        },
        {
            "id": "m5-panel-joint-bolt", "section": "hardware", "name": "M5 パネル接合ねじ",
            "quantity": quantities["7U40-R9-HW-PANEL-JOINT-BOLT"], "unit": "piece", "dimensionsMm": None,
            "material": "Unselected; provisional fastener envelope",
            "status": "provisional; exact head diameter and length unconfirmed",
            "unitPriceJpy": None, "lineTotalJpy": None, "costTreatment": "unquoted",
            "notes": "Head height 1.4 mm is user-confirmed; seated below the padder.",
        },
        {
            "id": "m5-rail-end-bolt", "section": "hardware", "name": "M5 レール端ねじ",
            "quantity": quantities["7U40-R9-HW-RAIL-END-BOLT"], "unit": "piece", "dimensionsMm": None,
            "material": "Unselected; provisional fastener envelope",
            "status": "provisional; length unconfirmed",
            "unitPriceJpy": None, "lineTotalJpy": None, "costTreatment": "unquoted",
            "notes": "M5 flat-head height 1.4 mm is user-confirmed, seated below the padder; exact shank length remains provisional. Rail unit manufacturing cost is excluded by request.",
        },
        {
            "id": "m5-washer-1mm", "section": "hardware", "name": "M5 ワッシャー",
            "quantity": quantities["7U40-R9-HW-WASHER-1MM"], "unit": "piece", "dimensionsMm": None,
            "thicknessMm": params["outer_washer"]["value"],
            "material": "Unselected; OD/ID provisional",
            "status": "provisional; 1.0 mm thickness user-confirmed",
            "unitPriceJpy": None, "lineTotalJpy": None, "costTreatment": "unquoted",
            "notes": "Combined count: 10 outer washers and 36 panel-joint washers. Slot bearing coverage is not resolved.",
        },
        {
            "id": "m5-nut", "section": "hardware", "name": "M5 ナット",
            "quantity": quantities["7U40-R9-HW-M5-NUT"], "unit": "piece", "dimensionsMm": None,
            "material": "Unselected; display-envelope dimensions provisional",
            "status": "provisional; nut type and dimensions unconfirmed",
            "unitPriceJpy": None, "lineTotalJpy": None, "costTreatment": "unquoted",
            "notes": "Envelope count comprises 10 case-mount and 36 panel-joint nuts.",
        },
        {
            "id": "inner-spacer-8mm", "section": "hardware", "name": "内側スペーサー",
            "quantity": quantities["7U40-R9-HW-INNER-SPACER"], "unit": "piece", "dimensionsMm": None,
            "thicknessMm": params["inner_spacer"]["value"],
            "material": "Unselected; OD/ID provisional",
            "status": "provisional; 8 mm thickness user-confirmed",
            "unitPriceJpy": None, "lineTotalJpy": None, "costTreatment": "unquoted",
            "notes": "Product dimensions and material are not selected.",
        },
        {
            "id": "m3-lid-frame-screw", "section": "hardware", "name": "M3 蓋板・フレーム組立ねじ",
            "quantity": 8, "unit": "piece", "dimensionsMm": None,
            "material": "Unselected; provisional hardware",
            "status": "provisional; length, head, and tool access unconfirmed",
            "unitPriceJpy": None, "lineTotalJpy": None, "costTreatment": "unquoted",
            "notes": "Eight plate-to-frame bores; these are lid-assembly screws, not lid-to-body locks.",
        },
        {
            "id": "m3-lid-frame-nut", "section": "hardware", "name": "M3 蓋板・フレーム組立ナット",
            "quantity": 8, "unit": "piece", "dimensionsMm": None,
            "material": "Unselected; provisional hardware",
            "status": "provisional; exact nut type and tool access unconfirmed",
            "unitPriceJpy": None, "lineTotalJpy": None, "costTreatment": "unquoted",
            "notes": "Eight plate-to-frame bores; these are not lid-to-body locks.",
        },
        {
            "id": "rubber-foot", "section": "hardware", "name": "ゴム足",
            "quantity": quantities["7U40-R9-HW-FOOT"], "unit": "piece", "dimensionsMm": None,
            "material": "Black rubber candidate; product unselected",
            "status": "provisional; dimensions and attachment method unconfirmed",
            "unitPriceJpy": None, "lineTotalJpy": None, "costTreatment": "unquoted",
            "notes": "Display envelope only.",
        },
        {
            "id": "external-transport-strap", "section": "hardware", "name": "着脱式外周バンド",
            "quantity": 2, "unit": "piece", "dimensionsMm": None,
            "widthMm": body_spec["lid_preview"]["strapWidthMm"],
            "modeledThicknessMm": body_spec["lid_preview"]["strapThicknessMm"],
            "estimatedLoopLengthMm": body_spec["lid_preview"]["strapLoopGeometricEstimateMm"],
            "material": "Generic external strap; material and product unselected",
            "status": "schematic estimate; not load-tested",
            "unitPriceJpy": None, "lineTotalJpy": None, "costTreatment": "unquoted",
            "notes": "Geometric loop estimate excludes buckle, overlap, protrusions, and actual tightening.",
        },
    ]

    excluded = []
    for part_id, name, note in (
        ("7U40-R9-HW-RAIL-UNIT-ENVELOPE", "40HP rail unit", "Existing rail source; rail manufacturing cost is excluded by request."),
        ("7U40-R9-PCB-FIXER", "Fixer PCB", "Existing source PCB; purchase/manufacturing cost excluded by request."),
    ):
        component = body_component[part_id]
        row = {
            "id": part_id, "section": "excluded_from_cost", "name": name,
            "quantity": component["quantity"], "unit": "piece",
            "costTreatment": "excluded from cost by request",
            "unitPriceJpy": None, "lineTotalJpy": None, "productCostJpy": None,
            "notes": note,
        }
        if part_id.startswith("7U40-R9-PCB-"):
            row["thicknessMm"] = 1.6
            row["status"] = "user-confirmed existing source PCB"
            row["notes"] += " PCB thickness 1.6 mm is user-confirmed."
        else:
            row["status"] = "existing source rail; cost excluded by request"
        excluded.append(row)
    for part_id, name in (("7U40-R9-PCB-PADDER-3U", "3U padder PCB"),
                          ("7U40-R9-PCB-PADDER-1U", "1U padder PCB")):
        component = body_component[part_id]
        excluded.append({
            "id": part_id, "section": "excluded_from_cost", "name": name,
            "quantity": component["quantity"], "unit": "piece",
            "thicknessMm": 1.6,
            "status": "user-confirmed existing source PCB",
            "costTreatment": "excluded from cost by request",
            "unitPriceJpy": None, "lineTotalJpy": None, "productCostJpy": None,
            "notes": "Existing source PCB; purchase/manufacturing cost excluded by request. PCB thickness 1.6 mm is user-confirmed.",
        })

    bom = {
        "schema": "zudo-case-r9-bom-v1",
        "revision": "R9-PROTOTYPE-01",
        "model": "7u40",
        "units": "mm",
        "currency": "JPY",
        "status": "unapproved_prototype",
        "productionApproved": False,
        "priceStatus": "No current supplier quotation is recorded; all unquoted prices and totals are null.",
        "items": items + hardware,
        "coupons": coupons,
        "excludedFromCost": excluded,
        "costSummary": {
            "quotedSubtotalJpy": None,
            "quotedTotalJpy": None,
            "note": "Do not use the old R3 t1.2 guard screenshot value of JPY 2,264 as a current R9 quote; tax and shipping were not shown.",
        },
        "sources": [
            "engineering/r9-prototype-01/out/build-log.json",
            "engineering/r9-prototype-01/out/hardware-envelopes/body-manifest.json",
            "engineering/r9-prototype-01/out/pa12/guards/t1p2/manifest.json",
            "engineering/r9-prototype-01/out/pa12/guards/t1p0/manifest.json",
            "engineering/r9-prototype-01/out/pa12/lid/manifest.json",
            "engineering/r9-prototype-01/out/coupons/coupon-manifest.json",
            "project/current-spec.json",
            "project/source-notes/user-decisions.md",
        ],
        "notes": [
            "Body has five independent aluminum plates; 7U40 means 3U + 3U + 1U in one plane.",
            "The lid plate is an aluminum sheet with a separate PA12 locating frame; no lid/body lock is included.",
            "The 1.0 mm PA12 guard set is a comparison and remains separate from the 1.2 mm main candidate.",
            "User-confirmed: fixer/padder PCBs are 1.6 mm, M5 flat-head height is 1.4 mm and sits below the padder, the inner spacer is 8 mm, outer washer is 1 mm, and bracket thickness is 2 mm measured.",
            "Fastener lengths/types, nut sizes, washer OD/ID, foot product, and strap product remain provisional or unselected.",
            "Rail, fixer, and padder costs are excluded; all current prices are unquoted.",
        ],
    }
    return bom, coupons


CSV_FIELDS = (
    "section", "id", "name", "quantity", "unit", "quantityMeaning", "dimensionsMm",
    "thicknessMm", "measuredThicknessMm", "coverMm", "widthMm", "modeledThicknessMm",
    "estimatedLoopLengthMm",
    "material", "status", "unitPriceJpy", "lineTotalJpy", "incrementalCashJpy",
    "productCostJpy", "costTreatment", "fileCount", "notes",
)


def _bom_csv(bom: dict) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    rows = [*bom["items"], *bom["coupons"], *bom["excludedFromCost"]]
    for row in rows:
        values = dict(row)
        if "dimensionsMm" in values and values["dimensionsMm"] is not None:
            values["dimensionsMm"] = json.dumps(values["dimensionsMm"], separators=(",", ":"))
        if "files" in values:
            values["notes"] = str(values.get("notes", "")) + " Files: " + ", ".join(values["files"])
        writer.writerow(values)
    return buffer.getvalue().encode("utf-8")


def _diff_document() -> bytes:
    return """# R9-PROTOTYPE-01 / 7U40 — R6・R8との差分と梱包内容

**状態:** 製作候補・未承認。R6は本体形状の起点、R8は載せ蓋の表示用コンセプトです。ここに記すR9データも製作承認ではありません。

## R6本体からの変更

- R6由来の本体寸法をもとに、独立したアルミ板５枚を維持しています。板厚1.5 mm、A5052、黒アルマイトは候補です。
- ブラケット位置36か所を5.5 × 7.5 mm、±1.0 mm移動の長穴候補として出力しました。位置誤差を調整し、仮締め後に外形・直角を整えて本締めする狙いです。候補の長軸は折曲げ線に直交しますが、方向と移動量は製造確認が残ります。レール固定穴10か所はφ5.5 mmの丸穴を維持します。
- t1.2 mm・被覆5 mmのPA12-HPガードを主候補、t1.0 mmを比較候補として分離しました。ガードは保護用カバーで、構造接合には使いません。接着・保持・現物嵌合は未確認です。
- R6本体の穴位置は名目形状を引き継いでいます。ブラケット実物への照合、公差、ワッシャー、ねじと工具のアクセスは完了していません。

## R8蓋コンセプトからの変更

- 採用したロックなしの構成を具体化するため、直線的に載せて持ち上げる蓋と、アルミ蓋板＋４分割PA12位置決め枠を7U40候補形状として書き出しました。運搬時の保持は別体の外周バンドを想定します。
- R7のM3蓋・本体ロック、フック、回転、スライド、磁石は採用していません。蓋板とPA12枠の組立ねじは別部品ですが、仕様は暫定です。
- R8の表示用形状を製作用ファイルとして再利用したものではありません。R9ジェネレーターで出したSTEP/STL/DXFは候補データで、蓋とガードの実嵌合やノブ・ケーブル空間を検証していません。
- 蓋上がり30 mm、モジュール板2 mm＋ノブ25 mm、ケーブルを外す前提は表示上の仮定です。全モジュールのノブ高さ・配線条件を検証した値ではありません。

## 重要な未確認事項

- 長穴は36か所候補です。現在の10 mm外径ワッシャー案は壁側の複数位置で受け代が不足します。必要外径11.5 mm以上は試す候補で、選定済みではありません。
- ガード保持・接着、公差、黒染色条件、蓋枠の座面、工具アクセス、実ノブ高さ、バンド長・張力・蓋たわみが未確認です。
- 保存済みR9検証は名目CAD/データ整合の確認です。FEA、強度、材料適合、物理嵌合、落下、疲労、運搬試験を示しません。
- G01–G11 は未完了です。サプライヤーへの送付、発注、製造承認を行う状態ではありません。

## ZIPの範囲

- アルミ: ６枚の板のSTEP/DXF、穴テーブル、長穴チェック。
- PA12: ガードt1.2主候補、t1.0比較候補、蓋枠４部品のSTEP/STLと数量表。
- クーポン: C1、C2、C3のファイルと、ZIP内相対パスを記録したcoupon-manifest.json。
- 各ZIPは25 MiB未満で、`READ-BEFORE-ORDER.txt`とSHA-256付きpackage-manifest.jsonを含みます。

## 見積とサイズ

現在の材料・加工・印刷見積はありません。価格欄はnullです。既存在庫ブラケット18個だけは追加現金支出0円として扱い、製品原価は不明のままです。レール、fixer、padderの費用は依頼により除外しました。異寸法の過去R3ガード価格は流用していません。

新たにコミットするファイル別サイズと合計は `SIZE-INVENTORY.json` に記録します。`engineering/r9-prototype-01/.gitignore` が `out/` 全体を除外するため、CADの重複中間STL、hardware-envelope、アセンブリ検査物、プレビューmesh/断面画像はコミットせず、必要な6枚等を各候補ZIPにだけ収録します。
""".encode("utf-8")


def _source_inputs() -> tuple[list[dict], list[dict], list[dict]]:
    records: dict[str, dict] = {}

    def add_file(path: Path, kind: str) -> None:
        rel = path.relative_to(REPO_ROOT).as_posix()
        raw = path.read_bytes()
        records[rel] = {"path": rel, "kind": kind, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

    generator_files = [R9_ROOT / "build.py", R9_ROOT / "pyproject.toml", R9_ROOT / "uv.lock"]
    generator_files.extend(sorted((R9_ROOT / "r9").glob("*.py")))
    generator_files.extend([
        R9_ROOT / "CONTRACTS.md",
        R9_ROOT / "VALIDATION.md",
        R9_ROOT / "preview" / "build.py",
        R9_ROOT / "preview" / "index.html",
        R9_ROOT / "preview" / "app.js",
        R9_ROOT / "preview" / "styles.css",
        R9_ROOT / "preview" / "three-bundle.js",
        R9_ROOT / "preview" / "THREE-LICENSE.txt",
    ])
    for path in sorted(set(generator_files)):
        add_file(path, "generator_source")

    for path in sorted((R9_ROOT / "params").glob("*.json")):
        add_file(path, "parameter")
    add_file(REPO_ROOT / "project" / "current-spec.json", "document_registry_reference")
    add_file(REPO_ROOT / "project" / "source-notes" / "user-decisions.md", "user_decisions_reference")
    add_file(REPO_ROOT / "project" / "open-issues.json", "open_issue_status_reference")

    body_manifest = _load_json(OUT / "hardware-envelopes" / "body-manifest.json")
    r6_files = []
    for source in body_manifest["sourceFiles"]:
        path = REPO_ROOT / source["path"]
        actual = {"path": source["path"], "kind": "r6_source_data", "bytes": path.stat().st_size,
                  "sha256": sha256_file(path), "purpose": source["purpose"]}
        if actual["sha256"] != source["sha256"]:
            raise ValueError(f"R6 source hash differs from R9 body manifest: {source['path']}")
        if not actual["bytes"]:
            raise ValueError(f"empty R6 source input: {source['path']}")
        records[source["path"]] = actual
        r6_files.append(actual)

    lid_manifest = _load_json(OUT / "pa12" / "lid" / "manifest.json")
    r7_path = REPO_ROOT / "public" / "downloads" / "archive" / "r7-m3-lid-source.zip"
    archive_record = {
        "path": r7_path.relative_to(REPO_ROOT).as_posix(),
        "kind": "r7_archive",
        "bytes": r7_path.stat().st_size,
        "sha256": sha256_file(r7_path),
    }
    records[archive_record["path"]] = archive_record
    members = []
    with zipfile.ZipFile(r7_path, "r") as archive:
        for info in sorted((item for item in archive.infolist() if not item.is_dir()), key=lambda item: item.filename):
            raw = archive.read(info.filename)
            members.append({
                "path": f"{archive_record['path']}::{info.filename}",
                "archive": archive_record["path"],
                "member": info.filename,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            })
    expected = lid_manifest["sourceMemberHashes"]
    for key, basename in (("r7_build_lids_sha256", "build_lids.py"),
                          ("r7_lid_parameters_sha256", "lid-parameters.json")):
        found = [member for member in members if Path(member["member"]).name == basename]
        if len(found) != 1 or found[0]["sha256"] != expected[key]:
            raise ValueError(f"R7 source member hash does not match lid manifest: {basename}")

    all_inputs = sorted(records.values(), key=lambda item: item["path"])
    r6_files.sort(key=lambda item: item["path"])
    members.sort(key=lambda item: item["path"])
    return all_inputs, r6_files, members


def _collect_outputs() -> list[dict]:
    files = []
    for path in OUT.rglob("*"):
        if not path.is_file() or path.resolve() == OUTPUT_MANIFEST.resolve():
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        files.append({"path": rel, "kind": "generated_out_file", "bytes": path.stat().st_size,
                      "sha256": sha256_file(path)})
    for name in PACKAGE_NAMES.values():
        path = CANDIDATE / name
        files.append({"path": path.relative_to(REPO_ROOT).as_posix(), "kind": "candidate_package_zip",
                      "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    preview = REPO_ROOT / "public" / "previews" / "r9-prototype-01.html"
    if not preview.is_file():
        raise FileNotFoundError("single-file R9 preview is missing")
    files.append({"path": preview.relative_to(REPO_ROOT).as_posix(), "kind": "single_file_preview_html",
                  "bytes": preview.stat().st_size, "sha256": sha256_file(preview)})
    files.sort(key=lambda item: item["path"])
    return files


def _browser_evidence() -> dict:
    check_path = OUT / "preview" / "browser-check.json"
    screenshots = []
    for path in sorted((R9_ROOT / "preview" / "shots").glob("r9-prototype-01-*.png")):
        screenshots.append({"path": path.relative_to(REPO_ROOT).as_posix(),
                            "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    if not check_path.is_file():
        return {
            "available": False,
            "scope": "offline interactive preview only; not CAD, fit, physical, or transport testing",
            "screenshots": screenshots,
        }
    check = _load_json(check_path)
    return {
        "available": True,
        "checkFile": check_path.relative_to(REPO_ROOT).as_posix(),
        "status": check.get("status"),
        "scope": "offline browser preview interactions and viewport only; not CAD validation, physical fit, strength, or transport testing",
        "screenshots": screenshots,
    }


def _output_manifest() -> bytes:
    inputs, r6_sources, r7_members = _source_inputs()
    build_log = _load_json(OUT / "build-log.json")
    return _json_bytes({
        "schema": "zudo-case-r9-output-manifest-v1",
        "revision": "R9-PROTOTYPE-01",
        "model": "7u40",
        "units": "mm",
        "status": "unapproved_prototype",
        "productionApproved": False,
        "generatedBy": "engineering/r9-prototype-01/r9/package.py",
        "buildModules": build_log.get("modules", []),
        "inputs": inputs,
        "r6SourceFiles": r6_sources,
        "r7ZipMembers": r7_members,
        "outputs": _collect_outputs(),
        "browserEvidence": _browser_evidence(),
        "manifestPolicy": {
            "selfHash": "outputs-manifest.json is deliberately excluded from outputs to avoid a self-reference.",
            "hashBasis": "SHA-256 and byte counts are calculated from delivered/current file bytes.",
            "browserEvidence": "Browser records cover the offline preview only and are not CAD or physical test results.",
        },
    })


def _write_size_inventory(manifest_size_guess: int) -> int:
    records = []
    own_name = SIZE_INVENTORY.relative_to(REPO_ROOT).as_posix()
    for name in NEW_COMMITTED_FILES:
        path = REPO_ROOT / name
        if name == OUTPUT_MANIFEST.relative_to(REPO_ROOT).as_posix():
            size = manifest_size_guess
        elif name == own_name:
            size = path.stat().st_size if path.is_file() else 0
        else:
            if not path.is_file():
                raise FileNotFoundError(f"new committed file missing for size inventory: {name}")
            size = path.stat().st_size
        records.append({"path": name, "bytes": size})

    own_record = next(row for row in records if row["path"] == own_name)
    # The inventory includes its own byte size. Length stabilizes once the
    # decimal digit count does; iterate to make that value exact.
    for _ in range(8):
        total = sum(row["bytes"] for row in records)
        document = {
            "schema": "zudo-case-r9-size-inventory-v1",
            "revision": "R9-PROTOTYPE-01",
            "scope": "new files committed for issue #92, including this inventory and outputs-manifest.json",
            "files": records,
            "totalBytes": total,
            "limitBytes": TOTAL_NEW_FILE_LIMIT_BYTES,
        }
        raw = _json_bytes(document)
        if own_record["bytes"] == len(raw):
            SIZE_INVENTORY.write_bytes(raw)
            if total >= TOTAL_NEW_FILE_LIMIT_BYTES:
                raise ValueError(f"new committed file set is >= 40 MiB: {total} bytes")
            return len(raw)
        own_record["bytes"] = len(raw)
    raise ValueError("size inventory self-size did not stabilize")


def _write_manifest_and_inventory() -> None:
    manifest_size = OUTPUT_MANIFEST.stat().st_size if OUTPUT_MANIFEST.exists() else 0
    for _ in range(10):
        _write_size_inventory(manifest_size)
        raw = _output_manifest()
        OUTPUT_MANIFEST.write_bytes(raw)
        actual = len(raw)
        if actual == manifest_size:
            # Ensure the inventory also records the exact final manifest size.
            _write_size_inventory(actual)
            final = _output_manifest()
            if final != OUTPUT_MANIFEST.read_bytes():
                OUTPUT_MANIFEST.write_bytes(final)
                manifest_size = len(final)
                continue
            return
        manifest_size = actual
    raise ValueError("outputs manifest/inventory sizes did not stabilize")


def build() -> dict:
    """Rebuild BOM, three candidate ZIPs, and byte-hash ledgers from `out/`."""
    _load_and_verify_build_log()
    OUT.mkdir(parents=True, exist_ok=True)
    CANDIDATE.mkdir(parents=True, exist_ok=True)

    aluminum_entries, plate_rows = _plate_entries()
    aluminum_entries["READ-BEFORE-ORDER.txt"] = _readme("aluminum")
    aluminum_entries["plates.json"] = _json_bytes({
        "schema": "zudo-case-r9-aluminum-plate-quantities-v1",
        "revision": "R9-PROTOTYPE-01", "model": "7u40", "units": "mm",
        "status": "unapproved_prototype", "plates": plate_rows,
    })
    aluminum_zip = _write_package("aluminum", aluminum_entries)

    pa12_entries, quantities = _guard_table()
    pa12_entries["READ-BEFORE-ORDER.txt"] = _readme("pa12")
    pa12_zip = _write_package("pa12", pa12_entries)

    coupon_files, _ = _coupon_entries()
    coupon_files["READ-BEFORE-ORDER.txt"] = _readme("coupons")
    coupon_zip = _write_package("coupons", coupon_files)

    bom, _coupons = _bom_rows()
    (OUT / "bom.json").write_bytes(_json_bytes(bom))
    (OUT / "bom.csv").write_bytes(_bom_csv(bom))
    (OUT / "DIFF-FROM-R6-R8.md").write_bytes(_diff_document())

    _write_manifest_and_inventory()
    return {
        "packages": [aluminum_zip, pa12_zip, coupon_zip],
        "bom": OUT / "bom.json",
        "manifest": OUTPUT_MANIFEST,
        "inventory": SIZE_INVENTORY,
        "packageBytes": {path.name: path.stat().st_size for path in (aluminum_zip, pa12_zip, coupon_zip)},
    }


if __name__ == "__main__":
    result = build()
    for key, value in result.items():
        print(f"{key}: {value}")
