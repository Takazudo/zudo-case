"""Exercise rejection gates on disposable copies of one successful full build."""
from pathlib import Path
import argparse,errno,hashlib,json,os,shutil,subprocess,sys,tempfile
root=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);a=p.parse_args()
source=a.out.resolve()
def copy(src,dst):
    def link_or_copy(a,b):
        try: return os.link(a,b)
        except OSError as e:
            if e.errno != errno.EXDEV: raise
            return shutil.copy2(a,b)
    shutil.copytree(src,dst,copy_function=link_or_copy)
def rewrite(path,data):
    path.unlink();path.write_text(json.dumps(data,separators=(',',':')))
def refresh_model_manifest(dst):
    m=json.loads((dst/'outputs-manifest.json').read_text());data=(dst/'source/model.json').read_bytes()
    for f in m['files']:
        if f['path']=='source/model.json':f.update(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    rewrite(dst/'outputs-manifest.json',m)
def rejected(command,label):
    result=subprocess.run(command,capture_output=True,text=True)
    assert result.returncode!=0,(label,result.stdout,result.stderr)
    print('rejected',label)
with tempfile.TemporaryDirectory() as tmp:
    tmp=Path(tmp)
    d=tmp/'missing';copy(source,d);(d/'stl/floor-1.stl').unlink()
    rejected([sys.executable,str(root/'verify.py'),'--out',str(d)],'missing STL')
    d=tmp/'duplicate';copy(source,d);model=json.loads((d/'source/model.json').read_text());model['parts'][-1]['id']=model['parts'][0]['id'];rewrite(d/'source/model.json',model);refresh_model_manifest(d)
    rejected([sys.executable,str(root/'verify.py'),'--out',str(d)],'duplicate print part')
    d=tmp/'wrong';copy(source,d);model=json.loads((d/'source/model.json').read_text());model['revision']='R10-FULLSET-01';rewrite(d/'source/model.json',model);refresh_model_manifest(d)
    rejected([sys.executable,str(root/'verify.py'),'--out',str(d)],'wrong variant')
    d=tmp/'stale';copy(source,d);param=json.loads((d/'source/parameters.json').read_text());param['body']['inside_width']=227.4;rewrite(d/'source/parameters.json',param)
    rejected([sys.executable,str(d/'source/build_html.py')],'stale scene')
    # Invalid CAD parameters must fail before any output is generated.
    d=tmp/'invalid-input';d.mkdir();shutil.copytree(root/'source',d/'source',ignore=shutil.ignore_patterns('model.json','__pycache__'));shutil.copytree(root/'reference',d/'reference');shutil.copy2(root/'build.py',d/'build.py')
    param=json.loads((d/'source/parameters.json').read_text());param['body']['panel_thickness']=6;rewrite(d/'source/parameters.json',param)
    rejected([sys.executable,str(d/'build.py'),'--out',str(tmp/'invalid-output')],'unsupported panel thickness')
    param['body']['panel_thickness']=5;param['lid']['locator_clearance_per_side']=0.4;rewrite(d/'source/parameters.json',param)
    rejected([sys.executable,str(d/'build.py'),'--out',str(tmp/'unreviewed-output')],'unreviewed locator change')
