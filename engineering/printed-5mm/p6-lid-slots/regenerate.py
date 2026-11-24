"""Regenerate the seven P6 outputs separately and compare exact bytes."""
from pathlib import Path
import hashlib
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
expected = sorted(p.relative_to(ROOT/'out') for p in (ROOT/'out').rglob('*') if p.is_file())
assert len(expected) == 7, expected
with tempfile.TemporaryDirectory(prefix='zudo-case-p6-') as temp:
    out = Path(temp)/'out'
    run = subprocess.run([sys.executable,str(ROOT/'build.py'),'--out',str(out)],capture_output=True,text=True)
    if run.returncode:
        print(run.stdout)
        print(run.stderr,file=sys.stderr)
        raise SystemExit(run.returncode)
    actual = sorted(p.relative_to(out) for p in out.rglob('*') if p.is_file())
    assert actual == expected, (actual,expected)
    for rel in expected:
        assert (ROOT/'out'/rel).read_bytes() == (out/rel).read_bytes(), str(rel)
        print('PASS',rel,hashlib.sha256((out/rel).read_bytes()).hexdigest())
print('P6 source regeneration: all 7 outputs byte-identical')
