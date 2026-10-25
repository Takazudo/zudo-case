"""R10 port of accepted R2 guard/joint topology. See reference receipt.
Runtime dimensions and source hole datums are configured by build.py.
"""
import cadquery as cq
import math, json, hashlib
from pathlib import Path

OUT=Path(__file__).resolve().parents[1]
W,D,H,T=229.4,334.,91.,1.5
XM,YM=W/2-T,D/2-T
XS=[-(XM-53.7), XM-53.7]
YS=[-(D/2-40.5),0.,D/2-40.5]
ZS=[36.5,66.5]
MOUNT_Z=68.1894265
# Source fixer7u normalized centre is 157.377228 (saved source placements).
MOUNT_Y=[u-157.377228 for u in [22.8453565,90.111288,157.37722,224.6431425,291.873764]]
FACES={
 'front':((0,-D/2,0),(1,0,0),(0,0,1),(0,-1,0),'前板'),
 'back':((0,D/2,0),(-1,0,0),(0,0,1),(0,1,0),'後板'),
 'right':((W/2,0,0),(0,1,0),(0,0,1),(1,0,0),'右側板'),
 'left':((-W/2,0,0),(0,-1,0),(0,0,1),(-1,0,0),'左側板'),
 'floor':((0,0,0),(1,0,0),(0,-1,0),(0,0,-1),'底板'),
}
meshes={}; scenes={}; audits=[]; solids={}
# G2: only the wall-side exterior caps change. Pads, slots, guard ears,
# the two 1 mm central lap layers and internal/floor washers remain G1.
CAPS = {
 'corner': dict(length=16., width=12., radius=1.5, eccentricity=0.),
 'lower': dict(length=16., width=14., radius=1.5, eccentricity=1.),
}


def box(x0,x1,y0,y1,z0,z1):
 return cq.Solid.makeBox(x1-x0,y1-y0,z1-z0,cq.Vector(x0,y0,z0))
def fuse(items):
 s=items[0]
 for a in items[1:]: s=s.fuse(a)
 return s.clean()
def slot(u,v,length,width,z0,z1,ang=0):
 return cq.Workplane('XY',origin=(u,v,z0)).slot2D(length,width,ang).extrude(z1-z0).val()
def rr(u0,u1,v0,v1,n0,n1,r=1.5):
 s=cq.Workplane('XY').box(u1-u0,v1-v0,n1-n0,centered=(True,True,False))
 s=s.edges('|Z').fillet(min(r,(u1-u0)/2-.01,(v1-v0)/2-.01)).val()
 return s.translate(((u0+u1)/2,(v0+v1)/2,n0))
def disk(u,v,n0,n1,r,ri=0):
 s=cq.Solid.makeCylinder(r,n1-n0,cq.Vector(u,v,n0))
 return s.cut(cq.Solid.makeCylinder(ri,n1-n0+2,cq.Vector(u,v,n0-1))) if ri else s

def world(s,f):
 o,u,v,n,_=FACES[f]
 m=cq.Matrix([[u[0],v[0],n[0],o[0]],[u[1],v[1],n[1],o[1]],[u[2],v[2],n[2],o[2]],[0,0,0,1]])
 return s.moved(cq.Plane(origin=o,xDir=u,normal=n).location)
def worldpoint(f,u,v,n):
 o,a,b,c,_=FACES[f]
 return [o[k]+a[k]*u+b[k]*v+c[k]*n for k in range(3)]
def extrude_poly(points,n0,n1):
 w=cq.Wire.makePolygon([cq.Vector(u,v,n0) for u,v in points],close=True)
 return cq.Solid.extrudeLinear(w,[],cq.Vector(0,0,n1-n0))
def roundwasher(u,v,n0,n1):return disk(u,v,n0,n1,5,2.75)
def coverwasher(u,v,n0,n1,ang=0):
 s=slot(u,v,20,12,n0,n1,ang)
 return s.cut(disk(u,v,n0-1,n1+1,2.75)).clean()
def outer_cap(u,v,n0,n1,kind='corner',outline_only=False):
 """Manufacturable, constant outline; hole is not resized/clipped as it moves.

 Corner: long axis U, centred round hole. Lower: long axis V; the body
 centre is 1 mm further inward/upward than the round hole. G1 ears stay put.
 """
 c=CAPS[kind]
 if kind=='corner':
  s=rr(u-c['length']/2,u+c['length']/2,v-c['width']/2,v+c['width']/2,n0,n1,c['radius'])
 else:
  vc=v+c['eccentricity']
  s=rr(u-c['width']/2,u+c['width']/2,vc-c['length']/2,vc+c['length']/2,n0,n1,c['radius'])
 return s if outline_only else s.cut(disk(u,v,n0-1,n1+1,2.75)).clean()

