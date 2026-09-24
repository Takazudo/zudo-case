"""Build R8 display meshes, not manufacturing CAD. Units: mm.

Requires cadquery and numpy; the normal HTML build needs only Python stdlib.
Source: reference-models.json.gz contains the R7-derived lightweight study meshes.
R6 body/rail/PCB dimensions are preserved; all lid-to-case locks are removed.
"""
from pathlib import Path
import gzip, json, base64, copy, math
import cadquery as cq
import numpy as np
ROOT = Path(__file__).resolve().parent

def box(x0,x1,y0,y1,z0,z1):
    return cq.Solid.makeBox(x1-x0,y1-y0,z1-z0,cq.Vector(x0,y0,z0))

def fuse(shapes):
    s=shapes[0]
    for p in shapes[1:]: s=s.fuse(p)
    s=s.clean()
    assert s.isValid() and len(s.Solids())==1
    return s

def cylinder(axis,lo,hi,center,r):
    p=list(center);p[axis]=lo
    v=[0.,0.,0.];v[axis]=1.
    return cq.Solid.makeCylinder(r,hi-lo,cq.Vector(*p),cq.Vector(*v))

def hexhole(x,y,z0,z1,af):
    r=af/math.sqrt(3)
    w=cq.Wire.makePolygon([cq.Vector(x+r*math.cos(i*math.pi/3),y+r*math.sin(i*math.pi/3),z0) for i in range(6)],close=True)
    return cq.Solid.extrudeLinear(w,[],cq.Vector(0,0,z1-z0))

def mesh(s,id,name,cat,**kwargs):
    assert s.isValid() and len(s.Solids())==1,id
    verts,tris=s.tessellate(.025,.15)
    b=s.BoundingBox()
    p=dict(id=id,name=name,category=cat,positions=[round(float(n),6) for v in verts for n in v.toTuple()],indices=[int(j) for t in tris for j in t],dimensions=[b.xlen,b.ylen,b.zlen])
    p.update(kwargs)
    return p

def render_bbox(p):
    a=np.asarray(p['positions']).reshape(-1,3)
    return a.min(axis=0),a.max(axis=0)

