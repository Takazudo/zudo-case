#!/usr/bin/env python3
"""Build a quote-only sample packet from verified existing CAD. No orders or approvals."""
import argparse, hashlib, io, json, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'engineering/r9-fitfix-01'
OUT = BASE / 'out'
PREP = BASE / 'order-prep'
PUBLIC = ROOT / 'public/downloads/candidate/fit-test-order-pack-DRAFT.zip'

def digest(b):
    return hashlib.sha256(b).hexdigest()

def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()

def archive(entries):
    result = io.BytesIO()
    with zipfile.ZipFile(result, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, data)
    return result.getvalue()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    def put(path, data):
        if args.check:
            if not path.is_file() or path.read_bytes() != data:
                raise ValueError(f'Order packet drift: {path.relative_to(ROOT)}')
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    manifest = json.loads((OUT / 'outputs-manifest.json').read_text())
    if manifest['production_approved'] is not False:
        raise ValueError('Expected unapproved candidate')
    listed = {x['path']: x for x in manifest['files']}
    def verified(name):
        b = (OUT / name).read_bytes()
        if digest(b) != listed[name]['sha256'] or len(b) != listed[name]['bytes']:
            raise ValueError(f'CAD byte mismatch: {name}')
        return b

    bom = json.loads(verified('BOM.json'))
    rows = [r for r in bom if r['variant'] == 'coupon' and r['order_quantity'] > 0]
    pa12 = [r for r in rows if r['group'] == 'coupon']
    metal = [r for r in rows if r['group'] == 'coupon-metal']
    assert len(pa12) == 13 and sum(r['order_quantity'] for r in pa12) == 15
    assert len(metal) == 7 and sum(r['order_quantity'] for r in metal) == 7
    attachments = {}
    for name, group, formats in [
        ('fit-coupons-pa12-NOT-APPROVED.zip', pa12, ('stl',)),
        ('fit-coupons-metal-NOT-APPROVED.zip', metal, ('step', 'dxf')),
    ]:
        b = verified(name)
        with zipfile.ZipFile(io.BytesIO(b)) as z:
            expected = {r[k] for r in group for k in formats}
            actual = {n for n in z.namelist() if Path(n).suffix in ('.stl', '.step', '.dxf')}
            assert expected == actual, (name, expected ^ actual)
            for file in expected:
                assert z.read(file) == verified(file), file
        attachments[name] = b

    old = ROOT / 'engineering/r9-prototype-01'
    old_manifest = json.loads((old / 'out/coupons/coupon-manifest.json').read_text())
    c3 = [c for c in old_manifest['coupons'] if c['id'].startswith('C3-')]
    assert len(c3) == 3
    c3_files = {}
    for coupon in c3:
        for f in coupon['fileHashes']:
            b = (old / f['path']).read_bytes()
            assert len(b) == f['bytes'] and digest(b) == f['sha256'], f['path']
            c3_files[Path(f['path']).name] = b
    c3_files['SOURCE-MANIFEST.json'] = encode({
        'revision': old_manifest['revision'], 'status': 'optional-quote-only',
        'production_approved': False, 'physical_plate_count': 6,
        'quantity_rule': 'Each STEP/DXF pair is ONE plate; quantity 1 each. Three bottom/wall pairs.',
        'coupons': c3,
    })
    attachments['c3-hardware-coupons-R9-PROTOTYPE-01-DRAFT.zip'] = archive(c3_files)
    plan = {
        'revision': 'R9-FITFIX-01', 'status': 'quote-ready-draft-not-sent',
        'production_approved': False, 'purchase_authorized': False,
        'quote_total': None, 'currency': None, 'tax': None, 'shipping': None,
        'pa12': {'supplier_candidate': 'JLC3DP', 'process': 'MJF', 'material': 'PA12-HP',
                 'finish_requested': 'dyed black; supplier confirmation pending',
                 'unique_parts': 13, 'quantity': 15, 'parts': pa12},
        'aluminum_base': {'supplier_candidate': 'JLCCNC or purchaser-selected sheet-metal shop',
                         'material': 'A5052', 'thickness_mm': 1.5,
                         'finish_requested': 'black anodized after cutting, deburred',
                         'unique_parts': 7, 'quantity': 7, 'parts': metal},
        'aluminum_optional_C3': {'revision': old_manifest['revision'], 'quantity': 6,
                                'selection': 'quote separately; not included in base seven',
                                'coupon_ids': [c['id'] for c in c3]},
        'sources_checked_date': '2026-09-30',
        'sources': [
            {'url': 'https://jlc3dp.com/help/article/pa12-hp-nylon',
             'facts': 'MJF; listed wall 1 mm; tolerance ±0.3 mm within 100 mm. Not part-specific approval.'},
            {'url': 'https://jlccnc.com/sheet-metal-fabrication',
             'facts': '5052, 1.5 mm sheet and anodizing listed; small-part acceptance and finished tolerances require quote.'},
        ],
        'attachments': [{'file': name, 'bytes': len(b), 'sha256': digest(b)} for name, b in attachments.items()],
        'remaining_before_payment': [
            'Supplier DFM acceptance of exact files, material/finish and small-part handling',
            'Destination-specific quote with tax/shipping and lead time',
            'Choose whether to include optional C3 six plates',
            'Purchaser approval of the exact paid test order',
        ],
        'not_required_before_dry_fit_order': ['Final adhesive selection', 'Completed full-case physical tests'],
    }
    put(PREP / 'order-plan.json', encode(plan))
    attachments['order-plan.json'] = encode(plan)
    for name in ['README.md', 'PA12-RFQ.txt', 'ALUMINUM-RFQ.txt', 'TEST-PLAN.md']:
        attachments[name] = (PREP / name).read_bytes()
    attachments['FIT-RECORD.md'] = (BASE / 'handoff/FIT-RECORD.md').read_bytes()
    packet = archive(attachments)
    assert len(packet) < 25 * 1024 * 1024
    put(PUBLIC, packet)
    ledger_path = ROOT / 'project/artifact-manifest.json'
    ledger = json.loads(ledger_path.read_text())
    relative = PUBLIC.relative_to(ROOT).as_posix()
    record = {'path': relative, 'bytes': len(packet), 'sha256': digest(packet), 'status': 'quote-only-not-approved'}
    ledger['files'] = [r for r in ledger['files'] if r['path'] != relative] + [record]
    # Match the repository's existing JSON serialization (ASCII punctuation / Unicode retained).
    put(ledger_path, encode(ledger))
    print(f'Order packet {"verified" if args.check else "prepared"}: PA12 15 / aluminum 7 + optional C3 6; {len(packet)} bytes; SHA256 {digest(packet)}')

if __name__ == '__main__':
    main()
