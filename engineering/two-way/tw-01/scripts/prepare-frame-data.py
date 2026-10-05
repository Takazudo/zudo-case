#!/usr/bin/env python3
"""Bake canonical saved contours. No contour fitting, repair or source mutation."""
from pathlib import Path
import json, math, hashlib, argparse
import shapely
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[2]
PREFIX='engineering/r6-body/source-data/'
REF=REPO/PREFIX
COMMIT='6a13d80d816b0247ab9eee761c29c1fb786b76cc'
def pcb(name,outer,holes,sha,path,curve_approx=False):
    poly=orient(Polygon(outer,holes),sign=1)
    assert poly.is_valid, (name,shapely.is_valid_reason(poly))
    # Store an indexed solid in normalized (thickness X, longitudinal U, depth V).
    rings=[list(poly.exterior.coords)[:-1]]+[list(r.coords)[:-1] for r in poly.interiors]
    pos=[]; ids={}; faces=[]; edges=[]
    def vertex(p):
        p=tuple(float(v) for v in p)
        if p not in ids:ids[p]=len(pos)//3;pos.extend(p)
        return ids[p]
    def tri(a,b,c):faces.extend([vertex(a),vertex(b),vertex(c)])
    ts=shapely.constrained_delaunay_triangles(poly)
    assert abs(sum(t.area for t in ts.geoms)-poly.area)<1e-6
    for t in ts.geoms:
        a,b,c=list(orient(t,sign=1).exterior.coords)[:3]
        tri([1.6,*a],[1.6,*b],[1.6,*c]);tri([0,*c],[0,*b],[0,*a])
    for ring in rings:
        for a,b in zip(ring,ring[1:]+ring[:1]):
            tri([0,*a],[0,*b],[1.6,*b]);tri([0,*a],[1.6,*b],[1.6,*a])
            edges.extend([0,*a,0,*b,1.6,*a,1.6,*b])
    return dict(name=name,sourceBlobSHA=sha,sourcePath=PREFIX+'panels/'+path,sourceCommit=COMMIT,
                outer=outer,cutouts=holes,thickness=1.6,positions=pos,indices=faces,edges=edges,
                cutoutCount=len(holes),surfaceAreaMm2=poly.area,
                exteriorFidelity='source vertices',cutoutFidelity='canonical saved source polygon vertices',
                manufacturingApproved=False)

def build():
    src=json.loads((REF/'panels/panel-geometry.json').read_text())
    placements=json.loads((REF/'panels/placements.json').read_text())['layouts']
    panels={}
    for name,p in src['panels'].items():
        uv=lambda c: [[y,x] for x,y in c['points']] if name=='fixer7u' else c['points']
        panels[name]=pcb(name,uv(p['outer']),[uv(c) for c in p['cutouts']],p['source']['git_blob_sha'],p['source']['path'].removeprefix('panels/'))
    rails={}
    for hp in ('40','60'):
        path=REF/f'rail{hp}/rail_mesh.json';raw=path.read_bytes();v=json.loads(raw)
        sha=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
        rails[hp]=dict(positions=v['positions'],indices=v['indices'],sourceBlobSHA=sha,sourcePath=PREFIX+f'rail{hp}/rail_mesh.json',sourceCommit=COMMIT,triangleCount=len(v['indices'])//3,exactSourceMesh=True)
    units={}
    for kind,key in [('3u','3u'),('7u','3u3u1u')]:
        p=placements[key];axes=[a['axisUV'] for a in p['selectedRailAxes']]
        pads=[dict(kind=a['panelKey'],u=a['translationUV'][0],v=a['translationUV'][1]) for a in p['padderPlacementsPerSide']]
        # Generic 3U placements omit case mounts. Explicit R6 configure rule takes precedence.
        mounts=[a['axisUV'] for a in p['selectedCaseMountAxesPerSide']]
        if not mounts:
            assert kind=='3u'
            mounts=[[p['coordinateSystem']['fixerCenterU']+u,21.3105735] for u in [-45,45]]
        top=-2+axes[1][1]-14.930564880371094
        length=p['fixerOuterBBoxUV']['dimensions'][0]
        u=dict(fixer=p['fixerPanelKey'],length=length,top=top,rails=axes,mounts=mounts,padders=pads,rowHeights=[128.5 if n==3 else 39.65 for n in p['layoutOrderAlongIncreasingU']],mountBasis='placements.json' if kind=='7u' else 'build_geometry.py configure(): BOARD_Y0 +/-45, V=21.3105735')
        u['rearReach']=max(max(v for _,v in panels[u['fixer']]['outer']),*(max(v for _,v in panels[a['kind']]['outer'])+a['v'] for a in pads))-top
        u['rowY']=[(axes[i][0]+axes[i+1][0])/2-length/2 for i in range(0,len(axes),2)]
        units[kind]=u
    paths=[REF/'panels/panel-geometry.json',REF/'panels/placements.json',REPO/'engineering/r6-body/build_geometry.py',*[REF/f'rail{hp}/rail_mesh.json' for hp in ('40','60')],*sorted((REF/'panels').rglob('*.kicad_pcb'))]
    hashes={str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    return dict(version='TW-01-canonical-frame-1',repo='Takazudo/zudo-case',commit=COMMIT,railUpstreamCommit='0f7316ad9000b7906e5769aa89aff2dc18c661c8',pcbUpstreamCommit=src['commitSha'],railFidelity='all original positions and indices; rigid transforms only; source topology unchanged',pcbFidelity='canonical saved outer and cutout polygon vertices; display triangulation, not manufacturing CAD',pcbThickness=1.6,sideSpacer=8,outerWasher=1,headHeight=1.4,units=units,rails=rails,panels=panels,inputHashes=hashes,tool=dict(shapely=shapely.__version__,geos=shapely.geos_version_string))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    d=build();payload=json.dumps(d,separators=(',',':'),ensure_ascii=False)+'\n'
    (a.out/'frame-data.json').write_text(payload)
    (a.out/'frame-data.js').write_text('/* Canonical saved source contours; generated display derivative. */\n(function(r){r.ZudoFrameData='+payload.strip()+';})(typeof window!=="undefined"?window:globalThis);\n')
    print(json.dumps({'inputHashes':d['inputHashes'],'outputSha256':hashlib.sha256(payload.encode()).hexdigest(),'tool':d['tool']},indent=2))
