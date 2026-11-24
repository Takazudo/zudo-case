"""Package current P6 by replacing only two P5 roofs; preserve every P5 payload."""
from pathlib import Path
import argparse
import hashlib
import io
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REVISION = "P6-PRINTED-5MM-LID-SLOTS"
P5 = "P5-PRINTED-5MM-TAB-JOINTS-J3"
SOURCE = ROOT / "engineering/printed-5mm/p6-lid-slots"
DEST = ROOT / "public/downloads/candidate"
REGISTRY = ROOT / "project/printed-5mm/p6-lid-slots/files.json"
REPLACED = ["lid-top-1", "lid-top-2"]
OPTIONAL = {"pad-horizontal": 48, "pad-vertical": 48, "washer-round": 28}
IDS = sorted(["floor-1", "floor-2", "wall-front", "wall-back", "wall-left", "wall-right",
              "lid-edge-front", "lid-edge-back", "lid-edge-left", "lid-edge-right", *REPLACED, *OPTIONAL])


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(data):
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()


def zip_bytes(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            item = zipfile.ZipInfo(name, (2026, 11, 24, 0, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = 0o100644 << 16
            archive.writestr(item, data)
    return output.getvalue()


def build_packages():
    cad, projects, parts = {}, {}, []
    for part in IDS:
        changed = part in REPLACED
        cad_root = SOURCE / "out" if changed else ROOT / "engineering/printed-5mm/p5-tab-joints/out"
        project_root = SOURCE / "out/projects" if changed else ROOT / "engineering/printed-5mm/p5-h2d-3mf/out/projects"
        matching = list(project_root.glob(f"{'p6' if changed else 'p5'}-{part}-h2d-*.3mf"))
        assert len(matching) == 1, (part, matching)
        row = {"id": part, "quantity": OPTIONAL.get(part, 1), "optional": part in OPTIONAL,
               "source_revision": REVISION if changed else P5, "unchanged_from_p5": not changed, "files": []}
        for extension in ("stl", "step", "3mf"):
            source = matching[0] if extension == "3mf" else cad_root / extension / f"{part}.{extension}"
            member = "projects/" + source.name if extension == "3mf" else f"{extension}/{part}.{extension}"
            data = source.read_bytes()
            (projects if extension == "3mf" else cad)[member] = data
            row["files"].append({"format": extension, "path": str(source.relative_to(ROOT)),
                                 "member": member, "bytes": len(data), "sha256": sha(data)})
        parts.append(row)
    manifest = {"revision": REVISION, "units": "mm", "production_approved": False,
                "unsliced": True, "print_parts": {"structural": 12, "optional_types": 3},
                "optional_quantities": OPTIONAL, "replaced_parts": REPLACED,
                "reused_parts": [p for p in IDS if p not in REPLACED], "parts": parts}
    guide = """# P6 / 7U40・5mm家庭印刷

P6-PRINTED-5MM-LID-SLOTS。一式は15型です。構造12型は各1個、任意の横パッド48個・縦パッド48個・丸座金28個。
P6天板 lid-top-1 と lid-top-2 は各1枚。各4か所の10.5 × 5.5 mm長穴、内外方向の公称調整量±2.5 mmです。
他13型は保存済みP5出力と同じバイト列です。3MFの継承部品は由来を示すp5ファイル名のままです。
P5を印刷済みなら天板2枚だけを交換します。この全ケースパッケージに旧丸穴の天板は含みません。

STLはmmの印刷姿勢、STEPは組立座標。長側板は45度平置き済みなので追加回転は不要です。
H2D・PLA・0.6 mm、ブリム0 mm、未スライス。長側板はRightノズルです。各3MFは1部品・1プレート。
レール・PCB・金属L金具・ねじは印刷セットに含みません。設計材料のASA想定と3MFのPLA設定を区別します。
サポート・実スライス・現物嵌合・締結強度・反り・クリープ・運搬は未確認で、製造未承認です。

PRINT-MAPPING.json に数量、各ファイルの由来、元パス、SHA-256を記録します。
天板ソースは printed-5mm-p6-lid-slots-source.zip。他13型の保守ソースは保存済みP5を引き継ぎます。
""".encode()
    common = {"PRINT-START-HERE.md": guide, "PRINT-MAPPING.json": encoded(manifest),
              "P6-ROOF-VERIFICATION.json": (SOURCE / "out/verification.json").read_bytes()}
    return manifest, {
        DEST / "printed-5mm-p6-lid-slots-stl.zip": zip_bytes({**cad, **common}),
        DEST / "printed-5mm-p6-lid-slots-h2d-3mf.zip": zip_bytes({**projects, **common}),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    manifest, packages = build_packages()
    replacement = {str(p.relative_to(SOURCE / 'out')): p.read_bytes()
                   for p in (SOURCE / 'out').rglob('*') if p.is_file()}
    replacement.update({name: (SOURCE / name).read_bytes() for name in ('README.md', 'parameters.json')})
    packages[DEST / 'printed-5mm-p6-lid-slots.zip'] = zip_bytes(replacement)
    source_files = [p for p in SOURCE.rglob('*') if p.is_file()
                    and not any(part in ('.venv', '__pycache__', '.cache') for part in p.relative_to(SOURCE).parts)
                    and p.suffix != '.pyc']
    packages[DEST / 'printed-5mm-p6-lid-slots-source.zip'] = zip_bytes({str(p.relative_to(SOURCE)): p.read_bytes() for p in source_files})
    for path, data in packages.items():
        if args.check:
            assert path.read_bytes() == data, f"Stale P6 full package: {path.relative_to(ROOT)}"
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    paths = list(source_files)
    paths.extend(DEST / x for x in ("printed-5mm-p6-lid-slots.zip", "printed-5mm-p6-lid-slots-source.zip"))
    paths.extend(packages)
    paths.append(ROOT / "public/previews/printed-5mm-p6-lid-slots.html")
    registry = {**manifest, "source": "engineering/printed-5mm/p6-lid-slots/",
                "geometry_verification": "engineering/printed-5mm/p6-lid-slots/out/verification.json",
                "files": [{"path": str(p.relative_to(ROOT)), "sha256": sha(p.read_bytes()), "bytes": p.stat().st_size}
                          for p in sorted(set(paths))]}
    data = encoded(registry)
    if args.check:
        assert REGISTRY.read_bytes() == data, "Stale P6 registry; regenerate with scripts/sync-printed-p6.py"
    else:
        REGISTRY.parent.mkdir(parents=True, exist_ok=True)
        REGISTRY.write_bytes(data)
    print(f"P6: 15 STL + 15 STEP, 15 H2D projects; exactly 2 replaced and 13 inherited types; {len(registry['files'])} registered files")


if __name__ == "__main__":
    main()