def cap_note(kind):
 if kind=='corner':
  return 'G2：角丸長方形16×12×1mm、中央の丸穴φ5.5。元の20×14mm固定耳内に収まる。初期ネジ位置での確認。'
 return 'G2：角丸長方形14×16×1mm、丸穴φ5.5。外形中心をネジ軸より内側へ1mmずらす偏心穴。中央16×18mm耳内に収まる。初期ネジ位置での確認。'

def cap_pad_check(f,k,orig,bolt,kind):
 """Projected containment and full-slot silhouette coverage, not a strength test."""
 ou,ov=orig;u,v=bolt
 if kind=='corner':
  pad=rr(ou-10,ou+10,ov-7,ov+7,0,1,2)
  opening=slot(ou,ov,10.5,5.5,0,1,0)
 else:
  bottom=5 if f in ('left','right') and abs(ou)<.1 else 4.5
  pad=rr(ou-8,ou+8,bottom,23,0,1,1.5 if bottom==5 else 2)
  opening=slot(ou,ov,10.5,5.5,0,1,90)
 cap=outer_cap(u,v,0,1,kind,True)
 over=cap.cut(pad).Volume()
 uncovered=opening.cut(cap).Volume()
 audits.append(dict(check='G2 wall cap stays within original rounded pad',part=f'{f}-{k}',
                    type=kind,outside_mm3=over,uncovered_slot_outline_mm3=uncovered,
                    passed=over<1e-7 and uncovered<1e-7))

def nut(u,v,n0,n1):
 p=[(u+8/math.sqrt(3)*math.cos(k*math.pi/3),v+8/math.sqrt(3)*math.sin(k*math.pi/3)) for k in range(6)]
 return extrude_poly(p,n0,n1).cut(disk(u,v,n0-1,n1+1,2.5)).clean()
def head(u,v,n0,n1):
 s=disk(u,v,n0,n1,6)
 # A shallow hex socket, purely indicative, does not specify a purchased bolt.
 pts=[(u+2.3*math.cos(k*math.pi/3),v+2.3*math.sin(k*math.pi/3)) for k in range(6)]
 return s.cut(extrude_poly(pts,n0-.1,n0+.7)).clean()

def mesh(s):
 verts,tris=s.tessellate(.06,.22)
 p=[round(q,5) for a in verts for q in a.toTuple()]
 inds=[int(a) for tr in tris for a in tr]
 dat={'p':p,'i':inds}
 key=hashlib.sha1(json.dumps(dat,separators=(',',':')).encode()).hexdigest()[:14]
 if key not in meshes:meshes[key]=dat
 return key

def add(items,s,id,name,cat,f=None,note='',explode=None,role='',material='',group=None):
 if f:s=world(s,f)
 solids[id]=s
 if not s.isValid():raise ValueError('Invalid '+id)
 bb=s.BoundingBox()
 o={'id':id,'name':name,'cat':cat,'mesh':mesh(s),'box':[bb.xmin,bb.ymin,bb.zmin,bb.xmax,bb.ymax,bb.zmax],
 'note':note,'material':material,'role':role,'group':group or id,'volume':round(s.Volume(),3),'solids':len(s.Solids()),
 'explode':explode or [0,0,0]}
 items.append(o)
 return s,o

def face_ex(f,scale):return [a*scale for a in FACES[f][3]]

def panel_holes(f):
 if f=='floor':
  return [(x, -sy*(YM-10),90,'floor-front') for sy in(-1,1) for x in XS]+[(sx*(XM-10),-y,0,'floor-side') for sx in(-1,1) for y in YS]
 if f in ('front','back'):
  return [(x,T+10,90,'lower') for x in XS]+[(s*(XM-10),z,0,'corner') for z in ZS for s in(-1,1)]
 return [(y,T+10,90,'lower') for y in YS]+[(s*(YM-10),z,0,'corner') for z in ZS for s in(-1,1)]+[(a if f=='right' else -a,MOUNT_Z,None,'rail') for a in MOUNT_Y]

