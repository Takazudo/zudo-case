"""7U40 R11 body: screw-centred lap joints and nylon panel locating walls.

Geometry in assembly coordinates, millimetres. Original R10 inputs are read-only.
"""
import math
from collections import defaultdict
import cadquery as cq
from .core import *

JX=P['joint_stations']['front_back_x'][1]
JY=P['joint_stations']['side_y'][1]
ZS=[36.5,P['hardware']['upper_corner_axis_z']]
MOUNT_Z=68.1894265
MOUNT_Y=[u-157.377228 for u in [22.8453565,90.111288,157.37722,224.6431425,291.873764]]
LENGTH=P['slots']['new_length']; SW=P['slots']['width']
EDGE_GAP=P['locators']['panel_edge_gap']

def stations(f):
    if f in ('front','back'):return [-JX,JX]
    return [-JY,0.,JY] if P['joint_stations']['side_existing_center_retained'] else [-JY,JY]
def jstation(f):return JX if f in ('front','back') else JY
def width(f):return W if f in ('front','back') else D

def corner_key(f,sign):
    return {'front':(sign,-1),'back':(-sign,1),'right':(1,sign),'left':(-1,-sign)}[f]

def hole(f,u,v,ang,kind,status='retained',inward=None):
    if ang is None:du=dv=0
    elif inward is not None:du,dv=inward
    elif kind=='corner':du,dv=-math.copysign(1,u),0
    elif kind=='upper':du,dv=0,-1
    elif f=='floor':
        du,dv=(-math.copysign(1,u),0) if ang==0 else (0,-math.copysign(1,v))
    else:du,dv=0,1
    uc,vc=u+2.5*du,v+2.5*dv
    return dict(face=f,u=u,v=v,uc=uc,vc=vc,angle=ang,kind=kind,status=status,
                length=None if ang is None else LENGTH,width=SW,
                inward=[du,dv],old_length=None if ang is None else 10.5,
                near_end_preserved=ang is not None)

def panel_rows(f):
    if f=='floor':
        rows=[hole(f,x,sy*(YM-10),90,'floor-front') for sy in (-1,1) for x in (-JX,JX)]
        rows += [hole(f,sx*(XM-10),y,0,'floor-side','relocated' if y else 'retained') for sx in (-1,1) for y in stations('right')]
    else:
        short=f in ('front','back')
        rows=[hole(f,u,11.5,90,'lower','relocated' if not short and u else 'retained') for u in stations(f)]
        rows += [hole(f,u,80.,90,'upper','new') for u in (-jstation(f),jstation(f))]
        edge=XM-10 if short else YM-10
        rows += [hole(f,s*edge,z,0,'corner','relocated' if z>60 else 'retained') for z in ZS for s in (-1,1)]
        if not short:rows += [hole(f,a if f=='right' else -a,MOUNT_Z,None,'rail') for a in MOUNT_Y]
    # R11-03 retains the R11-02 sheet profiles without dedicated hanging holes.
    # The ten original round rail
    # mounting holes remain; anodizing fixtures for slot-only sheets are unconfirmed.
    for k,r in enumerate(rows):r['id']=f'{f}-{k}'
    return rows

def panel_blank(f,clearance=False):
    c=.1 if clearance else 0
    if f=='floor':return box(-W/2-c,W/2+c,-D/2-c,D/2+c,-T,0)
    a=(XM-EDGE_GAP) if f in ('front','back') else D/2
    return box(-a-c,a+c,T+EDGE_GAP-c,H,-T-c,c)

def panel_shape(f):
    s=panel_blank(f)
    for r in panel_rows(f):
        cut=disk(r['uc'],r['vc'],-T-1,1,r['width']/2) if r['angle'] is None else slot(r['uc'],r['vc'],LENGTH,SW,-T-1,1,r['angle'])
        s=s.cut(cut)
    return s.clean()

