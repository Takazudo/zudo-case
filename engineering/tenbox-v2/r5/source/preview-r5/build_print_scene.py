"""Show exact flat roof/floor poses from the unsliced single-nozzle projects."""
import json
from pathlib import Path
import numpy as np
import cadquery as cq

ROOT=Path(__file__).resolve().parents[1]


def add_print_scene(data):
    pose=json.loads((ROOT/'h2d-r5/roof-print-pose.json').read_text())
    parts=[]

    def add_cad(pid,name,shape,category,note):
        vertices,triangles=shape.tessellate(.12,.25)
        points=np.asarray([v.toTuple() for v in vertices])
        data['meshes'][pid]={'p':points.ravel().tolist(),'i':[i for t in triangles for i in t]}
        parts.append({'id':pid,'sourceId':pid,'name':name,'mesh':pid,'group':'printReference','cat':category,
                      'box':np.r_[points.min(0),points.max(0)].tolist(),'explode':[0,0,0],
                      'note':note,'selectable':False})

    def box(x,y,z,dx,dy,dz):return cq.Solid.makeBox(dx,dy,dz,cq.Vector(x,y,z))

    add_cad('h2d-bed','H2D bed',box(0,0,-2.2,350,320,2),'printBed',
            '350 × 320 mm total bed. These projects use the left nozzle only.')
    add_cad('h2d-left-area','Left nozzle · 325 × 320 mm',box(0,0,-.2,325,320,.2),'printArea',
            'Verified left nozzle range: X0–325, Y0–320 mm.')
    add_cad('h2d-rear-exclusion','Rear exclusion',box(145,310,0,111,10,.25),'printExclusion',
            'Saved wrapping exclusion at X145–256, Y310–326 mm, clipped to the bed boundary.')

    width=.6
    rods=[box(0,0,0,325,width,.3),box(0,320-width,0,325,width,.3),
          box(0,0,0,width,320,.3),box(325-width,0,0,width,320,.3)]
    add_cad('h2d-left-outline','Single-nozzle boundary',cq.Compound.makeCompound(rods),'printLimits',
            'Flat outline of the left nozzle area. Each shown project uses one nozzle.')

    pid='h2d-roof'
    data['meshes'][pid]=pose['mesh']
    points=np.asarray(pose['mesh']['p']).reshape(-1,3)
    dims=points.max(0)-points.min(0)
    assert np.max(np.abs(dims-[317,290,5]))<.002, dims
    parts.append({'id':pid,'sourceId':'lid-top-single','name':'One-piece roof · flat, left nozzle',
                  'mesh':pid,'group':'print','cat':'lidRoof',
                  'box':np.r_[points.min(0),points.max(0)].tolist(),'explode':[0,0,0],
                  'note':'317 × 290 × 5 mm. X4–321, Y10–300, Z0–5. One nozzle; no supports or brim. Unsliced.'})
    data.setdefault('jointScenes',{})['h2d']=parts
    data['h2dView']={'template':'Bambu Lab H2D 0.6 nozzle / PLA',
                     'nozzle':'left','nozzleAreaMm':[325,320],
                     'roofFootprintMm':dims.tolist(),'roofBoundsMm':np.r_[points.min(0),points.max(0)].tolist(),
                     'yawDegrees':0,'brimAllowanceMm':0,'sliced':False,
                     'status':'Flat model in verified left-nozzle area. Studio slicing and physical printing remain pending.'}

    floor_pose=json.loads((ROOT/'h2d-r5/floor-print-pose.json').read_text())
    floor_parts=[dict(p) for p in parts if p['id']!='h2d-roof']
    pid='h2d-floor'
    data['meshes'][pid]=floor_pose['mesh']
    points=np.asarray(floor_pose['mesh']['p']).reshape(-1,3)
    lo=points.min(0);hi=points.max(0);dims=hi-lo
    assert abs(dims[2]-5)<.002 and abs(lo[2])<.002
    assert lo[0]>0 and hi[0]<325 and lo[1]>0 and hi[1]<320
    floor_parts.append({'id':pid,'sourceId':'body-bottom-back','name':'Common floor · flat diagonal, left nozzle',
                        'mesh':pid,'group':'print','cat':'floor',
                        'box':np.r_[lo,hi].tolist(),'explode':[0,0,0],
                        'note':f'{dims[0]:.2f} × {dims[1]:.2f} mm footprint; 5 mm high. Same part for front/back; print twice. No brim or support. Unsliced.'})
    data['jointScenes']['floor-fit']=floor_parts
    data['floorPrintView']={'template':'Bambu Lab H2D 0.6 nozzle / PLA',
                           'nozzle':'left','yawDegrees':-45,'quantity':2,'sliced':False,
                           'footprintMm':dims.tolist(),'boundsMm':np.r_[lo,hi].tolist(),
                           'status':'Actual outline clears the single-left-nozzle area and the rear wrapping exclusion.'}