def panel(f,L):
 if f=='floor':s=box(-W/2,W/2,-D/2,D/2,-T,0)
 elif f in ('front','back'):s=box(-XM,XM,T,H,-T,0)
 else:s=box(-D/2,D/2,T,H,-T,0)
 for u,v,a,r in panel_holes(f):s=s.cut(disk(u,v,-T-1,1,2.75) if a is None else slot(u,v,L,5.5,-T-1,1,a))
 return s.clean()

def guard_upper(wall,q):
 ox,oy=W/2+q+wall,D/2+q+wall;ex,ey=W/2+q,D/2+q
 ix,iy=W/2-T-q,D/2-T-q;ax,ay=ix-wall,iy-wall
 def ring(x,y,xx,yy,z0,z1):return box(-x,x,-y,y,z0,z1).cut(box(-xx,xx,-yy,yy,z0-1,z1+1))
 return fuse([ring(ox,oy,ex,ey,H-5,H),ring(ix,iy,ax,ay,H-5,H),ring(ox,oy,ax,ay,H,H+wall)])

def lower_local(f,half,wall,new):
 # W = x dimension / D = y dimension. New lower guards touch exterior metal.
 A=W/2 if f in ('front','back') else D/2-5.25
 u0,u1=(-A,-.25) if half==0 else (.25,A)
 q=0 if new else .3
 s=fuse([box(u0,u1,0,5,q,q+wall),box(u0,u1,-wall,0,-5,q+wall)])
 if not new:return s
 rows=[(u,v,a) for u,v,a,r in panel_holes(f) if r=='lower' and (u<0 if half==0 else u>0)]
 for u,v,a in rows:
  p=rr(u-8,u+8,4.5,23,0,1,2)
  s=s.fuse(p)
 # Central side joint: two closed slotted ears, separated normally by exactly 1 mm.
 if f in ('right','left'):
  p=rr(-8,8,5,23,0 if half==0 else 1,1 if half==0 else 2,1.5)
  # An attached neck outside the overlap footprint; outer neck is a joggle.
  if half==0: neck=box(-12,-6,3,9,0,1)
  else:
   # profile in u/n, extruded along v. Offset is 1mm, not an unsupported floating ear.
   s=s.cut(box(.24,8.01,4.9,5.01,-.01,1.001)).clean() # Remove zero-thickness ear/strip pinch.
   neck=box(8,12,3,9,0,2) # Local stepped web: t2, both ears remain t1.

  s=fuse([s,p,neck])
  rows.append((0,T+10,90))
 for u,v,a in rows:s=s.cut(slot(u,v,10.5,5.5,-1,4,a))
 s=s.clean()
 if len(s.Solids())!=1:raise ValueError(f'disconnected lower {f}/{half}: {len(s.Solids())}')
 return s

def corner_guard(sx,sy,wall,new):
 # Entire corner guard including two wings uses one solid.
 q=0 if new else .3
 x,y=sx*W/2,sy*D/2
 xx=sorted((x+sx*q,x+sx*(q+wall))); yy=sorted((y+sy*q,y+sy*(q+wall)))
 innerx=sorted((x-sx*5,x+sx*(q+wall))); innery=sorted((y-sy*5,y+sy*(q+wall)))
 parts=[box(xx[0],xx[1],innery[0],innery[1],5.25,H-5.25),box(innerx[0],innerx[1],yy[0],yy[1],5.25,H-5.25)]
 if new:
  for f in (('right' if sx>0 else 'left'),('back' if sy>0 else 'front')):
   for u,v,a,r in panel_holes(f):
    if r!='corner':continue
    c=worldpoint(f,u,v,0)
    if (c[0]*sx<=0 or c[1]*sy<=0):continue
    # Original G1 20 x 14 rounded pad; unchanged in G2.
    p=rr(u-10,u+10,v-7,v+7,0,1,2)
    p=p.cut(slot(u,v,10.5,5.5,-1,2,0)).clean()
    parts.append(world(p,f))
 s=fuse(parts)
 if len(s.Solids())!=1:raise ValueError('disconnected corner')
 return s

