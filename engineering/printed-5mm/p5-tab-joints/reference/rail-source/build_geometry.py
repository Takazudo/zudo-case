"""Zudo case family R6 source-CAD based geometry. CadQuery 2.7 + NumPy + ezdxf; units mm.

Run: python build_geometry.py
Edit design-parameters.json inputs, then rerun to regenerate mesh/STL/STEP/DXF.
The input rail mesh is preserved as supplied. Its non-manifold topology is
reported and excluded from BREP STEP exports. Physical thicknesses and hardware
not supplied by the user remain explicitly provisional.
"""
from pathlib import Path
import json, math, struct
from collections import Counter
import cadquery as cq
import numpy as np
import ezdxf
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib

ROOT=Path(__file__).resolve().parent
PARAM_FILE=ROOT/'design-parameters.json'
PARAM=json.loads(PARAM_FILE.read_text())
def iv(key): return PARAM['inputs'][key]['value']
ALL_PANELS=json.loads((ROOT/PARAM['sourceData']['panels']).read_text())
GLOBAL_ENGINEERING=ROOT/'engineering';GLOBAL_ENGINEERING.mkdir(parents=True,exist_ok=True)
BASE_VOLUME_CM3=PARAM['comparisons']['r2OriginalVolumeCm3']


def normalized_panel(kind):
    data=json.loads(json.dumps(ALL_PANELS['panels'][kind]))
    swap=kind=='fixer7u'
    for contour in [data['outer']]+data['cutouts']:
        if swap:contour['points']=[[v,u] for u,v in contour['points']]
        points=np.array(contour['points']);lo=points.min(axis=0);hi=points.max(axis=0)
        contour['bbox']={'min':lo.tolist(),'max':hi.tolist(),'center':((lo+hi)/2).tolist(),'dimensions':(hi-lo).tolist()}
    data['normalizedCoordinateMap']='u=rawY,v=rawX' if swap else 'u=rawX,v=rawY'
    return data


