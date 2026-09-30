"""Coupons derive from the SAME section/perimeter/lid functions as the case.

C1 is straight upper-channel comparison. C2 is a seated front lid section.
C4 tests the floor+wall LOWER joint. C5 tests the two-wall UPPER corner.
C3 is not changed here: use/review the existing R9 slot/hardware coupons locally.
"""
from dataclasses import replace
import cadquery as cq
from .geometry import *

GLYPHS={
 'C':('111','100','100','100','111'),'-':('000','000','111','000','000'),
 '0':('111','101','101','101','111'),'1':('010','110','010','010','111'),
 '2':('111','001','111','100','111'),'3':('111','001','111','001','111'),
 '4':('101','101','111','001','001'),'5':('111','100','111','001','111'),
 '6':('111','100','111','101','111'),'7':('111','001','001','001','001'),
 '8':('111','101','111','101','111'),'9':('111','101','111','001','111'),
}

def label_on_x(shape, text, x, y, z, direction=1, pixel=.4, rise=.3):
    """Raised fixed glyphs, 2mm high. Their bottom face meets the outside wall."""
    marks=[]
    for idx,char in enumerate(text):
        for row,bits in enumerate(GLYPHS[char]):
            for col,bit in enumerate(bits):
                if bit=='1':
                    x0,x1=sorted([x,x+direction*rise])
                    marks.append(box(x0,x1,y+(4*idx+col)*pixel,y+(4*idx+col+1)*pixel,
                                     z+(4-row)*pixel,z+(5-row)*pixel))
    return union([shape,*marks],text+' label')


def coupon_families(b: Body,g: Guard,l: dict):
    records=[]
    # C1 fixtures rest on a real metal edge; the roof's underside is the datum.
    variants=[('C1-01',g,40,1,'baseline'),
              ('C1-02',replace(g,fit_per_face=.10),40,1,'fit=.10 only'),
              ('C1-03',replace(g,fit_per_face=.25),40,1,'fit=.25 only'),
              ('C1-04',replace(g,adhesive_per_face=0),40,1,'adhesive allowance=0 only'),
              ('C1-05',replace(g,wall=1.0),40,1,'wall=1.0 only'),
              ('C1-06',g,(40-g.end_gap)/2,2,'pair, target total split gap=.5'),
              ('C1-07',g,20,2,'pair, target total split gap=0')]
    for name,gg,length,qty,note in variants:
        s=guard_section(b,gg,length)
        textwidth=(len(name)*4-1)*.4
        s=label_on_x(s,name,gg.gap+gg.wall,(length-textwidth)/2,-3.5)
        p=Part(name.lower()+'-guard',s,qty,group='coupon')
        records.append(dict(id=name,parts=[p],variables=vars(gg),purpose=note,
                            physical_results=None,reusable_fixture='c1-metal-edge'))
    metal=Part('c1-metal-edge',box(-b.metal,0,0,40,-20,0),1,'A5052 t1.5 candidate','coupon-metal')
    records.append(dict(id='C1-METAL',parts=[metal],purpose='One reusable 40x20mm real metal edge',physical_results=None))
    body={p.id:p for p in body_envelopes(b)}
    fullguards=guard_instances(guard_parts(b,g))
    # Clip existing generated instances, not a separately-designed cross-section.
    topfront=next(p for p in fullguards if p.id=='t1p2-top-a-b')
    lowerfront=next(p for p in fullguards if p.id=='t1p2-lower-width-half-b')
    for num,c in enumerate((l['locator_clearance'],.5,.9),1):
        ll={**l,'locator_clearance':c};name=f'C2-{num:02d}'
        parts,holes=lid_parts(b,g,ll);mp={p.id:p for p in parts}
        def cut(s):return clip(s,20,50,-b.depth/2-5,-b.depth/2+27,60,150)
        frame=cut(mp['lid-frame-fr'].shape)
        # Label on the local outer front face by swapping X/Y for the glyph tool.
        rotated=frame.rotate((0,0,0),(0,0,1),90)
        # After rotation the front exterior is positive X, Y=original X.
        rotated=label_on_x(rotated,name,b.depth/2+g.gap+g.wall,24,99)
        frame=solid(rotated.rotate((0,0,0),(0,0,1),-90))
        selected=[Part(name.lower()+'-wall',cut(body['body-front'].shape),1,'A5052 t1.5 candidate','coupon-metal'),
                  Part(name.lower()+'-guard',cut(topfront.shape),1,group='coupon'),
                  Part(name.lower()+'-frame',frame,1,group='coupon'),
                  Part(name.lower()+'-plate',cut(mp['lid-plate'].shape),1,'A5052 t1.5 candidate','coupon-metal')]
        records.append(dict(id=name,parts=selected,purpose='Front lid/guard physical seating and locator fit',
                            locator_clearance_mm=c,interface=interface(b,g,ll),holes_assembly_xy=holes,
                            physical_results=None,reuse='wall, guard and plate are reusable across C2; order one of each for sequential trials'))
    # NEW: floor and wall physically occupy the same geometry as the case.
    def cut_lower(s):return clip(s,20,50,-b.depth/2-5,-b.depth/2+20,-5,20)
    lower=cut_lower(lowerfront.shape)
    rot=lower.rotate((0,0,0),(0,0,1),90)
    rot=label_on_x(rot,'C4-01',b.depth/2+g.gap+g.wall,24,1.5)
    lower=solid(rot.rotate((0,0,0),(0,0,1),-90))
    records.append(dict(id='C4-01',parts=[
        Part('c4-01-floor',cut_lower(body['body-bottom'].shape),1,'A5052 t1.5 candidate','coupon-metal'),
        Part('c4-01-wall',cut_lower(body['body-front'].shape),1,'A5052 t1.5 candidate','coupon-metal'),
        Part('c4-01-lower-guard',lower,1,group='coupon')],
        purpose='NEW: bottom-floor + vertical wall + lower L cover, same case solids',physical_results=None))
    def cut_corner(s):return clip(s,-b.width/2-5,-b.width/2+12,-b.depth/2-5,-b.depth/2+12,b.height-20,b.height+5)
    upper=next(p for p in fullguards if p.id=='t1p2-top-a-a')
    corner=cut_corner(upper.shape)
    corner=label_on_x(corner,'C5-01',-b.width/2-g.gap-g.wall,-b.depth/2+1,b.height-3.5,-1)
    records.append(dict(id='C5-01',parts=[
        Part('c5-01-front',cut_corner(body['body-front'].shape),1,'A5052 t1.5 candidate','coupon-metal'),
        Part('c5-01-left',cut_corner(body['body-left'].shape),1,'A5052 t1.5 candidate','coupon-metal'),
        Part('c5-01-upper-guard',corner,1,group='coupon')],
        purpose='NEW: two meeting vertical plates and upper U-return corner, same case solids',physical_results=None))
    return records
