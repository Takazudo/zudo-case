#!/usr/bin/env python3
"""Prepare the offline reference-frame data.

Rail JSONs are byte-identical Git blobs. PCB exterior vertices and padder
rectangles are transcribed from the pinned KiCad files. Rounded cutouts are
DISPLAY approximations to the source contour bounds, explicitly not drill CAD.
No source part is shortened or stretched. Requires Shapely 2.1 for triangulation.
"""
from pathlib import Path
import json, math, hashlib
import shapely
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
ROOT=Path(__file__).resolve().parents[1]
REF=ROOT/'reference/zudo-case'
COMMIT='6a13d80d816b0247ab9eee761c29c1fb786b76cc'
PREFIX='engineering/r6-body/source-data/'

def rect(x0,y0,x1,y1):return [[x0,y0],[x1,y0],[x1,y1],[x0,y1]]
def ellipse(x0,y0,x1,y1,n=32):
    cx=(x0+x1)/2; cy=(y0+y1)/2
    return [[cx+(x1-x0)/2*math.cos(i*2*math.pi/n),cy+(y1-y0)/2*math.sin(i*2*math.pi/n)] for i in range(n)]
def slot(x0,y0,x1,y1,n=12):
    """Capsule with the SOURCE bounds, not a modified mounting center."""
    if y1-y0 > x1-x0:
        return [[y,x] for x,y in slot(y0,x0,y1,x1,n)]
    r=(y1-y0)/2; cy=(y0+y1)/2
    return [[x1-r+r*math.cos(a),cy+r*math.sin(a)] for a in [(-math.pi/2+i*math.pi/n) for i in range(n+1)]] + [[x0+r+r*math.cos(a),cy+r*math.sin(a)] for a in [(math.pi/2+i*math.pi/n) for i in range(n+1)]]

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
                exteriorFidelity='source vertices',cutoutFidelity='bounds-based visual curve approximation' if curve_approx else 'source polygon vertices',
                manufacturingApproved=False)

panels={}
panels['fixer3u']=pcb('3U fixer',[[134.53186,14.995021],[134.53186,29.990042],[0,29.990042],[0,0],[12.560537,0],[134.53186,0]],
    [ellipse(3.210692,12.243012,8.785304,17.817623),ellipse(125.746536,12.243012,131.321136,17.817623),slot(14.112954,6.068562,120.454178,11.290379),slot(14.112957,18.699665,120.454178,23.921482)],
    'd09df0a92b4cf1a0d0d17d55f597961143e092b2','zb-side-frame-3u/zd-side-frame-3u.kicad_pcb',True)
