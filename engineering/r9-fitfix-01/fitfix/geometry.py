"""Shared guard, lid and coupon geometry. Z=0 is the metal floor underside.

All dimensions are mm. Empty fit/adhesive space is added BEFORE material
thickness, never subtracted from it. Allowances apply to VERTICAL bonding faces only;
the roof/floor bearing faces are hard datums with zero vertical gap. Lower guards are L covers, not inverted
upper U channels. The upper perimeter is built from nested rectangular rings,
so its returns stay wholly inside the two-wall cavity at every corner.
"""
from __future__ import annotations
from dataclasses import dataclass, replace
import math
from typing import Iterable
import cadquery as cq

EPS = 1e-7

@dataclass(frozen=True)
class Body:
    width: float = 229.4
    depth: float = 334.0
    height: float = 91.0
    metal: float = 1.5

@dataclass(frozen=True)
class Guard:
    wall: float = 1.2
    cover: float = 5.0
    fit_per_face: float = .15
    adhesive_per_face: float = .15
    end_gap: float = .5
    vertical_end_gap: float = .25
    outer_radius: float = .4

    @property
    def gap(self) -> float:
        return self.fit_per_face + self.adhesive_per_face

    def validate(self) -> None:
        fields = vars(self)
        if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in fields.values()):
            raise ValueError('Guard values must be finite numbers')
        if self.wall <= 0 or self.cover <= 0 or self.gap < 0:
            raise ValueError('Positive wall/cover and nonnegative fit+adhesive are required')
        if min(self.fit_per_face, self.adhesive_per_face, self.end_gap,
               self.vertical_end_gap, self.outer_radius) < 0:
            raise ValueError('Negative allowances are not permitted')
        if self.outer_radius >= self.wall or self.end_gap >= self.cover:
            raise ValueError('Fillet must be smaller than wall; split gap must be smaller than cover')

@dataclass
class Part:
    id: str
    shape: cq.Shape
    quantity: int = 1
    material: str = 'PA12-HP black candidate'
    group: str = 'guard'


def box(x0, x1, y0, y1, z0, z1):
    if min(x1-x0, y1-y0, z1-z0) <= 0:
        raise ValueError(f'Nonpositive box: {(x0,x1,y0,y1,z0,z1)}')
    return cq.Solid.makeBox(x1-x0, y1-y0, z1-z0, cq.Vector(x0,y0,z0))


def solid(shape: cq.Shape, name: str = 'part') -> cq.Shape:
    shape = shape.clean()
    if not shape.isValid() or len(shape.Solids()) != 1 or shape.Volume() <= EPS:
        raise ValueError(f'{name}: invalid or multiple solids')
    return shape


def union(shapes: Iterable[cq.Shape], name='part') -> cq.Shape:
    items = list(shapes)
    return solid(items[0].fuse(*items[1:]), name)


def ring(outer_x, outer_y, inner_x, inner_y, z0, z1):
    if inner_x <= 0 or inner_y <= 0 or inner_x >= outer_x or inner_y >= outer_y:
        raise ValueError('Nested ring dimensions are invalid')
    return solid(box(-outer_x,outer_x,-outer_y,outer_y,z0,z1).cut(
        box(-inner_x,inner_x,-inner_y,inner_y,z0-1,z1+1)), 'rectangular ring')


def rounded_outer_edge(shape, ox, oy, z, radius):
    if radius == 0:
        return shape
    edges=[]
    for e in shape.Edges():
        b=e.BoundingBox()
        if e.geomType() != 'LINE' or abs(b.zmin-z)>EPS or abs(b.zmax-z)>EPS:
            continue
        on_x=abs(b.xmax-b.xmin)<EPS and abs(abs(b.xmin)-ox)<EPS
        on_y=abs(b.ymax-b.ymin)<EPS and abs(abs(b.ymin)-oy)<EPS
        if on_x or on_y:
            edges.append(e)
    if len(edges)!=4:
        raise ValueError(f'Expected four outer edges, got {len(edges)}')
    return solid(shape.Solids()[0].fillet(radius,edges), 'outer rounding')


