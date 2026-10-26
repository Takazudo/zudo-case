"""Build the self-contained preview from build.py's meshes, without network access."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
d=json.loads((ROOT/'source/model.json').read_text())
current=json.loads((ROOT/'source/parameters.json').read_text())
if d['revision']!='P3-PRINTED-5MM-7U-RAILS' or d['parameters']!=current:
    raise SystemExit('Stale or wrong-variant scene; run the full P3 build')
for part in d['parts']:
    x,y=part['bed_footprint_mm'][:2];ox,oy=x/2+5,y/2+5;ix,iy=x/2,y/2
    pts=[];inds=[]
    for a,b,c,e in [((-ox,-oy),(ox,-oy),(ix,-iy),(-ix,-iy)),((ox,-oy),(ox,oy),(ix,iy),(ix,-iy)),((ox,oy),(-ox,oy),(-ix,iy),(ix,iy)),((-ox,oy),(-ox,-oy),(-ix,-iy),(-ix,iy))]:
        k=len(pts)//3
        for u,v in [a,b,c,e]:pts.extend([u,v,.08])
        inds.extend([k,k+1,k+2,k,k+2,k+3])
    key='brim-'+part['id'];d['meshes'][key]={'p':pts,'i':inds}
    d['scenes']['bed-'+part['id']].insert(1,{'id':key,'name':'5mm brim allowance','cat':'brim','mesh':key,'box':[-ox,-oy,.08,ox,oy,.08],'note':'Conservative rectangular footprint including brim. Not sliced toolpaths.','explode':[0,0,0],'group':'bed','material':'Layout diagnostic','volume':0,'solids':0})
s=(ROOT/'source/viewer-template.html').read_text()
assert s.count('__MODEL__')==1
s=s.replace('__MODEL__',json.dumps(d,separators=(',',':')))
(ROOT/'zudo-case-printed-5mm-p3.html').write_text(s)
print('Wrote standalone HTML:',len(s.encode()),'bytes')