def profile(f,kind):
    a=width(f)/2+1.1
    if kind=='top':
        ss=[box(-a,a,H-5,H,.1,1.1),box(-a,a,H-5,H,-2.6,-1.6),box(-a,a,H,H+1,-2.6,1.1)]
    else:
        ss=[box(-a,a,-1,5,.1,1.1),box(-a,a,-1,0,-7.5,1.1),
            box(-a,a,T+.1,T+.9,-2.6,1.1),box(-a,a,T+.1,T+EDGE_GAP+4,-2.6,-1.6)]
    s=fuse(ss)
    j=jstation(f)
    for sign in (-1,1):
        u=sign*j
        s=s.cut(box(u-10,u+10,-3,H+2,0,4))
        if kind=='bottom':s=s.cut(box(u-10,u+10,-3,0,-30,4))
        else:s=s.cut(box(u-10,u+10,64,H,-3,0))
    if kind=='bottom':
        # Reserve each inner seat for the central span's continuous L cheek.
        # The nearby corner channel stops 0.1 mm before that cheek, so separate
        # printed pieces do not overlap. The span has its own inward root.
        for u in stations(f):s=s.cut(box(u-8.2,u+8.2,T+.9,30,-25,-1.5))
        for u in stations(f):s=s.cut(box(u-10.1,u+10.1,T,30,-31,-1.5))
    return s.clean()

def wall_pad(u,kind,n0,n1):
    lo,hi=(-1,28) if kind=='bottom' else (64,H+1)
    s=rr(u-10,u+10,lo,hi,n0,n1,1.5)
    vc=14 if kind=='bottom' else 77.5
    return s.cut(slot(u,vc,LENGTH,SW,n0-1,n1+1,90)).clean()

def floor_pad(u,v0,v1):
    outside=1 if v0==-1 else 2
    s=cq.Workplane('XY').newObject([box(u-10,u+10,v0,v1,-28,outside)]).edges('|Y').fillet(1.5).val()
    cutter=slot(u,-14,LENGTH,SW,-v1-1,-v0+1,90).rotate((0,0,0),(1,0,0),90)
    return s.cut(cutter).clean()

def top_inner(u):
    # Preserve the existing top ear and its loose inside load-spreading washer.
    # Here the nut has no metal bracket: removing that washer would make the
    # AF8 nut bear directly on the long nylon slot with much less contact area.
    s=rr(u-10,u+10,64,H,-2.5,-1.5,1.5)
    return s.cut(slot(u,77.5,LENGTH,SW,-4,0,90)).clean()

def lower_inner(u):
    """One integral inner L cheek: wall and floor, each t1, under the bracket."""
    wall=rr(u-10,u+10,T,28,-2.5,-1.5,1.5)
    wall=wall.cut(slot(u,14,LENGTH,SW,-3.5,-.5,90))
    floor=floor_pad(u,T,T+1).intersect(box(u-11,u+11,T,T+1,-29,-1.5))
    return fuse([wall,floor])

