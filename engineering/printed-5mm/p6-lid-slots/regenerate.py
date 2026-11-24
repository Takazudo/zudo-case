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
    import cadquery as cq
    first = cq.importers.importStep(str(out/'step/lid-top-1.step')).val()
    second = cq.importers.importStep(str(out/'step/lid-top-2.step')).val()
    rotated = first.rotate((0,0,0), (0,0,1), 180)
    differences = [rotated.cut(second).Volume(), second.cut(rotated).Volume()]
    assert all(abs(volume) < 1e-6 for volume in differences), ('The lid halves no longer share one printable shape', differences)
    print('PASS same STL x2: 180-degree assembly rotation; STEP difference volumes mm3', differences)
print('P6 source regeneration: all 7 outputs byte-identical')