def main():
    family=json.loads(gzip.decompress((ROOT/'reference-models.json.gz').read_bytes()))
    result={};checks={}
    for key,old in family.items():
        meta=copy.deepcopy(old['meta']);W,D,H=meta['metalEnvelopeMm']
        ox,oy=W/2+1.2,D/2+1.2
        seat,platez,platetop,liptop=92.7,122.2,123.7,124.0
        # Thin broad locating blades. They slide vertically into existing front/back gaps.
        # Outer face is 0.7mm inside the R6 upper guard opening; thickness 2mm.
        tab_y=-D/2+3.2;tab_inner=tab_y+2.0
        tab_xmax=W/2-3.2;tab_bottom=80.2
        screw_front=(ox*.30,-oy+6.)
        screw_side=(ox-6.,-oy*.5)
        wallpieces=[box(.2,ox,-oy,-oy+1.5,seat,liptop),
                    box(ox-1.5,ox,-oy+1.5,-.2,seat,liptop)]
        ledgepieces=[box(.2,ox,-oy,-oy+8.,platez-1.5,platez),
                     box(ox-8.,ox,-oy+8.,-.2,platez-1.5,platez)]
        bosses=[box(screw_front[0]-7,screw_front[0]+7,-oy,-oy+11,platez-4.4,platez),
                box(ox-11,ox,screw_side[1]-7,screw_side[1]+7,platez-4.4,platez)]
        # The bottom of this lid is open; there are no catches, undercuts or rotating parts.
        tab=box(.2,tab_xmax,tab_y,tab_inner,tab_bottom,seat+2.5)
        bottomedges=[e for e in tab.Edges() if abs(e.BoundingBox().zmin-tab_bottom)<1e-5 and abs(e.BoundingBox().zmax-tab_bottom)<1e-5]
        tab=tab.fillet(.4,bottomedges).clean()
        bridge=box(.2,tab_xmax,-oy,tab_inner,seat,seat+2.5)
        upper=fuse(wallpieces+ledgepieces+bosses+[bridge])
        for x,y in (screw_front,screw_side):
            upper=upper.cut(cylinder(2,platez-5,platetop+1,(x,y,0),1.7))
            upper=upper.cut(hexhole(x,y,platez-4.6,platez-1.5,5.9)).clean()
        assert upper.isValid()
        # Avoid coincident, duplicate surface rendering. Conceptually this is one PA12 piece.
        blade_visible=tab.cut(upper).clean()
        fullframe=fuse([upper,tab])
        transforms=[('FR',lambda s:s),('FL',lambda s:s.mirror('YZ')),('BL',lambda s:s.rotate((0,0,0),(0,0,1),180)),('BR',lambda s:s.mirror('YZ').rotate((0,0,0),(0,0,1),180))]
        lid=[]
        for label,tf in transforms:
            lid.append(mesh(tf(upper),f'{key}-simple-frame-{label}',f'蓋PA12枠 / {label}','lidFrame',note='組立用M3は残す。蓋と本体の固定機構はなし。'))
            lid.append(mesh(tf(blade_visible),f'{key}-locator-{label}',f'前後の位置決め用差し込み / {label}','locator',note='PA12枠と一体の段差。厚さ2mm、差込12mmの模式設計。'))
        # Reuse only the lid plate, its assembly screws/nuts and seat strips, NOT old locks.
        for p in old['lid']:
            if p['category'] in ['lidMetal','lidGasket'] or '-lid-top-' in p.get('id',''):
                lid.append(p)
        body=copy.deepcopy(old['body'])
        for side,y0,y1 in [('front',-D/2,-D/2+1.5),('back',D/2-1.5,D/2)]:
            s=box(-W/2+1.5,W/2-1.5,y0,y1,1.5,H)
            for x,_,z in old['frontHoles' if side=='front' else 'backHoles']:
                s=s.cut(cylinder(1,y0-1,y1+1,(x,0,z),2.75)).clean()
            body.append(mesh(s,f'{key}-metal-{side}',('前板' if side=='front' else '後板')+' / 蓋ロック穴なし','metal'))
        # Actual CAD checks only for the new broad blades vs source outer envelope and brackets.
        # No force/tolerance/wear certification, and no strap deformation calculation.
        side_guard_boundary=W/2-2.5
        blade_to_guard=side_guard_boundary-tab_xmax
        envelopefront=-meta['railUnitDepthMm']/2
        tab_to_unit=envelopefront-tab_inner
        bracket_max=max(render_bbox(p)[1][2] for p in body if p['category']=='brackets')
        assert abs(blade_to_guard-.7)<1e-6
        assert tab_to_unit>4 and tab_bottom>bracket_max
        meta['revision']='R8-SIMPLE-LID-PREVIEW'
        meta['lidSlotCount']=0
        meta['panelHoleCountIncludingLid']=meta['panelHoleCount']
        meta['lidAvailable']=True
        meta['lidToBodyLocks']=0
        meta['lidRiseAboveGuardMm']=30
        meta['status']='Preview-only update: simple locating lid plus optional generic external straps. Manufacturing files unchanged.'
        # Remove the obsolete R7 locking claim from inherited metadata.
        meta['notes']=[x for x in meta.get('notes',[]) if 'M3' not in x]
        span=min(W,D)+2.4
        axis='x' if W<=D else 'y'
        longdim=D if axis=='x' else W
        # Stations avoid the inherited top screw positions and nominal case fixing positions.
        stations=[-longdim*(.30 if axis=='x' else .25),longdim*(.30 if axis=='x' else .25)]
        info=dict(lidRiseMm=30,locatorThicknessMm=2.,locatorEngagementMm=12.,locatorClearanceToGuardMm=.7,frontGapMm=meta['frontBackOpenGapMm'],lidOuterMm=[W+2.4,D+2.4],lidPlateMm=[W-1.8,D-1.8,1.5],bodyHeightMm=H,closedTopMm=125.8,closedHeightIncludingFeetMm=128.8,strapWidthMm=20.,strapThicknessMm=1.4,strapAxis=axis,strapStationsMm=stations,strapLoopGeometricEstimateMm=round(2*(span+128.8),1),strapNote='汎用バンドを模式表示。バックル・重なり代・突起や実際の締付による長さ差は含まない。')
        result[key]=dict(meta=meta,body=body,lid=lid,info=info)
        checks[key]=dict(bodyMetalPanels=sum(p['category']=='metal' for p in body),lidFrames=4,lidToBodyLocks=0,assemblyTopBolts=sum('-lid-top-bolt-' in p['id'] for p in lid),locatorToGuardMm=blade_to_guard,locatorToRailUnitEnvelopeMm=tab_to_unit,locatorToHighestBracketMm=tab_bottom-bracket_max,frameBRepValid=fullframe.isValid(),frontBackExtraLockHoles=0,sourcePreserved='body/rail/PCB meshes from R6/R7; front/back panels rebuilt with original M5 holes only',previewNotManufacturing=True)
        print(key,checks[key],flush=True)
    raw=json.dumps(result,ensure_ascii=False,separators=(',',':')).encode()
    compressed=gzip.compress(raw,compresslevel=9,mtime=0)
    (ROOT/'model-data.js').write_text('window.ZUDO_SIMPLE_MODEL_GZIP = '+json.dumps(base64.b64encode(compressed).decode())+';\n')
    (ROOT/'geometry-checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'preview-parameters.json').write_text(json.dumps({k:m['info'] for k,m in result.items()},ensure_ascii=False,indent=2)+'\n')
    print('Display payload',len(raw),'bytes ->',len(compressed),'gzip bytes')
if __name__=='__main__': main()