def bracket_shapes(shim):
 out=[]
 # Reconstruct all 18 source bracket placements; shift inward by shim on both mating faces.
 for f in ('front','back','right','left'):
  pts=XS if f in ('front','back') else YS
  for k,u in enumerate(pts):
   v=T+shim;n=-T-shim
   s=fuse([box(u-8,u+8,v,v+20,n-2,n),box(u-8,u+8,v,v+2,n-20,n)])
   s=s.cut(disk(u,v+10,n-3,n+1,2.75))
   cut=cq.Solid.makeCylinder(2.75,4,cq.Vector(u,v-1,n-10),cq.Vector(0,1,0))
   s=s.cut(cut).clean()
   out.append((world(s,f),f'bracket-{f}-{k}',f,worldpoint(f,u,v,n)))
 for sx in(-1,1):
  for sy in(-1,1):
   xx=sx*(XM-shim);yy=sy*(YM-shim)
   for k,z in enumerate(ZS):
    xa,xb=sorted((xx,xx-sx*20));ya,yb=sorted((yy,yy-sy*2));xc,xd=sorted((xx,xx-sx*2));yc,yd=sorted((yy,yy-sy*20))
    s=fuse([box(xa,xb,ya,yb,z-8,z+8),box(xc,xd,yc,yd,z-8,z+8)])
    s=s.cut(cq.Solid.makeCylinder(2.75,24,cq.Vector(xx-sx*10,yy-12,z),cq.Vector(0,1,0)))
    s=s.cut(cq.Solid.makeCylinder(2.75,24,cq.Vector(xx-12,yy-sy*10,z),cq.Vector(1,0,0))).clean()
    out.append((s,f'bracket-corner-{sx}-{sy}-{k}','corner',(xx,yy,z)))
 return out