def interface(b: Body, g: Guard, lid: dict) -> dict:
    g.validate()
    if min(b.width,b.depth,b.height,b.metal) <= 0:
        raise ValueError('Body dimensions must be positive')
    offset = g.gap+g.wall
    # Absolute coordinate, NOT the total guard envelope height.
    guard_top=b.height+g.wall
    guard_bottom=-g.wall
    opening_x=b.width-2*(b.metal+g.gap+g.wall)
    opening_y=b.depth-2*(b.metal+g.gap+g.wall)
    outside_x=b.width+2*offset
    outside_y=b.depth+2*offset
    if min(opening_x,opening_y) <= 0:
        raise ValueError('Guard opening collapsed')
    seat=guard_top
    plate_bottom=seat+lid['rise_to_plate_underside']
    plate_top=plate_bottom+lid['plate_thickness']
    return dict(
        guard_opening_mm=[opening_x,opening_y],
        guard_exterior_mm=[outside_x,outside_y],
        guard_bottom_z_mm=guard_bottom, guard_top_z_mm=guard_top,
        guard_envelope_height_mm=guard_top-guard_bottom,
        lid_seat_z_mm=seat, plate_bottom_z_mm=plate_bottom,
        plate_top_z_mm=plate_top, lip_top_z_mm=plate_top+lid['top_lip'],
        locator_bottom_z_mm=seat-lid['locator_engagement'],
        flat_wall_mm=g.wall, metal_offset_mm=g.gap,
        lid_plate_mm=[outside_x-2*(lid['frame_wall']+lid['plate_edge_gap']),
                      outside_y-2*(lid['frame_wall']+lid['plate_edge_gap']),lid['plate_thickness']],
        lid_locator_xy_clearance_mm=lid['locator_clearance'],
        lid_engagement_mm=lid['locator_engagement'],
        plate_under_clearance_to_assumed_knob_mm=plate_bottom-(b.height+lid['module_panel']+lid['knob_height']),
    )


def guard_section(b: Body, g: Guard, length: float, kind='top') -> cq.Shape:
    """Local metal exterior X=0, metal edge Z=0, extrusion +Y.

    Top: U around a vertical sheet X=-metal..0 below Z=0.
    Bottom: L outside a floor occupying X<=0, Z=0..metal.
    Wall thickness is g.wall on every major flat face for all allowances.
    """
    g.validate()
    if not math.isfinite(length) or length<=0:
        raise ValueError('Positive finite section length required')
    t,q,m,c=g.wall,g.gap,b.metal,g.cover
    if kind=='top':
        pts=[(-m-q-t,t),(q+t,t),(q+t,-c),(q,-c),
             (q,0),(-m-q,0),(-m-q,-c),(-m-q-t,-c)]
        edge_z=t
    elif kind=='bottom':
        pts=[(-c,-t),(q+t,-t),(q+t,c),(q,c),(q,0),(-c,0)]
        edge_z=-t
    else:
        raise ValueError('Unknown section kind')
    wire=cq.Wire.makePolygon([cq.Vector(x,0,z) for x,z in pts],close=True)
    s=solid(cq.Solid.extrudeLinear(wire,[],cq.Vector(0,length,0)))
    if g.outer_radius:
        edges=[e for e in s.Edges() if e.geomType()=='LINE'
               and abs(e.Length()-length)<EPS
               and abs(e.BoundingBox().xmin-(q+t))<EPS
               and abs(e.BoundingBox().zmin-edge_z)<EPS]
        if len(edges)!=1:
            raise ValueError('Missing section fillet edge')
        s=solid(s.Solids()[0].fillet(g.outer_radius,edges))
    return s


def guard_perimeter(b: Body, g: Guard, kind='top') -> cq.Shape:
    """All four corners come from ONE nested profile, not crossed U bars."""
    g.validate()
    t,q=g.wall,g.gap
    ox,oy=b.width/2+q+t,b.depth/2+q+t
    ex,ey=b.width/2+q,b.depth/2+q
    if kind=='top':
        ix,iy=b.width/2-b.metal-q,b.depth/2-b.metal-q
        opening_x,opening_y=ix-t,iy-t
        s=union([
            ring(ox,oy,ex,ey,b.height-g.cover,b.height),
            ring(ix,iy,opening_x,opening_y,b.height-g.cover,b.height),
            ring(ox,oy,opening_x,opening_y,b.height,b.height+t),
        ],'top U ring')
        return rounded_outer_edge(s,ox,oy,b.height+t,g.outer_radius)
    if kind=='bottom':
        s=union([
            ring(ox,oy,ex,ey,0,g.cover),
            ring(ox,oy,b.width/2-g.cover,b.depth/2-g.cover,-t,0),
        ],'bottom L ring')
        return rounded_outer_edge(s,ox,oy,-t,g.outer_radius)
    raise ValueError('Unknown perimeter kind')


