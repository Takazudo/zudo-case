#!/usr/bin/env python3
"""Compare a disposable regeneration with the committed R9-LID-M5-01 outputs.

  python tools/compare_outputs.py --fresh /tmp/lidm5
Byte equality is expected in the locked Linux toolchain; any difference fails.
"""
import argparse, hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

ap = argparse.ArgumentParser(); ap.add_argument('--fresh', type=Path, required=True)
args = ap.parse_args()
committed = json.loads((ROOT / 'out/outputs-manifest.json').read_text())
fresh = json.loads((args.fresh / 'outputs-manifest.json').read_text())
a = {f['path']: f['sha256'] for f in committed['files']}
b = {f['path']: f['sha256'] for f in fresh['files']}
bad = sorted(set(a) ^ set(b)) + sorted(p for p in set(a) & set(b) if a[p] != b[p])
bad += [i['path'] for i, j in zip(committed['inputs'], fresh['inputs']) if i != j]
print(json.dumps(dict(compared=len(a), differences=bad), ensure_ascii=False, indent=1))
sys.exit(1 if bad else 0)