# The 7U board uses raw X as depth and raw Y as row direction. Preserve ALL
# outside vertices, including the 0.035298 mm step; do not replace with a rectangle.
raw7=[[60.015381,30.060665],[60.015381,40.257282],[60.015381,42.6212],[60.015381,75.786667],[60.015381,117.067093],[60.015381,157.394867],[60.015381,197.722656],[60.015381,239.003082],[59.980083,239.073685],[59.980083,272.203888],[59.980083,274.567779],[59.980083,284.764404],[29.990042,314.754456],[0,314.754456],[0,308.721161],[0,269.063721],[0,180.222595],[0,134.53186],[0,45.690731],[0,6.033293],[0,0],[29.990042,0]]
round7=[(36.905434,42.480045),(48.901428,54.476040),(125.746536,131.321136),(137.742538,143.317169),(171.437256,177.011871),(183.433273,189.007904),(260.243103,265.817749),(272.274414,277.848999),(305.933868,311.508453)]
holes7=[ellipse(a,12.207715,b,17.782326) for a,b in round7]+[ellipse(3.245987,12.207717,8.820600,17.782328)]
for a,b in [(14.077661,31.613052),(59.768398,120.454178),(148.644775,166.109604),(194.264954,254.950729),(283.106049,300.641479)]:holes7.append(slot(a,6.068562,b,11.290379))
for a,b in [(14.077661,31.613052),(59.768398,120.454178),(148.644806,166.109634),(194.300262,254.986023),(283.106049,300.641479)]:holes7.append(slot(a,18.699665,b,23.921482))
for a,b,c,d in [(164.839417,36.058605,291.044647,41.280418),(23.674490,36.093899,149.879700,41.315712),(164.839401,48.689709,278.413544,53.911526),(36.305595,48.725029,149.879700,53.946842)]:holes7.append(slot(a,b,c,d))
panels['fixer7u']=pcb('7U fixer',[[y,x] for x,y in raw7],holes7,'b267d494d9ec8bb34248429d3064aa35c06f5b78','zb-side-frame-7u/zd-side-frame-7u.kicad_pcb',True)
panels['padder3u']=pcb('3U padder',rect(0,0,134.5,30),[rect(3.328213,12.374833,8.979433,17.973139),rect(125.820694,12.374833,131.471909,17.973139),rect(12.178968,4.137879,122.67054,26.213615)],'6140e916babd58829474dfe0c07db702c8702b2b','zb-side-frame-pad-3u/3u-padder.kicad_pcb')
panels['padder1u']=pcb('1U padder',rect(.024694,.025081,45.705303,30.024920),[rect(3.204659,12.196987,8.802291,17.798147),rect(36.882168,12.196987,42.479801,17.798147),rect(12.004972,3.999821,33.679489,25.995312)],'574d4711accfa4d0854c2c5ad125d842aa30bd0b','zb-side-frame-pad-1u/1u-padder.kicad_pcb')
rails={}
expected={'40':'178fd2e720d83b92f2430603e5592c5854ca2087','60':'0233c8735a777e0081f2a9e347ed887668588208'}
for hp in ('40','60'):
    p=REF/f'rail{hp}_mesh.json';raw=p.read_bytes()
    sha=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
    assert sha==expected[hp],(hp,sha)
    r=json.loads(raw);rails[hp]=dict(positions=r['positions'],indices=r['indices'],sourceBlobSHA=sha,sourcePath=PREFIX+f'rail{hp}/rail_mesh.json',sourceCommit=COMMIT,triangleCount=len(r['indices'])//3,exactSourceMesh=True)
# Original hole-center and padder-placement datums. Preserve slight asymmetry.
cx=14.930564880371094
units={
 '3u':dict(fixer='fixer3u',length=134.53186,top=-2+15.0303175-cx,
    rails=[[5.997998,15.0303175],[128.533836,15.0303175]],
    mounts=[[22.26593,21.3105735],[112.26593,21.3105735]],
    padders=[dict(kind='padder3u',u=0,v=0)],rowHeights=[128.5]),
 '7u':dict(fixer='fixer7u',length=314.754456,top=-2+14.9950205-cx,
    rails=[[6.0332935,14.9950225],[128.533836,14.9950205],[140.5298535,14.9950205],[263.030426,14.9950205],[275.0617065,14.9950205],[308.7211605,14.9950205]],
    mounts=[[u,21.3105735] for u in [22.8453565,90.111288,157.37722,224.6431425,291.873764]],
    padders=[dict(kind='padder3u',u=0,v=0),dict(kind='padder3u',u=134.531860,v=0),dict(kind='padder1u',u=269.039027,v=-.025081)],rowHeights=[128.5,128.5,39.65])
}
for k,u in units.items():
    u['rearReach']=max(max(v for _,v in panels[u['fixer']]['outer']),*(max(v for _,v in panels[p['kind']]['outer'])+p['v'] for p in u['padders']))-u['top']
    u['rowY']=[(u['rails'][i][0]+u['rails'][i+1][0])/2-u['length']/2 for i in range(0,len(u['rails']),2)]
D=dict(version='F5-reference-frame-1',repo='Takazudo/zudo-case',commit=COMMIT,railUpstreamCommit='0f7316ad9000b7906e5769aa89aff2dc18c661c8',pcbUpstreamCommit='b4db88ce5c93709f3f2f0a031f75190081f02443',
       railFidelity='all original positions and triangle indices; rigid transforms only',pcbFidelity='exact outside vertices, padder rectangles, original placement datums; rounded cutouts visual approximation',
       pcbThickness=1.6,sideSpacer=8,outerWasher=1,headHeight=1.4,units=units,rails=rails,panels=panels)
(REF/'frame-data.json').write_text(json.dumps(D,separators=(',',':'))+'\n')
(ROOT/'source/frame-data.js').write_text('/* Pinned source geometry, offline. See reference/PROVENANCE.md. */\n(function(r){r.ZudoFrameData='+json.dumps(D,separators=(',',':'))+';})(typeof window!=="undefined"?window:globalThis);\n')
manifest={k:{kk:vv for kk,vv in p.items() if kk not in ('positions','indices','edges','cutouts')} for k,p in panels.items()}
(REF/'pcb-geometry-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Prepared source frame data:',{k:dict(rearReach=u['rearReach'],rows=u['rowY']) for k,u in units.items()})