def clip(shape, x0,x1,y0,y1,z0=-1000,z1=1000):
    return solid(shape.intersect(box(x0,x1,y0,y1,z0,z1)), 'clip')


def vertical_corner(b: Body, g: Guard):
    t,q,c=g.wall,g.gap,g.cover
    x,y=-b.width/2,-b.depth/2
    z0=c+g.vertical_end_gap
    z1=b.height-c-g.vertical_end_gap
    s=union([box(x-q-t,x-q,y-q-t,y+c,z0,z1),
             box(x-q-t,x+c,y-q-t,y-q,z0,z1)],'vertical corner')
    if g.outer_radius:
        es=[e for e in s.Edges() if e.geomType()=='LINE'
            and abs(e.Length()-(z1-z0))<EPS
            and abs(e.BoundingBox().xmin-(x-q-t))<EPS
            and abs(e.BoundingBox().ymin-(y-q-t))<EPS]
        s=solid(s.Solids()[0].fillet(g.outer_radius,es))
    return s


def guard_parts(b: Body, g: Guard, tag='t1p2') -> list[Part]:
    top=guard_perimeter(b,g,'top'); bottom=guard_perimeter(b,g,'bottom')
    h=g.end_gap/2
    cut_y=-b.depth/2+g.cover
    return [
        Part(f'{tag}-top-a',clip(top,-1000,-h,-1000,-h),2),
        Part(f'{tag}-top-b',clip(top,-1000,-h,h,1000),2),
        Part(f'{tag}-lower-width-half',clip(bottom,-1000,-h,-1000,cut_y-h),4),
        Part(f'{tag}-lower-depth-a',clip(bottom,-1000,0,cut_y+h,-h),2),
        Part(f'{tag}-lower-depth-b',clip(bottom,-1000,0,h,-cut_y-h),2),
        Part(f'{tag}-vertical-corner',vertical_corner(b,g),4),
    ]


def guard_instances(parts: list[Part]) -> list[Part]:
    """Every physical instance, including all four lower and vertical parts."""
    result=[]
    for p in parts:
        transforms=[('a',lambda s:s)]
        if p.quantity>=2:
            transforms.append(('b',lambda s:s.mirror('YZ')))
        if p.quantity==4:
            transforms += [('c',lambda s:s.mirror('XZ')),('d',lambda s:s.rotate((0,0,0),(0,0,1),180))]
        if len(transforms)!=p.quantity:
            raise ValueError('Unsupported quantity')
        for suffix,fn in transforms:
            result.append(Part(f'{p.id}-{suffix}',solid(fn(p.shape)),1,p.material,p.group))
    return result


def hex_prism(x,y,z0,z1,af):
    r=af/math.sqrt(3)
    wire=cq.Wire.makePolygon([cq.Vector(x+r*math.cos(i*math.pi/3),y+r*math.sin(i*math.pi/3),z0)
                              for i in range(6)],close=True)
    return cq.Solid.extrudeLinear(wire,[],cq.Vector(0,0,z1-z0))


