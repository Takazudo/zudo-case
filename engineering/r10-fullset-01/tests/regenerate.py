"""Regenerate twice in independent temporary directories and compare every byte."""
import subprocess,sys,tempfile,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='r10-repeat-') as tmp:
    dirs=[Path(tmp)/'a',Path(tmp)/'b']
    for d in dirs:subprocess.run([sys.executable,str(ROOT/'build.py'),'--out',str(d)],check=True)
    def listing(d):return {p.relative_to(d).as_posix():p.read_bytes() for p in d.rglob('*') if p.is_file()}
    a,b=map(listing,dirs);assert a==b,'Independent regenerations differ'
    c=listing(ROOT/'out');assert a==c,'Committed outputs differ from regeneration'
    print('Two independent builds and committed outputs match:',len(a),'files')
