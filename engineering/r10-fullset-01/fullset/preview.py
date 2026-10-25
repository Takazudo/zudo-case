from pathlib import Path
import json,re
from . import geometry as g

def create(items,shapes,out,profile,travel):
    scenes={'new1':items}
    def local_scene(name,face,region,ids=None):
        result=[]
        loc=g.cq.Plane(origin=g.FACES[face][0],xDir=g.FACES[face][1],normal=g.FACES[face][3]).location.inverse
        cutter=g.box(*region)
        for item in items:
            if item['id'] not in shapes or (ids and item['id'] not in ids):continue
            shape=shapes[item['id']].moved(loc).intersect(cutter).clean()
            if not shape.Solids() or shape.Volume()<1e-6:continue
            bb=shape.BoundingBox();part=dict(item,mesh=g.mesh(shape),box=[bb.xmin,bb.ymin,bb.zmin,bb.xmax,bb.ymax,bb.zmax],explode=[0,0,item['explode'][0]+item['explode'][1]])
            result.append(part)
        scenes[name]=result
    local_scene('lap','right',(-27,27,-1,35,-32,15))
    local_scene('joint','front',(g.XS[1]-25,g.XS[1]+25,-2,35,-32,15))
    local_scene('top1.7-1.0','front',(-14,14,80,97,-7,7))
    scenes['corner']=[x for x in items if x['id'] in shapes and x['box'][0]<-85 and x['box'][1]<-140 and x['role']!='lid']
    # Crop actual corner shapes to keep local inspection local.
    crop=g.box(-125,-85,-180,-135,0,90)
    corner=[]
    for item in scenes['corner']:
        s=shapes[item['id']].intersect(crop).clean()
        if not s.Solids() or s.Volume()<1e-6:continue
        bb=s.BoundingBox()
        corner.append(dict(item,mesh=g.mesh(s),box=[bb.xmin,bb.ymin,bb.zmin,bb.xmax,bb.ymax,bb.zmax]))
    scenes['corner']=corner
    for kind in ['corner','lower']:
        result=[];face='right';loc=g.cq.Plane(origin=g.FACES[face][0],xDir=g.FACES[face][1],normal=g.FACES[face][3]).location.inverse
        k=3 if kind=='corner' else 1
        orig=g.panel_holes(face)[k];u,v=orig[:2]
        crop=g.box(u-20,u+20,v-18,v+18,-8,12)
        for item in items:
            id=item['id']
            if id not in shapes or not (id in ['panel-right','lower-right-0','lower-right-1','corner-1--1','bracket-corner-1--1-0'] or id.endswith(f'right-{k}')):continue
            shape=shapes[id].moved(loc).intersect(crop).clean()
            if not shape.Solids() or shape.Volume()<1e-6:continue
            shape=shape.translate((-u,-v,0))
            if kind=='lower':shape=shape.rotate((0,0,0),(0,0,1),-90)
            # Corner at negative U has +1 inward displacement; lower is +V.
            moving=id.startswith(('cap-','inner-','nut-','head-','shaft-'))
            if moving:shape=shape.translate((-1,0,0))
            bb=shape.BoundingBox();result.append(dict(item,mesh=g.mesh(shape),box=[bb.xmin,bb.ymin,bb.zmin,bb.xmax,bb.ymax,bb.zmax],role='moving' if moving else item['role'],explode=[0,0,item['explode'][0]]))
        scenes['washer-'+kind]=result
    data=dict(revision='R10-FULLSET-01',profile=profile,meshes=g.meshes,scenes=scenes,audits=g.audits,travel_checks=travel,outer_caps=g.CAPS)
    template=(Path(__file__).parent/'viewer.html').read_text()
    (out/'preview.html').write_text(template.replace('__MODEL__',json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('</script','<\\/script')))
