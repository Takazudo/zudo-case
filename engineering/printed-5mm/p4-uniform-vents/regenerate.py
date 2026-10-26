"""Two clean builds, the second from the extracted source ZIP; compare all payloads."""
from pathlib import Path
import tempfile,subprocess,sys,zipfile,json,hashlib,argparse
root=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--published-root',type=Path);a=p.parse_args()
with tempfile.TemporaryDirectory() as tmp:
    tmp=Path(tmp);first=tmp/'first';second=tmp/'second';source=tmp/'extracted'
    subprocess.run([sys.executable,str(root/'build.py'),'--out',str(first)],check=True)
    with zipfile.ZipFile(first/'printed-5mm-p4-uniform-vents-source.zip') as z:z.extractall(source)
    subprocess.run([sys.executable,str(source/'build.py'),'--out',str(second)],check=True)
    m=json.loads((first/'outputs-manifest.json').read_text())
    for f in m['files']:
        assert (first/f['path']).read_bytes()==(second/f['path']).read_bytes(),f['path']
    args=['--published-root',str(a.published_root)] if a.published_root else []
    subprocess.run([sys.executable,str(root/'verify.py'),'--out',str(second),*args],check=True)
    print('Two clean builds, including source ZIP rebuild:',len(m['files']),'identical payloads')
