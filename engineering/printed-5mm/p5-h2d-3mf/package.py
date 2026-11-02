"""Package the verified projects and their maintained sources deterministically."""
from pathlib import Path
import argparse,zipfile
root=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);a=p.parse_args()
if root==a.out.resolve() or root in a.out.resolve().parents:
    raise SystemExit('Place the ZIP outside its source tree')
with zipfile.ZipFile(a.out,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
    for source in sorted(root.rglob('*')):
        if not source.is_file() or any(x in source.parts for x in ('__pycache__','.venv','.cache')):continue
        info=zipfile.ZipInfo(source.relative_to(root).as_posix(),(1980,1,1,0,0,0))
        info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
        archive.writestr(info,source.read_bytes())
print(a.out)
