"""Regenerate unsliced projects twice and compare every delivered byte."""
from pathlib import Path
import argparse,tempfile,subprocess,sys,zipfile
root=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--cad',required=True,type=Path);p.add_argument('--published-root',type=Path);a=p.parse_args()
with tempfile.TemporaryDirectory() as tmp:
    tmp=Path(tmp)
    for name in ('first','second'):
        subprocess.run([sys.executable,str(root/'build.py'),'--cad',str(a.cad),'--out',str(tmp/name)],check=True)
    for f in (tmp/'first').rglob('*'):
        if not f.is_file():continue
        rel=f.relative_to(tmp/'first')
        assert f.read_bytes()==(tmp/'second'/rel).read_bytes(),rel
        if a.published_root:
            assert f.read_bytes()==(a.published_root/'engineering/printed-5mm/p5-h2d-3mf/out'/rel).read_bytes(),rel
print('P5 3MF deterministic projects verified')

if a.published_root:
    package_root=a.published_root/'engineering/printed-5mm/p5-h2d-3mf'
    expected={f.relative_to(package_root).as_posix():f for f in package_root.rglob('*') if f.is_file() and not any(x in f.parts for x in ('__pycache__','.venv','.cache'))}
    with zipfile.ZipFile(a.published_root/'public/downloads/candidate/printed-5mm-p5-tab-joints-h2d-3mf.zip') as archive:
        assert archive.testzip() is None
        assert len(archive.namelist())==len(set(archive.namelist()))
        assert set(archive.namelist())==set(expected), '3MF download inventory differs'
        for name,source in expected.items():
            assert archive.read(name)==source.read_bytes(), 'Stale 3MF download member: '+name
    print('Published 3MF download matches all maintained sources and generated projects')