def configure(model_id):
    global MODEL_ID,MODEL,PANELS,RAIL_MESH,RAIL_META,L,TF,TP,SP,OW,T,FRAME,INNER,W,D,H,TOP,XM,YM,BR_T,INSET,BOARD_Y0,ENGINEERING,SHAPES,VALIDATION,ALUMINUM_EXPORTS,RAIL_HOLES,PADDER_PLACEMENTS,MOUNTS,BOTTOM_XS,BOTTOM_YS,MOUNT_Z,MOUNT_YS,UNIT_HALF_DEPTH,MINIMUM_D
    MODEL_ID=model_id;MODEL=PARAM['models'][model_id]
    PANELS={'panels':{k:normalized_panel(k) for k in ALL_PANELS['panels']}}
    PANELS['panels']['fixer']=PANELS['panels'][MODEL['fixer']]
    RAIL_MESH=json.loads((ROOT/PARAM['sourceData'][MODEL['rail']]).read_text())
    RAIL_META=json.loads((ROOT/'source-data'/MODEL['rail']/'rail_dimensions.json').read_text())
    rp=np.array(RAIL_MESH['positions']).reshape(-1,3);L=float(np.ptp(rp[:,2]))
    TF=iv('fixerThicknessMm');TP=iv('padderThicknessMm');SP=iv('innerSpacerThicknessMm');OW=iv('outerWasherThicknessMm');T=iv('metalThicknessMm')
    FRAME=L+2*(TF+TP);INNER=FRAME+2*SP;W=INNER+2*T
    fixer=PANELS['panels']['fixer'];BOARD_Y0=fixer['outer']['bbox']['center'][0]
    H=iv('caseHeightMm');TOP=H-iv('fixerTopOffsetBelowCaseMm')
    circles=[c for c in fixer['cutouts'] if max(c['bbox']['dimensions'])<6]
    circles.sort(key=lambda c:c['bbox']['center'][0])
    if model_id.startswith('3u'):
        RAIL_HOLES=circles
        PADDER_PLACEMENTS=[dict(kind='padder3u',u=0.,v=0.,row=0,label='3U')]
        MOUNTS=[dict(u=BOARD_Y0+u,v=21.3105735,row=0) for u in [-45,45]]
    else:
        wanted=[6.0332935,128.533836,140.5298535,263.030426,275.0617065,308.7211605]
        RAIL_HOLES=[min(circles,key=lambda c:abs(c['bbox']['center'][0]-u)) for u in wanted]
        assert all(abs(h['bbox']['center'][0]-u)<1e-6 for h,u in zip(RAIL_HOLES,wanted))
        PADDER_PLACEMENTS=[dict(kind='padder3u',u=0.,v=0.,row=0,label='3U 1'),dict(kind='padder3u',u=134.531860,v=0.,row=1,label='3U 2'),dict(kind='padder1u',u=269.039027,v=-.025081,row=2,label='1U')]
        MOUNTS=[dict(u=u,v=21.3105735,row=i//2) for i,u in enumerate([22.8453565,90.111288,157.37722,224.6431425,291.873764])]
    for index,hole in enumerate(RAIL_HOLES):hole['railIndex']=index
    extents=[fixer['outer']['bbox']]
    for placement in PADDER_PLACEMENTS:
        bb=PANELS['panels'][placement['kind']]['outer']['bbox']
        extents.append({'min':[bb['min'][0]+placement['u'],bb['min'][1]+placement['v']],'max':[bb['max'][0]+placement['u'],bb['max'][1]+placement['v']]})
    # The lip of each rail is checked in the same registered coordinates.
    cx=14.930564880371094;cy=6.7535858154296875
    for i,hole in enumerate(RAIL_HOLES):
        sy=-1 if i%2==0 else 1;u,v=hole['bbox']['center']
        ys=sy*(rp[:,1]-cy)+u
        extents.append({'min':[float(ys.min()),0],'max':[float(ys.max()),0]})
    halfdepth=max(max(abs(e['min'][0]-BOARD_Y0),abs(e['max'][0]-BOARD_Y0)) for e in extents)
    UNIT_HALF_DEPTH=halfdepth;MINIMUM_D=2*(halfdepth+iv('frontBackInsideClearanceMm')+T)
    D=float(math.ceil(MINIMUM_D))
    MOUNT_Z=TOP-21.3105735;MOUNT_YS=[m['u']-BOARD_Y0 for m in MOUNTS]
    XM=W/2-T;YM=D/2-T;BR_T=iv('bracketThicknessMm');INSET=iv('bracketHoleInsetMm')
    # Preserve 60HP X placement while following the actual shorter 40HP rail.
    BOTTOM_XS=[-(XM-53.7),XM-53.7]
    BOTTOM_YS=[-(D/2-40.5),D/2-40.5] if MODEL['sideBottomBracketCount']==2 else [-(D/2-40.5),0.,D/2-40.5]
    ENGINEERING=GLOBAL_ENGINEERING/model_id
    SHAPES={};VALIDATION={};ALUMINUM_EXPORTS=[]
    for path in (ENGINEERING,ENGINEERING/'aluminum',ENGINEERING/'pcbs',ENGINEERING/'guards'):path.mkdir(parents=True,exist_ok=True)

def box(x0,x1,y0,y1,z0,z1):
    return cq.Solid.makeBox(x1-x0,y1-y0,z1-z0,cq.Vector(x0,y0,z0))


def union(boxes):
    result=box(*boxes[0])
    for values in boxes[1:]:
        result=result.fuse(box(*values))
    result=result.clean()
    assert result.isValid() and len(result.Solids())==1
    return result


def at_origin(shape):
    b=exact_bbox(shape)
    return shape.translate(cq.Vector(-b.xmin,-b.ymin,-b.zmin))


def exact_bbox(shape):
    b=Bnd_Box()
    BRepBndLib.AddOptimal_s(shape.wrapped,b,False,False)
    return cq.BoundBox(b)


def bounds(shape):
    b=exact_bbox(shape)
    return [b.xlen,b.ylen,b.zlen]


def near(a,b):
    return abs(a-b)<1e-5


def round_edges(shape, radius, predicate, count):
    if radius==0:
        return shape
    chosen=[e for e in shape.Edges() if e.geomType()=='LINE' and predicate(e.BoundingBox())]
    assert len(chosen)==count,(len(chosen),count)
    result=shape.Solids()[0].fillet(radius,chosen).clean()
    assert result.isValid() and len(result.Solids())==1
    return result


def base_geometry(t=1.2, cover=5., radius=.4, split=True):
    """R3 guard layout, recomputed from current nominal case dimensions."""
    ox,oy=W/2+t,D/2+t
    ix,iy=W/2-T-iv("guardInnerOverhangMm"),D/2-T-iv("guardInnerOverhangMm")
    top=union([
        (-ox,ox,-oy,-iy,H,H+t), (-ox,ox,iy,oy,H,H+t),
        (-ox,-ix,-iy,iy,H,H+t), (ix,ox,-iy,iy,H,H+t),
        (-ox,ox,-oy,-D/2,H-cover,H), (-ox,ox,D/2,oy,H-cover,H),
        (-ox,-W/2,-D/2,D/2,H-cover,H), (W/2,ox,-D/2,D/2,H-cover,H),
    ])
    top=round_edges(top,radius,
        lambda b:near(b.zmin,H+t) and near(b.zmax,H+t) and
        ((near(abs(b.xmin),ox) and near(b.xmin,b.xmax)) or
         (near(abs(b.ymin),oy) and near(b.ymin,b.ymax))),4)
    long=union([
        (-ox,ox,-oy,-D/2+cover,-t,0),
        (-ox,ox,-oy,-D/2,0,cover),
    ])
    long=round_edges(long,radius,
        lambda b:near(b.ymin,-oy) and near(b.ymax,-oy) and
        near(b.zmin,-t) and near(b.zmax,-t),1)
    short=union([
        (-ox,-W/2+cover,-D/2+cover,D/2-cover,-t,0),
        (-ox,-W/2,-D/2,D/2,0,cover),
    ])
    short=round_edges(short,radius,
        lambda b:near(b.xmin,-ox) and near(b.xmax,-ox) and
        near(b.zmin,-t) and near(b.zmax,-t),1)
    corner=union([
        (-ox,-W/2+cover,-oy,-D/2,cover,H-cover),
        (-ox,-W/2,-D/2,-D/2+cover,cover,H-cover),
    ])
    corner=round_edges(corner,radius,
        lambda b:near(b.xmin,-ox) and near(b.xmax,-ox) and
        near(b.ymin,-oy) and near(b.ymax,-oy),1)
    if split:
        cut_half=box(-1000,0,-1000,1000,-1000,1000)
        top_part=top.intersect(cut_half).clean()
        long_part=long.intersect(cut_half).clean()
        top_parts=[top_part,top_part.rotate((0,0,0),(0,0,1),180)]
        front_parts=[long_part,long_part.translate(cq.Vector(ox,0,0))]
        bottom_parts=front_parts+[s.rotate((0,0,0),(0,0,1),180) for s in front_parts]
        quantities=[2,4,2,4]
    else:
        top_part,long_part=top,long
        top_parts=[top]
        bottom_parts=[long,long.rotate((0,0,0),(0,0,1),180)]
        quantities=[1,2,2,4]
    cc=at_origin(corner)
    corner_parts=[]
    for sx,sy,angle in ((-1,-1,0),(-1,1,-90),(1,1,180),(1,-1,90)):
        transformed=at_origin(cc.rotate((0,0,0),(0,0,1),angle))
        xmin=-ox if sx<0 else W/2-cover
        ymin=-oy if sy<0 else D/2-cover
        corner_parts.append(transformed.translate(cq.Vector(xmin,ymin,cover)))
    assembly=top_parts+bottom_parts+[short,short.rotate((0,0,0),(0,0,1),180)]+corner_parts
    parts=[top_part,long_part,short,corner]
    assert all(s.isValid() and len(s.Solids())==1 for s in parts)
    return parts,quantities,assembly,dict(outer_x=ox,outer_y=oy,thickness=t,cover=cover,radius=radius)


def vec(axis):
    return cq.Vector(*[1 if i==axis else 0 for i in range(3)])


def cylinder(axis, a0, a1, center, radius):
    a0,a1=sorted((a0,a1))
    origin=list(center);origin[axis]=a0
    return cq.Solid.makeCylinder(radius,a1-a0,cq.Vector(*origin),vec(axis))


def drill(shape, axis, center, radius=2.75):
    b=exact_bbox(shape)
    a0=(b.xmin,b.ymin,b.zmin)[axis]-1
    a1=(b.xmax,b.ymax,b.zmax)[axis]+1
    result=shape.cut(cylinder(axis,a0,a1,center,radius)).clean()
    assert result.isValid() and len(result.Solids())==1
    return result


def tube(axis,a0,a1,center,radius=5,inner=2.75):
    return cylinder(axis,a0,a1,center,radius).cut(cylinder(axis,min(a0,a1)-1,max(a0,a1)+1,center,inner)).clean()


def rounded(values, digits=8):
    return [round(float(v),digits) or 0 for v in values]


def mesh_part(shape, id, name, category, group='enclosure', explode=(0,0,0), **extra):
    assert shape.isValid(),id
    SHAPES[id]=shape
    # At least 80 segments per full circle; accurate enough for close browser views.
    vertices,triangles=shape.tessellate(.003,.08)
    bb=exact_bbox(shape)
    result=dict(id=id,name=name,category=category,group=group,
        positions=rounded([value for v in vertices for value in v.toTuple()]),
        indices=[int(i) for triangle in triangles for i in triangle],
        center=rounded([(bb.xmin+bb.xmax)/2,(bb.ymin+bb.ymax)/2,(bb.zmin+bb.zmax)/2]),
        dimensions=rounded([bb.xlen,bb.ylen,bb.zlen]),
        volumeCm3=round(shape.Volume()/1000,7),explode=list(explode),**extra)
    assert max(result['indices'])<len(result['positions'])//3
    return result


def write_json(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def export_solid(shape,base):
    """A standalone part, all dimensions in mm. STEP retains CAD curves."""
    base.parent.mkdir(parents=True,exist_ok=True)
    shape.exportStl(str(base.with_suffix('.stl')),tolerance=.001,angularTolerance=.06,ascii=False,relative=False)
    cq.exporters.export(shape,str(base.with_suffix('.step')))


def write_dxf(path,width,height,holes):
    # Standard millimetre DXF with explicit entity subclasses/tables.
    doc=ezdxf.new('R2010');doc.units=ezdxf.units.MM
    doc.layers.new('OUTLINE');doc.layers.new('HOLES')
    model=doc.modelspace()
    model.add_lwpolyline([(0,0),(width,0),(width,height),(0,height)],close=True,dxfattribs={'layer':'OUTLINE'})
    for x,y in holes:model.add_circle((x,y),iv('metalClearanceHoleDiameterMm')/2,dxfattribs={'layer':'HOLES'})
    doc.saveas(str(path))
    reread=ezdxf.readfile(path);audit=reread.audit()
    assert not audit.errors and not audit.fixes,(path.name,audit.errors,audit.fixes)
    circles=list(reread.modelspace().query('CIRCLE'));outlines=list(reread.modelspace().query('LWPOLYLINE'))
    assert len(outlines)==1 and outlines[0].closed and len(circles)==len(holes)
    assert reread.units==ezdxf.units.MM
    for circle,(x,y) in zip(circles,holes):
        assert abs(circle.dxf.center.x-x)<1e-9 and abs(circle.dxf.center.y-y)<1e-9
    VALIDATION.setdefault('aluminumDXF',[]).append(dict(file=str(path.relative_to(ROOT)),units='mm',holeCount=len(holes),auditErrors=0,auditFixes=0,closedOutline=True))


def local_panel(width,height,holes):
    shape=box(0,width,0,height,0,T)
    for x,y in holes:shape=drill(shape,2,(x,y,0),iv('metalClearanceHoleDiameterMm')/2)
    return shape


def pcb_solid(kind,x0,thickness,offset_u=0.,offset_v=0.):
    """Preserve every source Edge.Cuts point; no circle fitting or centering repair."""
    data=PANELS['panels'][kind]
    def wire(points):return cq.Wire.makePolygon([cq.Vector(x0,u+offset_u-BOARD_Y0,TOP-v-offset_v) for u,v in points],close=True)
    outer=wire(data['outer']['points']);holes=[wire(c['points']) for c in data['cutouts']]
    shape=cq.Solid.extrudeLinear(outer,holes,cq.Vector(thickness,0,0))
    assert shape.isValid() and len(shape.Solids())==1,(kind,'PCB invalid')
    expected=data['materialAreaMm2']*thickness
    assert abs(shape.Volume()-expected)<1e-4,(kind,shape.Volume(),expected)
    return shape


def rail_mesh_part(index,hole):
    sy=-1 if index%2==0 else 1
    u,v=hole['bbox']['center'];target_y=u-BOARD_Y0;target_z=TOP-v
    cx=14.930564880371094;cy=6.7535858154296875
    matrix=np.array([[0,0,sy,-sy*L/2],[0,sy,0,target_y-sy*cy],[-1,0,0,target_z+cx],[0,0,0,1]],dtype=float)
    assert abs(np.linalg.det(matrix[:3,:3])-1)<1e-12
    source=np.array(RAIL_MESH['positions'],dtype=float).reshape(-1,3)
    pts=source@matrix[:3,:3].T+matrix[:3,3];lo=pts.min(axis=0);hi=pts.max(axis=0)
    return dict(id=f'rail-{index+1}',name=f'レール {index+1} / {MODEL["layout"][index//2]}',category='rails',group='railUnit',role='rail',
        positions=pts.reshape(-1).tolist(),indices=RAIL_MESH['indices'],center=((lo+hi)/2).tolist(),dimensions=(hi-lo).tolist(),
        volumeCm3=None,explode=[0,0,120],approximate=False,sourceTransform=matrix.tolist(),sourceTriangleCount=RAIL_MESH.get('triangleCount',len(RAIL_MESH['indices'])//3),
        railIndex=index,railRow=index//2,axisCenterYZ=[target_y,target_z],sourceUrl=RAIL_MESH['source'].get('stl_url',''),
        material='既存zudo-rail（材質は元STLからは判別不可）',note='提供STLの全頂点・全三角形を剛体配置。元重複面は未修復。')


def hex_nut(sx,y,z):
    r=iv('lockNutAcrossFlatsMm')/math.sqrt(3)
    start=sx*(W/2+OW);end=start+sx*iv('lockNutHeightMm');a,b=sorted((start,end))
    wire=cq.Wire.makePolygon([cq.Vector(a,y+r*math.cos(math.pi*i/3),z+r*math.sin(math.pi*i/3)) for i in range(6)],close=True)
    shape=cq.Solid.extrudeLinear(wire,[],cq.Vector(b-a,0,0))
    return shape.cut(cylinder(0,a-1,b+1,(0,y,z),2.5)).clean()


def generic_nut(axis,a0,a1,center):
    a,b=sorted((a0,a1));r=iv('lockNutAcrossFlatsMm')/math.sqrt(3);other=[i for i in range(3) if i!=axis]
    points=[]
    for i in range(6):
        c=list(center);c[axis]=a;c[other[0]]+=r*math.cos(math.pi*i/3);c[other[1]]+=r*math.sin(math.pi*i/3);points.append(cq.Vector(*c))
    wire=cq.Wire.makePolygon(points,close=True)
    return cq.Solid.extrudeLinear(wire,[],vec(axis)*(b-a)).cut(cylinder(axis,a-1,b+1,center,2.5)).clean()


def common_geometry():
    result=[]; holes=[]
    # All panel joint holes are derived from bracket datums, not the older PDF.
    bottom_holes=[(x,sy*(YM-INSET),0) for sy in (-1,1) for x in BOTTOM_XS]+[(sx*(XM-INSET),y,0) for sx in (-1,1) for y in BOTTOM_YS]
    front_holes=[(x,0,T+INSET) for x in BOTTOM_XS]+[(sx*(XM-INSET),0,z) for z in iv('verticalBracketCenterHeightsMm') for sx in (-1,1)]
    side_holes=[(0,y,T+INSET) for y in BOTTOM_YS]+[(0,sy*(YM-INSET),z) for z in iv('verticalBracketCenterHeightsMm') for sy in (-1,1)]
    side_mount=[(0,y,MOUNT_Z) for y in MOUNT_YS]
    def panel(shape,id,name,axis,centers,explode,part_type):
        for center in centers:shape=drill(shape,axis,center,iv('metalClearanceHoleDiameterMm')/2)
        result.append(mesh_part(shape,id,name,'metal',explode=explode,role='aluminumPanel',
            approximate=False,dimensionalStatus='design_nominal',note='幅は実レール積層から計算。奥行・高さ・穴配置は今回の設計値。穴位置は在庫ブラケット詳細確認前。',
            holeCount=len(centers),material='A5052 t1.5 mm（候補）／黒アルマイト',partType=part_type,
            panelAxis=axis,holeCenters=[list(c) for c in centers]))
        for i,c in enumerate(centers):holes.append((id,axis,c,explode,i))
    panel(box(-W/2,W/2,-D/2,D/2,0,T),'metal-bottom','底板',2,bottom_holes,(0,0,-72),'bottom')
    for sy,slug,label in [(-1,'front','前板'),(1,'back','後板')]:
        y0,y1=sorted((sy*YM,sy*D/2))
        panel(box(-XM,XM,y0,y1,T,H),'metal-'+slug,label,1,[(x,sy*D/2,z) for x,y,z in front_holes],(0,sy*72,0),'front_back')
    for sx,slug,label in [(-1,'left','左側板'),(1,'right','右側板')]:
        x0,x1=sorted((sx*XM,sx*W/2))
        panel(box(x0,x1,-D/2,D/2,T,H),'metal-'+slug,label,0,[(sx*W/2,y,z) for x,y,z in side_holes+side_mount],(sx*72,0,0),'left_right')
    assert len(holes)==2*(12+2*MODEL['sideBottomBracketCount'])+2*len(MOUNTS)
    prototypes=[('bottom',W,D,[(x+W/2,y+D/2) for x,y,z in bottom_holes],1),
                ('front_back',W-2*T,H-T,[(x+XM,z-T) for x,y,z in front_holes],2),
                ('left_right',D,H-T,[(y+D/2,z-T) for x,y,z in side_holes+side_mount],2)]
    for slug,width,height,uv,quantity in prototypes:
        shape=local_panel(width,height,uv)
        base=ENGINEERING/'aluminum'/f'{MODEL_ID}_r6_aluminum_{slug}_qty{quantity}_mm'
        export_solid(shape,base);write_dxf(base.with_suffix('.dxf'),width,height,uv)
        ALUMINUM_EXPORTS.append(dict(partType=slug,quantity=quantity,widthMm=width,heightMm=height,thicknessMm=T,
            holeDiameterMm=iv('metalClearanceHoleDiameterMm'),holeCentersUV=uv,holeCount=len(uv),origin='lower left, local XY',
            files={ext:str(base.with_suffix('.'+ext).relative_to(ROOT)) for ext in ('stl','step','dxf')}))
    write_json(ENGINEERING/'aluminum'/'hole-layout.json',dict(units='mm',panels=ALUMINUM_EXPORTS,
        totalPanels=sum(p['quantity'] for p in ALUMINUM_EXPORTS),totalHoles=sum(p['quantity']*p['holeCount'] for p in ALUMINUM_EXPORTS),
        symmetry='前後同型・左右同型（両面同一仕上げを想定）。7U取付点は元長穴中心を保持し、前後対称化していない。',
        warning='穴配置は20×20×16ブラケットの穴位置を仮定した設計データ。未確認の実物ブラケットを前提とする最終発注図ではない。'))
    print(f'{MODEL_ID}: Aluminum 5 panels / 3 types / {len(holes)} holes exported',flush=True)
    # Sixteen actual outer-size brackets; profile thickness and bend radius remain provisional.
    counter=0
    def bracket(shape,axis_holes,explode):
        nonlocal counter
        counter+=1
        for axis,c in axis_holes:shape=drill(shape,axis,c)
        result.append(mesh_part(shape,f'bracket-{counter:02d}',f'Lブラケット {counter:02d}','brackets',explode=explode,role='panelBracket',
            approximate=True,note='在庫外寸20×20×16mm・実測板厚2mm。穴内面から10mmは未実測の提案位置。曲げR省略。占有厚2.2mmも別途検証。',
            material='手持ちのステンレスLブラケット',holeAxes=[dict(axis=a,center=list(c)) for a,c in axis_holes]))
    for sy in (-1,1):
        for x in BOTTOM_XS:
            a,b=sorted((sy*YM,sy*(YM-20)));c,d=sorted((sy*YM,sy*(YM-BR_T)))
            bracket(union([(x-8,x+8,a,b,T,T+BR_T),(x-8,x+8,c,d,T,T+20)]),
                [(2,(x,sy*(YM-INSET),0)),(1,(x,0,T+INSET))],(0,sy*44,-24))
    for sx in (-1,1):
        for y in BOTTOM_YS:
            a,b=sorted((sx*XM,sx*(XM-20)));c,d=sorted((sx*XM,sx*(XM-BR_T)))
            bracket(union([(a,b,y-8,y+8,T,T+BR_T),(c,d,y-8,y+8,T,T+20)]),
                [(2,(sx*(XM-INSET),y,0)),(0,(0,y,T+INSET))],(sx*44,0,-24))
    for sx in (-1,1):
        for sy in (-1,1):
            for z in iv('verticalBracketCenterHeightsMm'):
                a,b=sorted((sx*XM,sx*(XM-20)));c,d=sorted((sy*YM,sy*(YM-BR_T)))
                e,f=sorted((sx*XM,sx*(XM-BR_T)));g,h=sorted((sy*YM,sy*(YM-20)))
                bracket(union([(a,b,c,d,z-8,z+8),(e,f,g,h,z-8,z+8)]),
                    [(1,(sx*(XM-INSET),0,z)),(0,(0,sy*(YM-INSET),z))],(sx*44,sy*44,0))
    assert counter==12+2*MODEL['sideBottomBracketCount']
    print(f'{MODEL_ID}: Brackets {counter}, vertical centers {iv("verticalBracketCenterHeightsMm")}',flush=True)
    # Source rails, a single fixer on each side, and row-specific padders.
    for i,hole in enumerate(RAIL_HOLES):result.append(rail_mesh_part(i,hole))
    for sx in (-1,1):
        label='左' if sx<0 else '右'
        pcb_layers=[dict(kind='fixer',start=L/2+TP,thickness=TF,u=0.,v=0.,id=f'fixer-{sx}',role='fixer',label=label+' '+MODEL['fixer'])]
        for placement in PADDER_PLACEMENTS:
            pcb_layers.append(dict(kind=placement['kind'],start=L/2,thickness=TP,u=placement['u'],v=placement['v'],
                id=f'padder-{sx}-row{placement["row"]}',role='padder',label=label+' '+placement['label']+' padder',row=placement['row']))
        for layer in pcb_layers:
            a,b=sorted((sx*layer['start'],sx*(layer['start']+layer['thickness'])))
            shape=pcb_solid(layer['kind'],a,layer['thickness'],layer['u'],layer['v'])
            result.append(mesh_part(shape,layer['id'],layer['label'],'rails','railUnit',(0,0,120),role=layer['role'],
                approximate=False,note='元KiCad全輪郭頂点を保持。厚さ1.6mmは確認済。パダーは外形境界基準で配置し元穴中心微差を補正しない。',
                material='既存PCB / t1.6mm',thicknessMm=layer['thickness'],sourcePolygonKind=layer['kind'],
                sourcePlacementUV=[layer['u'],layer['v']],railRow=layer.get('row'),sourceUrl=PANELS['panels'][layer['kind']]['source']['source_url']))
            if sx==1:export_solid(at_origin(shape),ENGINEERING/'pcbs'/f'{MODEL_ID}_r6_{layer["id"]}_source_outline_mm')
        for mount_index,mount in enumerate(MOUNTS):
            y=mount['u']-BOARD_Y0;z=TOP-mount['v'];suffix=f'{sx}-{mount_index+1}';side=label+f' 取付{mount_index+1}'
            a,b=sorted((sx*FRAME/2,sx*(FRAME/2+SP)))
            spacer=tube(0,a,b,(0,y,z),iv('nylonOuterDiameterMm')/2,iv('nylonInnerDiameterMm')/2)
            result.append(mesh_part(spacer,'spacer-'+suffix,side+' 8mmスペーサー','spacers','spacers',(sx*48,0,80),role='innerSpacer',
                approximate=True,note='厚さ8mmは指定。内径5.5mm・外径10mmは表示用仮寸法。',material='ナイロン',thicknessMm=SP))
            a,b=sorted((sx*W/2,sx*(W/2+OW)))
            washer=tube(0,a,b,(0,y,z),iv('nylonOuterDiameterMm')/2,iv('nylonInnerDiameterMm')/2)
            result.append(mesh_part(washer,'outer-washer-'+suffix,side+' 外1mmワッシャー','spacers','outerWashers',(sx*95,0,80),role='outerWasher',
                approximate=True,note='厚さ1mmは指定。内外径は表示用仮寸法。',material='ナイロン',thicknessMm=OW))
            seat=sx*(L/2+TP);tip=seat+sx*iv('mountBoltLengthMm');head_end=seat-sx*iv('mountHeadHeightMm')
            bolt=cylinder(0,head_end,seat,(0,y,z),iv('mountHeadDiameterMm')/2).fuse(cylinder(0,seat,tip,(0,y,z),2.5)).clean()
            result.append(mesh_part(bolt,'mount-bolt-'+suffix,side+' 内側M5固定ボルト','fasteners','mountBolts',(-sx*45,0,80),role='mountBolt',
                approximate=True,headHeightMm=iv('mountHeadHeightMm'),headDiameterMm=iv('mountHeadDiameterMm'),railRow=mount['row'],
                note='頭厚1.4mm。頭径9mmは模式外形。軸と外側ナットは模式表示で部品長の指定ではない。ねじ山省略。',material='M5低頭ボルト',
                underHeadDatumMm=seat,nominalGripMm=TF+SP+T+OW,axisCenterYZ=[y,z]))
            result.append(mesh_part(hex_nut(sx,y,z),'mount-nut-'+suffix,side+' 外側ロックナット','fasteners','mountNuts',(sx*115,0,80),role='mountNut',
                approximate=True,note='外側締結の模式表示。ナット寸法はケース寸法の計算対象外。',material='ロックナット（模式形状）'))
        for i,hole in enumerate(RAIL_HOLES):
            u,v=hole['bbox']['center'];y=u-BOARD_Y0;z=TOP-v
            seat=sx*FRAME/2;tip=seat-sx*iv('railEndBoltLengthMm');head_end=seat+sx*iv('railEndHeadHeightMm')
            bolt=cylinder(0,seat,head_end,(0,y,z),iv('railEndHeadDiameterMm')/2).fuse(cylinder(0,tip,seat,(0,y,z),2.5)).clean()
            result.append(mesh_part(bolt,f'rail-end-bolt-{sx}-{i+1}',label+f' レール端M5ボルト {i+1}','fasteners','railUnit',(0,0,120),role='railEndBolt',
                approximate=True,note='軸長は旧ガイドM5×40の表示用仮寸法。頭厚1.4mmで内側ブラケット頭との隙間を検証。',material='レール端固定M5',
                axisCenterYZ=[y,z],railIndex=i,headHeightMm=iv('railEndHeadHeightMm')))
    print(f'{MODEL_ID}: {len(RAIL_HOLES)} rails, {2+2*len(PADDER_PLACEMENTS)} PCB layers, {2*len(MOUNTS)} mounting stacks',flush=True)
    # Panel joints: head inside bracket, full schematic shaft, outside washer/nut.
    for panel_id,axis,center,explode,i in holes:
        is_mount=axis==0 and abs(center[2]-MOUNT_Z)<1e-6
        if is_mount:continue
        sign=-1 if axis==2 else (-1 if center[axis]<0 else 1)
        out=center[axis]
        bottom_joint=axis==2
        if bottom_joint:
            seat=out;head_end=out-iv('mountHeadHeightMm');tip=out+T+BR_T+OW+iv('lockNutHeightMm')+1
            washer_a=out+T+BR_T;washer_b=washer_a+OW;nut_a=washer_b;nut_b=nut_a+iv('lockNutHeightMm')
        else:
            seat=out-sign*(T+BR_T);head_end=seat-sign*iv('mountHeadHeightMm');tip=out+sign*(OW+iv('lockNutHeightMm')+1)
            washer_a=out;washer_b=out+sign*OW;nut_a=washer_b;nut_b=out+sign*(OW+iv('lockNutHeightMm'))
        bolt=cylinder(axis,seat,head_end,center,iv('bracketHeadDiameterMm')/2).fuse(cylinder(axis,seat,tip,center,2.5)).clean()
        suffix=f'{panel_id}-{i}';shift=list(explode)
        result.append(mesh_part(bolt,'panel-bolt-'+suffix,f'{"外側" if bottom_joint else "内側"}M5接合ボルト {suffix}','fasteners','enclosure',shift,role='panelJointBolt',approximate=True,
            note=('底板のみ頭を外側、座金とナットを内側へ反転。' if bottom_joint else 'ブラケット内側に頭。')+'頭厚1.4mm。外径12mmと軸長は模式寸法。ねじ山省略。',parentPanel=panel_id,material='M5低頭ボルト',headSide='outside' if bottom_joint else 'inside',
            axis=axis,headSeatMm=seat,headHeightMm=iv('mountHeadHeightMm'),headDiameterMm=iv('bracketHeadDiameterMm')))
        washer=tube(axis,washer_a,washer_b,center,iv('nylonOuterDiameterMm')/2,iv('nylonInnerDiameterMm')/2)
        result.append(mesh_part(washer,'panel-washer-'+suffix,f'{"内側" if bottom_joint else "外側"}ワッシャー {suffix}','spacers','enclosure',shift,role='panelJointWasher',approximate=True,
            note=('底板ブラケット内側の' if bottom_joint else '外側の')+'1mmワッシャーを提案配置。内外径は模式寸法。',parentPanel=panel_id,material='ナイロン'))
        nut=generic_nut(axis,nut_a,nut_b,center)
        result.append(mesh_part(nut,'panel-nut-'+suffix,f'{"内側" if bottom_joint else "外側"}ロックナット {suffix}','fasteners','enclosure',shift,role='panelJointNut',approximate=True,
            note=('底板ブラケット内側の' if bottom_joint else '外側の')+'締結の模式表示。ナット実寸はケース寸法の条件に含めない。',parentPanel=panel_id,material='ロックナット'))
    for sx in (-1,1):
        for sy in (-1,1):
            x=sx*(W/2-iv('footInsetMm'));y=sy*(D/2-iv('footInsetMm'))
            foot=cylinder(2,-iv('footHeightMm'),0,(x,y,0),iv('footDiameterMm')/2)
            result.append(mesh_part(foot,f'foot-{sx}-{sy}','貼付式黒ゴム脚','feet','enclosure',(sx*15,sy*15,-50),role='foot',approximate=True,
                material='黒ゴム（既製貼付式を想定・未選定）',note='φ10×3mm、各外縁から20mm内側の仮配置。穴不要。JLCガードのSTL/体積/数量には含めない。'))
    VALIDATION['panelCount']=5;VALIDATION['panelHoleCount']=len(holes);VALIDATION['bracketCount']=counter
    VALIDATION['commonCategoryCounts']=dict(Counter(p['category'] for p in result))
    VALIDATION['commonRoleCounts']=dict(Counter(p.get('role','') for p in result))
    assert VALIDATION['commonRoleCounts'].get('railEndBolt')==2*len(RAIL_HOLES)
    return result




def inspect_binary_stl(path,cad_shape):
    raw=path.read_bytes();count=struct.unpack('<I',raw[80:84])[0]
    assert len(raw)==84+50*count,(path,'not binary STL')
    dtype=np.dtype([('normal','<f4',(3,)),('vertices','<f4',(3,3)),('attr','<u2')])
    tri=np.frombuffer(raw,dtype=dtype,offset=84,count=count)['vertices'].astype(float)
    verts,inverse=np.unique(tri.reshape(-1,3),axis=0,return_inverse=True);faces=inverse.reshape(-1,3)
    incidence=Counter(tuple(sorted((int(a),int(b)))) for f in faces for a,b in ((f[0],f[1]),(f[1],f[2]),(f[2],f[0])))
    hist=Counter(incidence.values());signed=float(np.einsum('ij,ij->i',tri[:,0],np.cross(tri[:,1],tri[:,2])).sum()/6)
    extents=tri.reshape(-1,3).max(axis=0)-tri.reshape(-1,3).min(axis=0)
    cadvol=cad_shape.Volume();error=abs(signed-cadvol)
    assert hist=={2:len(incidence)},(path.name,hist)
    assert signed>0,(path.name,signed)
    assert error<max(.1,cadvol*.0005),(path.name,error,cadvol)
    assert np.max(abs(extents-np.array(bounds(cad_shape))))<.0001,(path.name,extents,bounds(cad_shape))
    return dict(file=str(path.relative_to(ROOT)),triangleCount=count,closedManifold=True,edgeIncidenceHistogram=dict(hist),
        positiveVolume=True,meshVolumeCm3=signed/1000,cadVolumeCm3=cadvol/1000,absoluteVolumeErrorCm3=error/1000,dimensionsMm=extents.tolist())


def variants_geometry():
    variants={};VALIDATION['guardSTLs']=[]
    for key,t in [('t1p2',1.2),('t1p0',1.)]:
        cover=iv('guardCoverageMm');radius=iv('guardOuterEdgeRadiusMm')
        raw,_,raw_assembly,params=base_geometry(t,cover,radius,False)
        top,long,short,corner=raw;left_half=box(-1000,0,-1000,1000,-1000,1000)
        front_half=box(-1000,1000,-1000,0,-1000,1000);back_half=box(-1000,1000,0,1000,-1000,1000)
        prototype=[];qty=[];names=[];slugs=[];assembly=[];kinds=[]
        def add(s,name,slug,instances):
            kind=len(prototype);prototype.append(s);qty.append(len(instances));names.append(name);slugs.append(slug)
            assembly.extend(instances);kinds.extend([kind]*len(instances))
        if D+2*t<=iv('maxGuardPartLengthMm'):
            s=top.intersect(left_half).clean();add(s,'上端U字ガード','top_u',[s,s.rotate((0,0,0),(0,0,1),180)])
        else:
            for clipping,label in [(front_half,'a'),(back_half,'b')]:
                s=top.intersect(left_half).intersect(clipping).clean()
                add(s,'上端L字ガード '+label.upper(),'top_corner_'+label,[s,s.rotate((0,0,0),(0,0,1),180)])
        s=long.intersect(left_half).clean();ox=W/2+t
        pair=[s,s.translate(cq.Vector(ox,0,0))]
        add(s,'前後下辺・半分','lower_width_half',pair+[p.rotate((0,0,0),(0,0,1),180) for p in pair])
        if D<=iv('maxGuardPartLengthMm'):
            add(short,'左右下辺ガード','lower_depth_full',[short,short.rotate((0,0,0),(0,0,1),180)])
        else:
            for clipping,label in [(front_half,'a'),(back_half,'b')]:
                s=short.intersect(clipping).clean()
                add(s,'左右下辺・半分 '+label.upper(),'lower_depth_half_'+label,[s,s.rotate((0,0,0),(0,0,1),180)])
        add(corner,'縦辺コーナーガード','vertical_corner',raw_assembly[-4:])
        assert max(max(bounds(p)) for p in prototype)<=iv('maxGuardPartLengthMm')+1e-5
        volume=sum(p.Volume()*q for p,q in zip(prototype,qty))/1000
        assert abs(volume-sum(s.Volume() for s in assembly)/1000)<1e-5
        target=ROOT/'stl'/MODEL_ID/key;target.mkdir(exist_ok=True,parents=True)
        for stale in target.glob('*.stl'):stale.unlink()
        files=[];catalog=[]
        for kind,(s,q) in enumerate(zip(prototype,qty)):
            stem=f'{MODEL_ID}_r6_{key}_{kind+1:02d}_{slugs[kind]}_qty{q}_mm';files.append(stem+'.stl');local=at_origin(s)
            local.exportStl(str(target/(stem+'.stl')),tolerance=.001,angularTolerance=.06,ascii=False,relative=False)
            cq.exporters.export(local,str(ENGINEERING/'guards'/(stem+'.step')))
            VALIDATION['guardSTLs'].append(inspect_binary_stl(target/(stem+'.stl'),local))
            catalog.append(dict(partType=slugs[kind],name=names[kind],quantity=q,dimensions=rounded(bounds(local)),
                volumeCm3=round(local.Volume()/1000,8),stlFile=stem+'.stl',stepFile=str((ENGINEERING/'guards'/(stem+'.step')).relative_to(ROOT))))
        parts=[];sequence=[0]*len(prototype)
        for i,(s,kind) in enumerate(zip(assembly,kinds)):
            sequence[kind]+=1;bb=exact_bbox(s);cx=(bb.xmin+bb.xmax)/2;cy=(bb.ymin+bb.ymax)/2
            sx=-1 if cx<0 else 1;sy=-1 if cy<0 else 1;slug=slugs[kind]
            if slug.startswith('top'):explode=(sx*28,sy*20 if 'corner' in slug else 0,70)
            elif slug.startswith('lower_width'):explode=(sx*16,sy*46,-112)
            elif slug.startswith('lower_depth'):explode=(sx*66,sy*16 if 'half' in slug else 0,-112)
            else:explode=(sx*105,sy*88,0)
            parts.append(mesh_part(s,f'{key}-guard-{i+1:02d}',names[kind]+f' {sequence[kind]}','guards',explode=explode,role='edgeGuard',
                approximate=False,partType=slug,stlFile=files[kind],prototypeQuantity=qty[kind],material='PA12-HP Nylon / 黒染め',
                note='R6のケース外形に追従。各部品180mm以内へ分割。接触隙間0mm、保持方法・加工公差は未確定。'))
        stats=dict(thicknessMm=t,coverMm=cover,coverageMm=cover,radiusMm=radius,partCount=len(assembly),totalGuardParts=len(assembly),
            typeCount=len(prototype),quantities=qty,totalVolumeCm3=round(volume,8),volumeCm3=round(volume,8),approxMassG=round(volume*1.01,3),
            maxPartLengthMm=round(max(max(bounds(p)) for p in prototype),8),outerEnvelopeMm=rounded([W+2*t,D+2*t,H+2*t]),
            outerDimensions=rounded([W+2*t,D+2*t,H+2*t]),feetIncludedEnvelopeMm=rounded([W+2*t,D+2*t,H+t+iv('footHeightMm')]),
            envelopeScope='outerEnvelope: guard/metal only. feetIncludedEnvelope: guard/metal/feet, excludes side fastener protrusion.',openingMm=rounded([W-2*(T+iv('guardInnerOverhangMm')),D-2*(T+iv('guardInnerOverhangMm'))]),
            quoteJpy=None,quoteStatus='R6未見積。前回R3の2,264円は異なる寸法の比較基準。')
        variants[key]=dict(label=f'R6 · {t:g} mm',parts=parts,stats=stats,catalog=catalog)
        write_json(target/'manifest.json',dict(revision=PARAM['revision'],model=MODEL_ID,variant=key,units='mm',stats=stats,catalog=catalog,
            enclosureMetalEnvelopeMm=[W,D,H],enclosureMetalThicknessMm=T,notes=['各STLは1部品。qtyはケース1台の必要数。','R6未見積。JLCへ再アップロードして価格を確認する。','ガードの保持方法、接着層、嵌合公差は未確定。']))
        print(f'{MODEL_ID} {key}: {len(parts)} guards / {len(prototype)} prototypes / {volume:.8f} cm3 / max {stats["maxPartLengthMm"]} mm',flush=True)
    return variants


def nonzero_box_overlap(a,b):
    aa=exact_bbox(a);bb=exact_bbox(b)
    return all(min(x1,y1)-max(x0,y0)>1e-6 for x0,x1,y0,y1 in [(aa.xmin,aa.xmax,bb.xmin,bb.xmax),(aa.ymin,aa.ymax,bb.ymin,bb.ymax),(aa.zmin,aa.zmax,bb.zmin,bb.zmax)])


def validate_assembly(common,variants):
    checks=[];candidate_count=0;maximum=0.
    bodies=[p for p in common if p['category'] in ('metal','brackets','feet') or p.get('role') in ('fixer','padder')]
    for key,variant in variants.items():
        group=bodies+variant['parts'];bad=[]
        for i,a in enumerate(group):
            for b in group[i+1:]:
                sa=SHAPES[a['id']];sb=SHAPES[b['id']]
                if not nonzero_box_overlap(sa,sb):continue
                candidate_count+=1;volume=sa.intersect(sb).Volume();maximum=max(maximum,volume)
                if volume>1e-4:bad.append(dict(a=a['id'],b=b['id'],volumeMm3=volume))
        assert not bad,(MODEL_ID,key,bad)
        checks.append(dict(variant=key,partCount=len(group),interferences=bad))
    pcbs=[p for p in common if p.get('role') in ('fixer','padder')]
    bolts=[p for p in common if p.get('role') in ('mountBolt','railEndBolt','panelJointBolt')]
    hardware_errors=[];hardware_checks=0
    for p in bolts:
        for pcb in pcbs:
            a=SHAPES[p['id']];b=SHAPES[pcb['id']]
            if not nonzero_box_overlap(a,b):continue
            hardware_checks+=1;volume=a.intersect(b).Volume()
            if volume>1e-4:hardware_errors.append(dict(a=p['id'],b=pcb['id'],volumeMm3=volume))
    for i,p in enumerate(bolts):
        for q in bolts[i+1:]:
            a=SHAPES[p['id']];b=SHAPES[q['id']]
            if not nonzero_box_overlap(a,b):continue
            hardware_checks+=1;volume=a.intersect(b).Volume()
            if volume>1e-4:hardware_errors.append(dict(a=p['id'],b=q['id'],volumeMm3=volume))
    assert not hardware_errors,(MODEL_ID,'hardware',hardware_errors)
    # Occupancy study: 2.2mm bracket allowance and 12mm rail/bracket head
    # diameter. Keep physical CAD at the user-measured 2.0mm bracket thickness.
    conservative_heads=[]
    for p in common:
        if p.get('role')=='panelJointBolt':
            if p.get('headSide')=='outside':continue
            axis=p['axis'];sign=-1 if axis==2 else (-1 if p['center'][axis]<0 else 1)
            seat=p['headSeatMm']-sign*(iv('bracketAllowanceThicknessMm')-BR_T)
            h=cylinder(axis,seat,seat-sign*iv('mountHeadHeightMm'),p['center'],iv('bracketHeadDiameterMm')/2)
            conservative_heads.append((p['id']+'-allowance',h))
        elif p.get('role')=='railEndBolt':
            sx=-1 if p['center'][0]<0 else 1;seat=sx*FRAME/2;y,z=p['axisCenterYZ']
            h=cylinder(0,seat,seat+sx*iv('railEndHeadHeightMm'),(0,y,z),6)
            conservative_heads.append((p['id']+'-diameter12-study',h))
    conservative_errors=[];rail_head_study_interferences=[];study_pairs=0
    for i,(name,a) in enumerate(conservative_heads):
        for other,b in conservative_heads[i+1:]+[(p['id'],SHAPES[p['id']]) for p in pcbs]:
            if not nonzero_box_overlap(a,b):continue
            study_pairs+=1;volume=a.intersect(b).Volume()
            if volume>1e-4:
                issue=dict(a=name,b=other,volumeMm3=volume)
                if name.startswith('rail-end-bolt') and other.startswith('rail-end-bolt'):rail_head_study_interferences.append(issue)
                else:conservative_errors.append(issue)
    assert not conservative_errors,(MODEL_ID,'conservative heads',conservative_errors)
    VALIDATION['cadInterferenceChecks']=dict(scope='metal / measured-thickness bracket geometry / exact PCB / each guard variant; source rail excluded from BREP tests',results=checks,candidatePairsEvaluated=candidate_count,maxIntersectionVolumeMm3=maximum)
    VALIDATION['hardwareChecks']=dict(scope='all inner bolt heads and shafts against PCB solids and each other; raw rail thread engagement excluded',candidatePairsEvaluated=hardware_checks,interferences=hardware_errors)
    VALIDATION['clearanceAllowanceStudy']=dict(bracketPhysicalThicknessMm=BR_T,bracketOccupiedThicknessMm=iv('bracketAllowanceThicknessMm'),headHeightMm=iv('mountHeadHeightMm'),
        railHeadDiameterStudyMm=12,bracketHeadDiameterStudyMm=iv('bracketHeadDiameterMm'),candidatePairsEvaluated=study_pairs,interferences=conservative_errors,
        railToRailHeadStudyInterferences=rail_head_study_interferences,
        railToRailHeadStudyNote='直径12mmは未測定の追加仮定。7Uの隣接行軸間11.9960175mmで微小重複する。既存組立の実頭径とは区別し、ケース対ブラケットの干渉判定に混同しない。',
        conservativeFacingHeadXGapMm=SP-iv('bracketAllowanceThicknessMm')-iv('mountHeadHeightMm')-iv('railEndHeadHeightMm'),
        conservativeFrontBackPcbGapMm=(D/2-T-UNIT_HALF_DEPTH)-iv('bracketAllowanceThicknessMm')-iv('mountHeadHeightMm'),
        basis='Measured 2mm bracket is represented physically. 2.2mm occupancy adds 0.2mm inward to head seats; end head diameter12 is a conservative study, not measured.')
    bottom_hardware=[p for p in common if p.get('parentPanel')=='metal-bottom']
    bottom_internal=[p for p in bottom_hardware if p.get('role') in ('panelJointNut','panelJointWasher')]
    bottom_others=[p for p in common if p['category']=='brackets' or p.get('role') in ('fixer','padder','foot')]
    bottom_errors=[]
    for p in bottom_internal:
        for q in bottom_others:
            a=SHAPES[p['id']];b=SHAPES[q['id']]
            if nonzero_box_overlap(a,b):
                volume=a.intersect(b).Volume()
                if volume>1e-4:bottom_errors.append(dict(a=p['id'],b=q['id'],volumeMm3=volume))
    for foot in [p for p in common if p.get('role')=='foot']:
        for p in bottom_hardware:
            a=SHAPES[foot['id']];b=SHAPES[p['id']]
            if nonzero_box_overlap(a,b):
                volume=a.intersect(b).Volume()
                if volume>1e-4:bottom_errors.append(dict(a=foot['id'],b=p['id'],volumeMm3=volume))
    assert not bottom_errors,(MODEL_ID,'bottom hardware / feet',bottom_errors)
    VALIDATION['bottomFastenersAndFeet']=dict(headSide='outside',washerNutSide='inside',footCount=4,
        footDiameterMm=iv('footDiameterMm'),footHeightMm=iv('footHeightMm'),footInsetMm=iv('footInsetMm'),
        contactPlaneZMm=-iv('footHeightMm'),bottomHeadLowestZMm=-iv('mountHeadHeightMm'),
        headToContactPlaneGapMm=iv('footHeightMm')-iv('mountHeadHeightMm'),interferences=bottom_errors,
        note='貼付式既製ゴム脚の提案。穴なし。JLCガード数と体積には含めない。')
    VALIDATION['sourceRail']=dict(triangleCount=RAIL_MESH.get('triangleCount',len(RAIL_MESH['indices'])//3),duplicatesPreserved=True,repairApplied=False,
        transformDeterminants={p['id']:float(np.linalg.det(np.array(p['sourceTransform'])[:3,:3])) for p in common if p.get('role')=='rail'},excludedFromBrepExport=True)
    print(f'{MODEL_ID}: CAD and inside-head clearance validation passed',flush=True)


def build_model(model_id):
    configure(model_id)
    common=common_geometry();variants=variants_geometry();validate_assembly(common,variants)
    grip=TF+SP+T+OW;mountcount=2*len(MOUNTS);bracketcount=12+2*MODEL['sideBottomBracketCount'];actual_gap=D/2-T-UNIT_HALF_DEPTH
    derived=dict(railLengthMm=L,railFrameWidthMm=FRAME,railUnitDepthMm=UNIT_HALF_DEPTH*2,enclosureInnerWidthMm=INNER,enclosureMetalEnvelopeMm=[W,D,H],
        minimumDepthFor8mmMm=MINIMUM_D,selectedRoundedDepthMm=D,frontBackInsideClearanceMm=actual_gap,
        fixerTopZMm=TOP,fixerBottomZMm=TOP-PANELS['panels']['fixer']['outer']['bbox']['max'][1],
        mountAxesPerSide=[dict(sourceUV=[m['u'],m['v']],worldYZ=[m['u']-BOARD_Y0,TOP-m['v']],row=m['row']) for m in MOUNTS],
        mountingGripMm=grip,bracketCount=bracketcount,bracketBottomCount=bracketcount-8,
        frontBackBottomBracketXsMm=BOTTOM_XS,leftRightBottomBracketYsMm=BOTTOM_YS,feet=VALIDATION['bottomFastenersAndFeet'],
        positiveXStackMm=dict(railEnd=L/2,padderOuter=L/2+TP,fixerOuter=FRAME/2,innerSpacerOuter=INNER/2,metalOuter=W/2,outerWasherOuter=W/2+OW),
        padderPlacementsPerSide=PADDER_PLACEMENTS,guardVariants={k:v['stats'] for k,v in variants.items()},
        equations=dict(frameWidth='railLength + 2 * (padderThickness + fixerThickness)',enclosureInnerWidth='railFrameWidth + 2 * innerSpacerThickness',
            enclosureMetalWidth='enclosureInnerWidth + 2 * metalThickness',depth='ceil(max registered rail-unit half-depth * 2 + 2 * 8mm + 2 * metalThickness)',
            mountingGrip='fixerThickness + innerSpacerThickness + metalThickness + outerWasherThickness; padder not in the clamped stack'))
    assumptions=[f'ケース高さ{H:g}mm、fixer上端Z{TOP:g}mmを維持。奥行は全ユニット包絡から約8mmの余白を加えて整数mmへ切り上げ。',
        'ブラケット穴中心は内面から10mmの提案位置。実測の穴中心・曲げ形状は未反映。パネルはφ5.5丸穴。',
        'ブラケット実厚2mm、設計占有厚2.2mm。内側の頭厚1.4mmを含めて干渉確認。',
        '底板のみ低頭を外側、座金/ナットを内側へ反転。φ10×3mm貼付ゴム脚4個は未選定の提案。JLCガードとは別部品。',
        'ガードは公称接触すきま0mm、保持方法・嵌合公差・接着層は未設計。',
        'ワッシャー内外径、外側ナット、ねじ軸長は模式表示。必要ねじ長の指定ではない。',
        'レール元STLは重複面を保持。モジュール固定用のスライドナットは省略。',
        'レール端頭φ9は模式表示。φ12追加検証では7U隣接行の頭同士に約0.004mmの径方向包絡重複があり、実頭径の確認事項として別記。']
    roles=dict(Counter(p.get('role','') for p in common))
    meta=dict(title=MODEL['label'],revision=PARAM['revision'],modelId=model_id,hp=MODEL['hp'],layout=MODEL['layout'],units='mm',upAxis='Z',
        metalEnvelopeMm=[W,D,H],metalThicknessMm=T,railLengthMm=L,railCount=len(RAIL_HOLES),railFrameWidthMm=FRAME,railFrameDepthMm=UNIT_HALF_DEPTH*2,railUnitDepthMm=UNIT_HALF_DEPTH*2,
        fixerThicknessMm=TF,padderThicknessMm=TP,fixerCount=2,padderCount=len(PADDER_PLACEMENTS)*2,pcbCount=2+len(PADDER_PLACEMENTS)*2,
        fixerSourceDimensionsUVmm=PANELS['panels']['fixer']['outer']['bbox']['dimensions'],padderPlacementsPerSide=PADDER_PLACEMENTS,
        spacerThicknessMm=SP,spacerCount=mountcount,outerWasherThicknessMm=OW,outerWasherCount=mountcount,
        mountingGripMm=grip,mountingBoltLengthMm=iv('mountBoltLengthMm'),mountingNutHeightMm=iv('lockNutHeightMm'),mountingHardwareDimensionsStatus='schematic / not a fastener procurement specification',
        mountHeadHeightMm=iv('mountHeadHeightMm'),mountHeadHeightUserConfirmed=True,pcbThicknessUserConfirmed=True,bracketPhysicalThicknessMm=BR_T,bracketAllowanceThicknessMm=iv('bracketAllowanceThicknessMm'),
        railFixerTopMm=TOP,railMountZMm=MOUNT_Z,railMountYmm=MOUNT_YS,unitMountHoleCount=mountcount,
        panelCount=5,panelHoleCount=2*bracketcount+mountcount,panelJointHoleCount=2*bracketcount,bracketCount=bracketcount,bottomBracketCount=bracketcount-8,verticalBracketCount=8,
        railUnitLiftMm=155,frontBackInsideClearanceMm=actual_gap,frontBackInnerClearanceMm=actual_gap,frontBackClearanceMm=actual_gap,
        frontBackOpenGapMm=actual_gap-iv('guardInnerOverhangMm'),sideOpeningClearanceMm=SP-iv('guardInnerOverhangMm'),
        conservativeFacingHeadXGapMm=VALIDATION['clearanceAllowanceStudy']['conservativeFacingHeadXGapMm'],footCount=4,footDiameterMm=iv('footDiameterMm'),footHeightMm=iv('footHeightMm'),footInsetMm=iv('footInsetMm'),bottomHeadSide='outside',bottomHeadContactClearanceMm=iv('footHeightMm')-iv('mountHeadHeightMm'),
        nominalValuesFromSource=True,assumptions=assumptions,hardwareCounts=roles,
        status='R6 source-based family, nominal design; bracket hole positions and guard retention not finalized',
        notes=[f'実レール長{L:g}mm、PCB両1.6mm、内側スペーサー8mm、外側ワッシャー1mm、頭厚1.4mm。',
               '全ケースは底＋前後＋左右の5枚構成。7Uも内部仕切り板なし。',
               'ガードは各単体180mm以内の短い部品へ分割。']+assumptions,
        sources=[RAIL_MESH['source'].get('stl_url','')]+[PANELS['panels'][k]['source']['source_url'] for k in [MODEL['fixer']]+list(dict.fromkeys(p['kind'] for p in PADDER_PLACEMENTS))],
        sourceCommits=dict(rail=RAIL_MESH['source'].get('commit'),pcbs=ALL_PANELS['commitSha']))
    # Export BREP geometry; raw input rail mesh and schematic fasteners stay in viewer.
    assembly_parts=[SHAPES[p['id']] for p in common if p['category'] in ('metal','brackets','feet') or p.get('role') in ('fixer','padder')]+[SHAPES[p['id']] for p in variants['t1p2']['parts']]
    cq.exporters.export(cq.Compound.makeCompound(assembly_parts),str(ENGINEERING/f'{MODEL_ID}_r6_t1p2_enclosure_boards_assembly.step'))
    VALIDATION['derived']=derived;VALIDATION['status']='passed';VALIDATION['scopeNotes']=assumptions
    write_json(ENGINEERING/'validation.json',VALIDATION)
    # Stable model prefixes make IDs unambiguous across all three model datasets.
    for part in common+[p for v in variants.values() for p in v['parts']]:
        part['id']=model_id+'-'+part['id']
        if 'parentPanel' in part:part['parentPanel']=model_id+'-'+part['parentPanel']
    return dict(meta=meta,commonParts=common,variants=variants),derived


def main():
    models={};derived={}
    for model_id in PARAM['models']:
        models[model_id],derived[model_id]=build_model(model_id)
        # Checkpoint each finished model so partial regeneration remains inspectable.
        write_json(GLOBAL_ENGINEERING/model_id/'model-summary.json',dict(meta=models[model_id]['meta'],stats={k:v['stats'] for k,v in models[model_id]['variants'].items()}))
    PARAM['derived']=derived;write_json(PARAM_FILE,PARAM)
    data=dict(defaultModel=PARAM['defaultModel'],revision=PARAM['revision'],models=models)
    out=ROOT/'mesh-data.js';out.write_text('/* Generated by build_geometry.py; millimetres, Z up. */\nwindow.ZUDO_CASE_FAMILY = '+json.dumps(data,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')
    summary={k:dict(metalEnvelopeMm=v['meta']['metalEnvelopeMm'],commonParts=len(v['commonParts']),rails=v['meta']['railCount'],brackets=v['meta']['bracketCount'],mountCount=v['meta']['unitMountHoleCount'],panelHoles=v['meta']['panelHoleCount'],variants={a:b['stats'] for a,b in v['variants'].items()}) for k,v in models.items()}
    write_json(GLOBAL_ENGINEERING/'family-summary.json',summary)
    print(json.dumps(dict(file=str(out),bytes=out.stat().st_size,models=summary),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
