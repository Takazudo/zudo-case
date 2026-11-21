#!/usr/bin/env python3
"""Build the R11-BUILD-FEEDBACK-04 download packages from the imported, reviewed outputs.

Reads only ``source/out/`` (the byte-identical extraction of the received archive) and
writes ``packages/*.zip`` plus ``packages-manifest.json``. Python 3 standard library only.
Deterministic: sorted members, fixed timestamp 2026-11-22 00:00:00, fixed permissions,
ZIP_DEFLATED at level 9. No CAD is regenerated here.

Usage (from anywhere):
    python3 engineering/r11-build-feedback-04/package.py
"""
import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path

REVISION = 'R11-BUILD-FEEDBACK-04'
HERE = Path(__file__).resolve().parent
OUT = HERE / 'source' / 'out'
PACKAGES = HERE / 'packages'
MANIFEST = HERE / 'packages-manifest.json'
STAMP = (2026, 11, 22, 0, 0, 0)
MODE = 0o100644
PUBLIC_DIR = 'public/downloads/candidate'
URL_DIR = '/downloads/candidate'

# The received archive is published verbatim (not rebuilt). Its identity is the accepted input.
RECEIVED_ARCHIVE = {
    'filename': 'zudo-case-r11-04-design-files.zip',
    'sha256': '4c74dd94e84ecebee8ac8d714cb5ba60f0ff479667c8c7f4ed4c75790463fcad',
    'bytes': 16928225,
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def load_parts():
    manifest = json.loads((OUT / 'parts-manifest.json').read_text(encoding='utf-8'))
    if manifest['revision'] != REVISION or manifest['production_approved'] is not False:
        raise SystemExit('parts-manifest.json is not the accepted unapproved R11-04 manifest')
    parts = manifest['parts']
    for part in parts:
        for ref in part['files'].values():
            data = (OUT / ref['path']).read_bytes()
            if sha256(data) != ref['sha256'] or len(data) != ref['bytes']:
                raise SystemExit('out/ file differs from parts-manifest: ' + ref['path'])
    return parts


def pa12_text(parts):
    pa12 = [p for p in parts if p['category'] == 'pa12']
    body = [p for p in pa12 if p['id'].startswith('body-')]
    lid = [p for p in pa12 if p['id'].startswith('lid-')]
    longest = max(max(p['dimensions_mm']) for p in pa12)
    body_cm3 = sum(p['volume_mm3'] * p['quantity'] for p in body) / 1000
    lid_cm3 = sum(p['volume_mm3'] * p['quantity'] for p in lid) / 1000
    rows = '\n'.join(
        '| `pa12/{id}.step` / `.stl` | {name} | {q} | {d} | {v:.4f} |'.format(
            id=p['id'], name=p['name'], q=p['quantity'],
            d=' × '.join('{:.2f}'.format(x) for x in p['dimensions_mm']), v=p['volume_mm3'] / 1000)
        for p in pa12)
    return f"""# {REVISION} — PA12 プリント部品（20個）

7U40 金属ケースの CAD レビュー候補です。**製造承認ではありません**（`production_approved=false`）。現物の嵌合・強度・耐久・輸送保持は未確認です。

- 合計 **{len(pa12)}個 = 本体 {len(body)}個 + 蓋 {len(lid)}個**。各ファイルは **数量1個** の単体モデルです。STEP と STL は同じ部品の別形式で、二重に数えません。
- 材料候補: MJF **PA12-HP、黒染め**（候補であり確定仕様ではありません）。
- 各部品は **組立姿勢のまま** 最小XYZを0へ平行移動して書き出しています。これは書き出し基準で、**検証済みの造形姿勢ではありません**。
- 最長寸法は **{longest:g} mm**。公表されている 250 mm の大型部品判定には掛かりませんが、それは価格帯の確定ではありません。
- CAD 体積: 本体 {body_cm3:.4f} cm³、蓋 {lid_cm3:.4f} cm³、合計 {body_cm3 + lid_cm3:.4f} cm³（見積額ではありません）。
- 価格はすべて **null（未見積）** です。このパッケージは業者へ送信・発注されていません。発注・アップロードには別途の明示的な許可が必要です。
- `pa12-size-audit.csv` は各部品の計測寸法・体積・価格状態（unquoted）の一覧です。

| ファイル | 部品 | 数量 | 寸法 mm | 体積 cm³ |
|---|---|---:|---|---:|
{rows}

R11-03 から変わったのは蓋の4隅と左右中間の6個です。前後中間の蓋2個と本体12個は R11-03 と同一形状です。
"""


def aluminum_text(parts):
    sheets = [p for p in parts if p['category'] == 'aluminum']
    holes = list(csv.DictReader((OUT / 'panel-hole-map.csv').open(encoding='utf-8')))
    slots = [h for h in holes if h['shape'] == 'slot']
    rounds = [h for h in holes if h['shape'] == 'round']
    lid_round = [h for h in rounds if h['panel_id'] == 'lid-plate']
    rail_round = [h for h in rounds if h['panel_id'] != 'lid-plate']
    slot_dims = sorted({(float(h['total_length_mm']), float(h['width_or_diameter_mm'])) for h in slots})
    if len(slot_dims) != 1:
        raise SystemExit('unexpected slot sizes')
    slot_len, slot_w = slot_dims[0]
    rows = []
    for p in sheets:
        mine = [h for h in holes if h['panel_id'] == p['id']]
        rows.append('| `aluminum/{id}.step` / `.stl` / `.dxf` | {name} | {q} | {d} | {s} | {r} |'.format(
            id=p['id'], name=p['name'], q=p['quantity'],
            d=' × '.join('{:g}'.format(x) for x in p['dimensions_mm']),
            s=sum(h['shape'] == 'slot' for h in mine), r=sum(h['shape'] == 'round' for h in mine)))
    rows = '\n'.join(rows)
    return f"""# {REVISION} — アルミ板（6枚）

7U40 金属ケースの CAD レビュー候補です。**製造承認ではありません**（`production_approved=false`）。

- 板 **{len(sheets)}枚**、各1枚。材料候補: **A5052 t1.5、加工後黒アルマイト**（候補であり確定仕様ではありません）。
- STEP / STL / DXF は同じ板の別形式で、数量を重複させません。
- 機能穴は合計 **{len(holes)}個 = 本体長穴 {len(slots)}個（{slot_len:g} × {slot_w:g} mm）+ レール用丸穴 {len(rail_round)}個 + 蓋丸穴 {len(lid_round)}個**。位置は `panel-hole-map.csv` を参照してください。
- **専用の吊り穴はありません**。底・前・後の板は接合用長穴だけで、アルマイト処理時の吊り方は業者に**未確認**です。
- 価格は未見積で、このパッケージは業者へ送信・発注されていません。

| ファイル | 板 | 数量 | 外形 mm | 長穴 | 丸穴 |
|---|---|---:|---|---:|---:|
{rows}
"""


def washer_text(parts):
    washer = [p for p in parts if p['category'] == 'home-print']
    if len(washer) != 1:
        raise SystemExit('expected one washer model')
    w = washer[0]
    return f"""# {REVISION} — 家庭印刷の丸ワッシャー

- 再利用する **1種類のモデル**（OD15 / ID5 / t1 mm）: `home-print/round-washer.step` / `.stl`。
- 使用数は **{w['quantity']}個 = 本体外側 40個 + 本体上部内側 8個 + 蓋壁 16個**。
- 家庭での **黒ASA** 印刷部品です。PA12 の業者発注品ではなく、PA12 パッケージに混ぜません。
- これらの書き出しには **プリンター設定は含まれていません**。スライサー設定・造形姿勢は利用者が決めます。
- CAD レビュー候補であり、製造承認ではありません（`production_approved=false`）。現物の締結・耐久は未確認です。
"""


def package_specs(parts):
    by_cat = lambda c: [p for p in parts if p['category'] == c]
    pa12_files = [(f"pa12/{Path(r['path']).name}", r['path']) for p in by_cat('pa12') for r in p['files'].values()]
    alu_files = [(f"aluminum/{Path(r['path']).name}", r['path']) for p in by_cat('aluminum') for r in p['files'].values()]
    home_files = [(f"home-print/{Path(r['path']).name}", r['path']) for p in by_cat('home-print') for r in p['files'].values()]
    return [
        ('pa12', pa12_files + [('pa12-size-audit.csv', 'pa12-size-audit.csv')], pa12_text(parts)),
        ('aluminum', alu_files + [('panel-hole-map.csv', 'panel-hole-map.csv')], aluminum_text(parts)),
        ('home-print', home_files, washer_text(parts)),
    ]


def build_zip(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for name, data in sorted(entries, key=lambda e: e[0]):
            info = zipfile.ZipInfo(name, date_time=STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = MODE << 16
            zf.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return buf.getvalue()


def main():
    parts = load_parts()
    PACKAGES.mkdir(exist_ok=True)
    rel = lambda p: p.relative_to(HERE).as_posix()
    records = []
    for role, files, start_here in package_specs(parts):
        entries, members = [], []
        start = start_here.encode('utf-8')
        entries.append(('START-HERE.md', start))
        members.append({'name': 'START-HERE.md', 'source': 'package.py (generated text)', 'sha256': sha256(start)})
        for name, src in files:
            data = (OUT / src).read_bytes()
            entries.append((name, data))
            members.append({'name': name, 'source': rel(OUT / src), 'sha256': sha256(data)})
        members.sort(key=lambda m: m['name'])
        blob = build_zip(entries)
        filename = f'{REVISION}-{role}.zip'
        (PACKAGES / filename).write_bytes(blob)
        records.append({
            'role': role,
            'path': f'packages/{filename}',
            'public_path': f'{PUBLIC_DIR}/{filename}',
            'url': f'{URL_DIR}/{filename}',
            'bytes': len(blob),
            'sha256': sha256(blob),
            'members': members,
        })
    source_name = f'{REVISION}-source.zip'
    records.insert(0, {
        'role': 'source',
        'path': None,
        'public_path': f'{PUBLIC_DIR}/{source_name}',
        'url': f'{URL_DIR}/{source_name}',
        'bytes': RECEIVED_ARCHIVE['bytes'],
        'sha256': RECEIVED_ARCHIVE['sha256'],
        'verbatim_received_archive': True,
        'received_filename': RECEIVED_ARCHIVE['filename'],
        'members_record': 'SOURCE-RECEIPT.json',
    })
    manifest = {
        'revision': REVISION,
        'model': '7u40',
        'production_approved': False,
        'generator': {'path': 'package.py', 'sha256': sha256(Path(__file__).read_bytes())},
        'input_root': 'source/out/',
        'deterministic': {'timestamp': '2026-11-22T00:00:00', 'mode': '0644', 'compression': 'ZIP_DEFLATED level 9',
                          'member_order': 'sorted by name'},
        'paths_relative_to': 'engineering/r11-build-feedback-04/',
        'packages': records,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    for r in records:
        print(f"{r['role']}: {r['bytes']} bytes {r['sha256']}")


if __name__ == '__main__':
    main()