def body_nylon():
    corner=defaultdict(list);spans=[]
    metal_clear=[world(panel_blank(f,True),f) for f in FACES]
    for f in ('front','back','right','left'):
        j=jstation(f);a=width(f)/2+1.1
        for kind in ('top','bottom'):
            base=profile(f,kind)
            pieces=[]
            for sign in (-1,0,1):
                u0,u1=(-a,-j-.1) if sign<0 else (-j+.1,j-.1) if sign==0 else (j+.1,a)
                s=base.intersect(box(u0,u1,-3,H+3,-31,5)).clean()
                if sign:
                    u=sign*j
                    ss=[s,wall_pad(u,kind,0,1)]
                    if kind=='bottom':ss.append(floor_pad(u,-1,0))
                else:
                    ss=[s]
                    for sg in (-1,1):
                        u=sg*j;ua,ub=sorted((sg*(j-12),sg*(j-10)))
                        ss.append(wall_pad(u,kind,1,2))
                        if kind=='top':
                            ss += [box(ua,ub,H-5,H+1,.1,2),top_inner(u)]
                        else:
                            inner_a,inner_b=sorted((sg*(j-12),sg*(j-9)))
                            ss += [box(ua,ub,-1,5,.1,2),floor_pad(u,-2,-1),box(ua,ub,-2,0,-7.5,1.1),
                                   lower_inner(u),box(inner_a,inner_b,T+.1,T+EDGE_GAP+4,-2.6,-1.5)]
                    if kind=='bottom' and f in ('left','right') and P['joint_stations']['side_existing_center_retained']:
                        ss += [wall_pad(0,kind,0,2),floor_pad(0,-2,0)]
                s=fuse(ss)
                s=world(s,f)
                # Trim only the base channel where neighbouring sheet faces meet.
                # Pressure ears remain on the panel boundary (normal=0).
                for m in metal_clear:
                    # Only opposite-face clearances are needed; own-face ears
                    # contact the panel rather than sitting across an air gap.
                    if m is metal_clear[list(FACES).index(f)]:continue
                    s=s.cut(m)
                s=s.clean()
                if sign:corner[corner_key(f,sign)].append(s)
                else:
                    spans.append(part(f'body-{kind}-{f}',s,FACES[f][4]+(' 上辺中央' if kind=='top' else ' 下辺中央'),'span',
                        note='ネジ位置で1＋1mmの外側重ね耳。'+('従来の内側耳と丸ワッシャーを維持。上端だけはナットの面圧を分散する座金を残す。' if kind=='top' else '壁と底面に一体の内側L字耳。各1mmで従来の内側丸ワッシャーを置換。'),
                        explode=normal_explode(f,1.2),face=f,kind=kind))
    # Four complete corners: one solid includes top arms, lower arms and spine.
    for sx in (-1,1):
        for sy in (-1,1):
            xx=sorted((sx*(W/2+.1),sx*(W/2+1.1)))
            yy=sorted((sy*(D/2+.1),sy*(D/2+1.1)))
            ix=sorted((sx*(W/2-5),sx*(W/2+1.1)))
            iy=sorted((sy*(D/2-5),sy*(D/2+1.1)))
            ss=corner[(sx,sy)]+[box(*xx,*iy,-1,H+1),box(*ix,*yy,-1,H+1)]
            # Thin vertical separator occupies the new 1mm gap between sheets.
            rx=sorted((sx*(XM-.9),sx*(XM-.1)))
            ry=sorted((sy*(D/2+1.1),sy*(YM-2)))
            ss.append(box(*rx,*ry,T+.9,H+1))
            for f in ('right' if sx>0 else 'left','back' if sy>0 else 'front'):
                for r in panel_rows(f):
                    if r['kind']!='corner':continue
                    pt=worldpoint(f,r['u'],r['v'])
                    if pt[0]*sx<0 or pt[1]*sy<0:continue
                    # t2 outer pad at the upper corner is reserved for a compact
                    # hardware stack beside the original removable rail frame.
                    thick=2
                    half=P['hardware']['corner_pad_width']/2
                    pad=rr(r['uc']-half,r['uc']+half,r['vc']-9,r['vc']+9,0,thick,1.5)
                    pad=pad.cut(slot(r['uc'],r['vc'],LENGTH,SW,-1,thick+1,0))
                    ss.append(world(pad,f))
                    # A matching t1 inner pad replaces the washer layer under
                    # the L bracket. Its corner end meets the existing vertical
                    # nylon return, so it is part of this one corner solid.
                    inner=rr(r['uc']-half,r['uc']+half,r['vc']-9,r['vc']+9,-2.5,-1.5,1.5)
                    inner=inner.cut(slot(r['uc'],r['vc'],LENGTH,SW,-3.5,-.5,0))
                    ss.append(world(inner,f))
                    # Explicit corner-side neck into the full separator width.
                    # Keep the opposite, rail-facing end of the pad unchanged.
                    edge=XM if f in ('front','back') else YM
                    sg=math.copysign(1,r['u']);na,nb=sorted((sg*(edge-1.5),sg*edge))
                    ss.append(world(box(na,nb,r['vc']-9,r['vc']+9,-2.5,-1.5),f))
            s=fuse(ss)
            # Cut only sheet end clearances; the geometry never fills metal volume.
            for f in FACES:s=s.cut(world(panel_blank(f),f))
            s=s.clean()
            spans.append(part(f'body-corner-{sx}-{sy}',s,f'一体コーナー {sx:+}/{sy:+}','corner',
                         note='上下の腕・縦ガード・位置決め壁・内側の固定耳を一体化。縦角は外側t2＋内側t1。内側丸ワッシャー不要。',
                         explode=[sx*1.2,sy*1.2,0],sx=sx,sy=sy))
    return spans