def build_case(new=True,wall=1):
 items=[]; prefix='new' if new else 'old';sh=1 if new else 0;L=10.5 if new else 7.5
 shapes={}
 for f in FACES:
  s,o=add(items,panel(f,L),'panel-'+f,FACES[f][4]+' · A5052 t1.5','panels',f,note=f'接合穴 {5.5} × {L}mm。レール固定10穴はφ5.5のまま。',explode=face_ex(f,1),material='黒アルマイト・アルミ',role='panel')
  shapes[o['id']]=s
 for s,id,f,c in bracket_shapes(sh):
  ex=[0,0,0] # kept in assembly datum so added separation reads as hardware/panel layers
  add(items,s,id,'L字ブラケット · 20×20×16 / t2','brackets',note='元穴中心10mmは仮定。新案は各接触面から1mm離す。',explode=ex,material='金属（公称形状）',role='bracket')
 # Guard top: tighten groove for new study. Alternative groove templates generated separately.
 top=guard_upper(wall if new else 1.2,.1 if new else .3)
 for ix,sx in enumerate((-1,1)):
  for iy,sy in enumerate((-1,1)):
   clip=box(-1000 if sx<0 else .25,-.25 if sx<0 else 1000,-1000 if sy<0 else .25,-.25 if sy<0 else 1000,70,100)
   s=top.intersect(clip).clean()
   add(items,s,f'top-{ix}-{iy}','上端Uガード · '+('溝1.70mm' if new else '溝2.10mm'),'top',note='上面接着層なし。板厚に対する溝幅を縮小した試験候補。',explode=[sx*1.3,sy*1.3,.5],material='PA12候補',role='guard')
 for sx in(-1,1):
  for sy in(-1,1):
   s=corner_guard(sx,sy,wall,new)
   add(items,s,f'corner-{sx}-{sy}','縦辺ガード'+('＋固定耳4箇所' if new else '（接着保持）'),'guardA',note='外周は薄く、締付耳は1mm。耳の長穴がパネルの調整方向に追従。',explode=[sx*1.4,sy*1.4,0],material='PA12候補',role='guard')
 for f in ('front','back','right','left'):
  for h in (0,1):
   s=lower_local(f,h,wall if new else 1.2,new)
   s,o=add(items,s,f'lower-{f}-{h}',FACES[f][4]+' 下辺'+('A / 下側耳' if h==0 else 'B / 上側耳') if new else FACES[f][4]+' 下辺ガード','guardA' if h==0 else 'guardB',f,note='中央は1mm＋1mmの重ね耳。右側の耳に1mmの段差。' if f in ('left','right') and new else '下辺Lガード。耳をネジで捕捉し接着への依存を減らす。',explode=[x*1.4 for x in FACES[f][3]],material='PA12候補',role='guard')
   shapes[o['id']]=s
 # panel joints: keep existing direction (wall heads inside, nuts outside; floor vice versa).
 for f in FACES:
  for k,(u,v,ang,r) in enumerate(panel_holes(f)):
   if r=='rail':continue
   orig=(u,v)
   if new:
    if r=='corner':u-=math.copysign(1,u)
    elif r=='lower':v+=1
    elif r=='floor-front':v-=math.copysign(1,v)
    elif r=='floor-side':u-=math.copysign(1,u)
   id=f'{f}-{k}';normal=FACES[f][3]
   if new:
    s=coverwasher(u,v,-T-1,-T,ang)
    add(items,s,'inner-'+id,'内側保護ワッシャー · 1mm','inner',f,note='パネルとL金具の間。20×12mm、丸穴φ5.5。ASA黒の試作候補／ナイロンと同一材ではない。',explode=[x*-.35 for x in normal],material='ASA黒 試作候補',role='washer')
   if f=='floor':
    # Retain original inside washer/nut above bracket. Add external wide cover for slot.
    if new:add(items,floor_cover(u,v,0,1,ang),'cap-'+id,'底面・長穴押さえワッシャー','caps',f,note='新規ASA t1。底面低頭1.4mmを加えて2.4mm、仮脚3mmとの公称差0.6mm。',explode=[x*1.6 for x in normal],material='ASA黒',role='washer')
    hn=1 if new else 0
    add(items,head(u,v,hn,hn+1.4),'head-'+id,'底板の外側・低頭M5（模式）','hardware',f,explode=[x*2.4 for x in normal],material='金属',role='fastener')
    seat=-T-sh-2
    add(items,roundwasher(u,v,seat-1,seat),'retain-'+id,'底板金具裏の既存ワッシャー','caps',f,explode=[x*-.8 for x in normal],material='既存保護材',role='washer')
    add(items,nut(u,v,seat-6,seat-1),'nut-'+id,'底板内側・M5ナット（模式）','hardware',f,explode=[x*-1.3 for x in normal],material='金属',role='fastener')
    add(items,disk(u,v,seat-7,hn,2.5),'shaft-'+id,'M5軸 · ねじ長未選定','hardware',f,material='金属',role='fastener')
   else:
    lap=new and r=='lower' and abs(orig[0])<.1 and f in ('left','right')
    ear=(2 if lap else 1) if new else 0
    kind='corner' if r=='corner' else 'lower'
    s=outer_cap(u,v,ear,ear+1,kind) if new else roundwasher(u,v,0,1)
    add(items,s,'cap-'+id,'外側・角丸長方形の押さえ · 1mm' if new else '旧外側ワッシャー φ10','caps',f,note=cap_note(kind) if new else '旧R9比較のφ10ワッシャー。',explode=[x*1.9 for x in normal],material='ASA黒',role='washer')
    if new:cap_pad_check(f,k,orig,(u,v),kind)
    add(items,nut(u,v,ear+1,ear+6),'nut-'+id,'外側M5ロックナット（模式）','hardware',f,note='外側六角は元設計のナット。ユーザー在庫の外形は模式。',explode=[x*2.5 for x in normal],material='金属',role='fastener')
    seat=-T-sh-2
    add(items,head(u,v,seat-1.4,seat),'head-'+id,'金具内側のM5低頭ボルト（模式）','hardware',f,explode=[x*-.85 for x in normal],material='金属',role='fastener')
    add(items,disk(u,v,seat,ear+7,2.5),'shaft-'+id,'M5軸 · ねじ長未選定','hardware',f,material='金属',role='fastener')
 for sx in(-1,1):
  for sy in(-1,1):
   s=cq.Solid.makeCylinder(5,3,cq.Vector(sx*(W/2-20),sy*(D/2-20),-3))
   add(items,s,f'foot-{sx}-{sy}','ゴム脚 · 3mm仮値','feet',material='ゴム（仮）',explode=[0,0,-1])
 if new:
  for f in ('left','right'):
   a=shapes[f'lower-{f}-0'];b=shapes[f'lower-{f}-1']
   vol=a.intersect(b).Volume()
   audits.append({'check':'central lap A/B overlap','variant':wall,'side':f,'overlap_mm3':vol,'passed':vol<1e-6})
 audits.append({'check':'panel joint count','variant':prefix+str(wall),'count':sum(1 for p in items if p['id'].startswith('shaft-')),'passed':sum(1 for p in items if p['id'].startswith('shaft-'))==36})
 return items