def lid_quarter(b: Body,g: Guard,l: dict):
    """R9 make_quarter construction, rebuilt with derived seating references.

    Eight plate/frame M3 bores remain assembly fasteners only. No body lock,
    rear hook, magnet, rotary latch, or friction-retention promise is added.
    """
    i=interface(b,g,l)
    ox,oy=(x/2 for x in i['guard_exterior_mm'])
    wx,wy=(x/2 for x in i['guard_opening_mm'])
    w=l['frame_wall']; seat=i['lid_seat_z_mm'];pz=i['plate_bottom_z_mm'];lip=i['lip_top_z_mm']
    seam=l['frame_seam']/2;ledge=l['ledge_depth']
    front=(ox*l['front_screw_fraction'],-oy+l['screw_inset'])
    side=(ox-l['screw_inset'],-oy*l['side_screw_fraction'])
    tx=wx-l['locator_clearance'];ty=-wy+l['locator_clearance']
    bottom=i['locator_bottom_z_mm']
    if tx<=seam or l['locator_clearance']<0 or l['locator_engagement']<=0:
        raise ValueError('Invalid locator/clearance')
    tab=box(seam,tx,ty,ty+l['locator_wall'],bottom,seat+l['bridge_height'])
    edges=[e for e in tab.Edges() if abs(e.BoundingBox().zmin-bottom)<EPS
           and abs(e.BoundingBox().zmax-bottom)<EPS]
    tab=solid(tab.Solids()[0].fillet(l['lead_radius'],edges))
    s=union([
        box(seam,ox,-oy,-oy+w,seat,lip),box(ox-w,ox,-oy+w,-seam,seat,lip),
        box(seam,ox,-oy,-oy+ledge,pz-l['ledge_thickness'],pz),
        box(ox-ledge,ox,-oy+ledge,-seam,pz-l['ledge_thickness'],pz),
        box(front[0]-7,front[0]+7,-oy,-oy+11,pz-l['boss_depth'],pz),
        box(ox-11,ox,side[1]-7,side[1]+7,pz-l['boss_depth'],pz),
        box(seam,tx,-oy,ty+l['locator_wall'],seat,seat+l['bridge_height']),tab,
    ],'lid quarter')
    for x,y in (front,side):
        bore=cq.Solid.makeCylinder(l['assembly_hole']/2,l['boss_depth']+2,
                                  cq.Vector(x,y,pz-l['boss_depth']-1))
        pocket=hex_prism(x,y,pz-l['boss_depth']-.2,pz-l['nut_roof'],l['nut_af'])
        s=solid(s.cut(bore).cut(pocket),'lid nut boss')
    return s,(front,side)


def lid_parts(b: Body,g: Guard,l: dict) -> tuple[list[Part],list[tuple[float,float]]]:
    q,ss=lid_quarter(b,g,l)
    transforms=[('fr',lambda s:s,lambda p:p),
                ('fl',lambda s:s.mirror('YZ'),lambda p:(-p[0],p[1])),
                ('bl',lambda s:s.rotate((0,0,0),(0,0,1),180),lambda p:(-p[0],-p[1])),
                ('br',lambda s:s.mirror('XZ'),lambda p:(p[0],-p[1]))]
    parts=[];holes=[]
    for name,fn,pt in transforms:
        parts.append(Part('lid-frame-'+name,solid(fn(q)),1,'PA12-HP black candidate','lid'))
        holes.extend(pt(p) for p in ss)
    i=interface(b,g,l);px,py,t=i['lid_plate_mm']
    plate=(cq.Workplane('XY').box(px,py,t,centered=(True,True,False)).edges('|Z')
           .fillet(l['plate_corner_radius']).val().translate((0,0,i['plate_bottom_z_mm'])))
    for x,y in holes:
        plate=plate.cut(cq.Solid.makeCylinder(l['assembly_hole']/2,t+2,
                       cq.Vector(x,y,i['plate_bottom_z_mm']-1)))
    parts.append(Part('lid-plate',solid(plate),1,'A5052 t1.5 black anodized candidate','lid-metal'))
    return parts,holes


def body_envelopes(b: Body) -> list[Part]:
    w,d,h,t=b.width,b.depth,b.height,b.metal
    solids={
        'bottom':box(-w/2,w/2,-d/2,d/2,0,t),
        'front':box(-w/2+t,w/2-t,-d/2,-d/2+t,t,h),
        'back':box(-w/2+t,w/2-t,d/2-t,d/2,t,h),
        'left':box(-w/2,-w/2+t,-d/2,d/2,t,h),
        'right':box(w/2-t,w/2,-d/2,d/2,t,h),
    }
    return [Part('body-'+k,s,1,'A5052 t1.5 reference envelope','body-reference') for k,s in solids.items()]