def bracket_items():
    out=[]
    for f in ('front','back','right','left'):
        for k,u in enumerate(stations(f)):
            v=T+1;n=-T-1
            s=fuse([box(u-8,u+8,v,v+20,n-2,n),box(u-8,u+8,v,v+2,n-20,n)])
            s=s.cut(disk(u,v+10,n-3,n+1,2.75))
            s=s.cut(cq.Solid.makeCylinder(2.75,4,cq.Vector(u,v-1,n-10),cq.Vector(0,1,0)))
            out.append(part(f'bracket-{f}-{k}',world(s.clean(),f),'補強L金具 20×20×16 / t2','brackets','bracket',
                            note='既存在庫形状。穴中心10mmは従来の仮定。側面の外側2箇所を±95mmへ移設。',explode=normal_explode(f,.4)))
    for sx in (-1,1):
        for sy in (-1,1):
            xx=sx*(XM-1);yy=sy*(YM-1)
            for k,z in enumerate(ZS):
                xa,xb=sorted((xx,xx-sx*20));ya,yb=sorted((yy,yy-sy*2))
                xc,xd=sorted((xx,xx-sx*2));yc,yd=sorted((yy,yy-sy*20))
                s=fuse([box(xa,xb,ya,yb,z-8,z+8),box(xc,xd,yc,yd,z-8,z+8)])
                s=s.cut(cq.Solid.makeCylinder(2.75,24,cq.Vector(xx-sx*10,yy-12,z),cq.Vector(0,1,0)))
                s=s.cut(cq.Solid.makeCylinder(2.75,24,cq.Vector(xx-12,yy-sy*10,z),cq.Vector(1,0,0)))
                out.append(part(f'bracket-corner-{sx}-{sy}-{k}',s.clean(),'縦角の補強L金具','brackets','bracket'))
    return out

def body_fasteners():
    out=[];stacks=[]
    for f in FACES:
        for r in panel_rows(f):
            kind=r['kind']
            if kind=='rail':continue
            u,v=r['u'],r['v']
            if kind=='corner':u-=math.copysign(1,u)
            elif kind=='lower':v+=1
            elif kind=='upper':v=r['vc']
            elif f=='floor':
                if r['angle']==0:u-=math.copysign(1,u)
                else:v-=math.copysign(1,v)
            upper=kind=='upper';corner=kind=='corner'
            ear=2
            nut_h=P['hardware']['thin_nut_height'] if f=='floor' or corner and f in ('front','back') else P['hardware']['nut_height']
            length=12
            inner_seat=-3.5 if upper else -4.5
            # At bracketed sites, the old inner washer is integral with its
            # nylon connector. The eight top sites retain their inside washers.
            # No retained bracket, screw, nut or outside washer moves.
            items=[('washer-out',roundwasher(u,v,ear,ear+1),'外側丸ワッシャー Ø15 / Ø5 / t1','washer','washer'),
                   ('head',head(u,v,ear+1,ear+2.4),'外側M5ねじ頭','hardware','fastener'),
                   ('shaft',disk(u,v,ear+1-length,ear+1,2.5),'M5ねじ軸','hardware','fastener'),
                   ('nut',hexprism(u,v,inner_seat-nut_h,inner_seat,8,30 if corner else 0,2.5),f'内側M5ナット / h{nut_h:g}候補','hardware','fastener')]
            if upper:items.append(('washer-in',roundwasher(u,v,-3.5,-2.5),'上端の内側丸ワッシャー Ø15 / Ø5 / t1','washer','washer'))
            for tag,s,name,cat,role in items:
                multiplier=1.5 if tag in ('head','washer-out') else -.7 if tag in ('nut','washer-in') else 0
                out.append(part(f'{tag}-{r["id"]}',world(s,f),name,cat,role,
                    note=f'{FACES[f][4]} / {kind}。M5×{length}、ナット高さ{nut_h}mmは形状確認用。ナットはケース内側。',
                    explode=normal_explode(f,multiplier),face=f,kind=kind,fastener_site=r['id']))
            if upper:inner_owner='body-top-'+f
            elif kind=='lower':inner_owner='body-bottom-'+f
            elif f=='floor':
                edge_face=('front' if r['v']>0 else 'back') if kind=='floor-front' else ('right' if r['u']>0 else 'left')
                inner_owner='body-bottom-'+edge_face
            else:
                xyz=worldpoint(f,r['u'],r['v']);sx=1 if xyz[0]>0 else -1;sy=1 if xyz[1]>0 else -1
                inner_owner=f'body-corner-{sx}-{sy}'
            stacks.append(dict(id=r['id'],face=f,kind=kind,bolt_axis_uv=[u,v],
                axis_xyz=worldpoint(f,u,v),ear_mm=ear,bearing_n=ear+1,length_mm=length,
                inner_nut_n=[inner_seat-nut_h,inner_seat],nut_height_mm=nut_h,
                projection_mm=inner_seat-nut_h-(ear+1-length),nut_side='inside',
                inner_ear_owner=inner_owner,inner_ear_n=[-2.5,-1.5],
                inner_ear_thickness_mm=1.0,inner_washer_replaced=not upper))
    return out,stacks

def build_body():
    out=[]
    for f in FACES:
        out.append(part('panel-'+f,world(panel_shape(f),f),FACES[f][4]+' / A5052 t1.5','panels','metal',
                        note='全長穴を5mm内側へ延長。'+('前後板幅224.4mm／壁下端Z2.5mm。' if f in ('front','back') else '外形維持。壁下端Z2.5mm。' if f!='floor' else '外形229.4×334mmを維持。左右の外側穴を新しい接合位置へ移設。'),
                        explode=normal_explode(f,1.8),face=f))
    out += body_nylon()
    out += bracket_items()
    fasteners,stacks=body_fasteners();out+=fasteners
    for sx in (-1,1):
        for sy in (-1,1):
            s=disk(sx*(W/2-20),sy*(D/2-20),-6,0,5)
            out.append(part(f'foot-{sx}-{sy}',s,'仮ゴム脚 h6mm','guide','foot',note='底面重ね耳2＋座金1＋低頭1.4mmを避ける高さ6mmの仮設定。',explode=[0,0,-1]))
    removed_center_slots=[]
    if not P['joint_stations']['side_existing_center_retained']:
        removed_center_slots=[hole(f,0.,11.5,90,'lower','removed') for f in ('left','right')]
        removed_center_slots += [hole('floor',sx*(XM-10),0.,0,'floor-side','removed') for sx in (-1,1)]
    removed_hanging_holes=[dict(face=f,uv=list(uv),diameter_mm=4.0)
                           for f,uv in {'floor':(0,0),'front':(0,45),'back':(0,45),'left':(65,26),'right':(65,26)}.items()]
    meta=dict(hole_table=[r for f in FACES for r in panel_rows(f)],hardware_stacks=stacks,
              nylon_parts=12,body_fastener_sites=len(stacks),panel_edge_gap_mm=1,separator_mm=.8,
              inner_ear_sites=len(stacks),integrated_inner_washer_replacements=sum(r['inner_washer_replaced'] for r in stacks),
              removed_side_slots=[dict(face=f,u=s*126.5,v=11.5) for f in ('left','right') for s in(-1,1)],
              removed_center_slots=removed_center_slots,removed_hanging_holes=removed_hanging_holes,
              dedicated_hanging_hole_count=0,side_lower_clamp_spacing_mm=2*JY,
              side_center_locating_fences_restored=not P['joint_stations']['side_existing_center_retained'],
              panel_dimensions=dict(floor=[W,D,T],front_back=[W-2*T-2*EDGE_GAP,H-T-EDGE_GAP,T],side=[D,H-T-EDGE_GAP,T]))
    return out,meta
