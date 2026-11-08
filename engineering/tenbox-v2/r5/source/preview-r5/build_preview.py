"""Build the self-contained 10BOX review viewer from canonical candidate meshes."""
import argparse,base64,gzip,hashlib,json,re
from pathlib import Path
from build_print_scene import add_print_scene

ROOT=Path(__file__).resolve().parent.parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--inline-path',type=Path,default=ROOT/'deliverables/10box-v2-r5-inline.html')
args=parser.parse_args()
template=(ROOT/'preview-r5/tenbox-v2-template.html').read_text()
app=(ROOT/'preview-r5/viewer-app.js').read_text()
reference=(ROOT/'research/zudo-case/viewer-template.html').read_text()
core=reference[reference.index('const vsrc='):reference.index('function sceneKey()')]
render=reference[reference.index('function drawPart('):reference.index('function tick()')]
render=render.replace('gl.clearColor(.918,.941,.945,1)','gl.clearColor(.87451,.91373,.90588,1)')
render=render.replace('rgba[k]=234;rgba[k+1]=240;rgba[k+2]=241','rgba[k]=223;rgba[k+1]=233;rgba[k+2]=231')
# Orthographic lighting must not invent triangular seams on one planar roof.
render=render.replace('vv=V.norm(V.sub(eye,centroid))','vv=state.ortho?V.mul(forward,-1):V.norm(V.sub(eye,centroid))')
app=app.replace('__ENGINE_CORE__',core).replace('__ENGINE_RENDER__',render)
(ROOT/'preview-r5/viewer-built.js').write_text(app)

data_path=ROOT/'10box-v2-r5/model_data.json'
if not data_path.exists():
    print('Viewer script built; candidate model_data.json is not ready yet.')
    raise SystemExit(0)
data=json.loads(data_path.read_text())
# Compare the clipped floors against the preceding R4 geometry.
previous=json.loads((ROOT/'10box-v2-r5/source-r4/model_data.json').read_text())
data['baselineParts']=[]
for original in previous['parts']:
    p=dict(original)
    mesh_id='previous-r4-'+p['mesh']
    data['meshes'][mesh_id]=previous['meshes'][p['mesh']]
    p['mesh']=mesh_id
    data['baselineParts'].append(p)
data['comparison']={'name':'Previous R4','bodyWidthMm':337.4,'frameToSideGapMm':8,'roofPanels':1,'roofWidthMm':317,'floorCornersClipped':False}
body_ids={'body-left','body-right','body-front','body-back','body-bottom-front','body-bottom-back'}
for key in ['parts','baselineParts']:
    for p in data.get(key,[]):
        p.setdefault('sourceId',p['id'])
        p['cat']='floor' if 'bottom' in p['id'] else ('panels' if p['id'] in body_ids else p.get('cat','reference'))
        if p['id'].startswith('lid-'):
            p['group']='lid';p['cat']='lidRoof' if 'top' in p['id'] else 'lidEdges'
        elif p['id'].startswith('stand-'):
            p['group']='stand';p['cat']='stand'
        elif p['id'] in body_ids:p['group']='body'
        # Convert source explosion vectors to dimensionless direction coefficients.
        explode=p.get('explode',[0,0,0])
        if max(abs(x) for x in explode)>3:explode=[x/65 for x in explode]
        p['explode']=explode
for scene, parts in data.get('jointScenes', {}).items():
    for p in parts:
        p.setdefault('sourceId',p['id'].removeprefix(scene+'-'))
        p.setdefault('cat','floor' if 'bottom' in p['sourceId'] else 'panels')
        if p['sourceId'] in body_ids:p['cat']='floor' if 'bottom' in p['sourceId'] else 'panels'
        p['explode']=[1,0,0] if p['sourceId']=='body-right' else [0,0,0]

# Source rail meshes, two 3U60 frames, native part matrices and original layout.
rail_path=ROOT/'research/zzmod/rail-3u60-geometry.json'
if rail_path.exists():
    import numpy as np
    rails=json.loads(rail_path.read_text())
    for key,plane,prefix in [('parts',72.0,'r5'),('baselineParts',72.0,'r4')]:
        for row,depth in enumerate([-70,70]):
            for k,p in enumerate(rails['nylonParts']):
                src=rails['geometries'][p.get('asset') or p['panel']]
                pts=np.asarray(src['positions'],dtype=float).reshape(-1,3)
                mat=np.asarray(p['matrix']).reshape(4,4,order='F')
                q=np.c_[pts,np.ones(len(pts))]@mat.T
                # Preserve native geometry; change only the rail placement datum.
                # One exact front-row mesh, reused through rigid translations.
                world=np.c_[q[:,0],-70-q[:,1],72+q[:,2]]
                inds=np.asarray(src['indices'],dtype=int).reshape(-1,3)[:,[0,2,1]]
                mesh_id=f'source-rail-{k}'
                data['meshes'][mesh_id]={'p':np.round(world,5).ravel().tolist(),'i':inds.ravel().tolist()}
                note='Unchanged source frame. Upper mounting slots, panel plane flush at Z72; 8 mm side gap.'
                part_id=f'{prefix}-rail-{row}-{k}'
                part={'id':part_id,'sourceId':part_id,'name':('Front' if row==0 else 'Rear')+' 3U60 frame / '+str(p.get('id') or p.get('asset') or p.get('panel')),'cat':'railPCB' if p.get('category')=='panel' else 'rails','group':'rails','mesh':mesh_id,'box':np.r_[world.min(axis=0),world.max(axis=0)].tolist(),'staticOffset':[0,depth+70,plane-72],'explode':[0,(-.5 if row==0 else .5),.7],'material':'Original rail reference','note':note}
                data[key].append(part)
    data['railSource']={'sha':rails.get('sourceCommit') or rails.get('repositorySha'), 'panelPlaneZ':72.0,'previousPanelPlaneZ':72.0,'physicalFitVerified':False}

add_print_scene(data)

# Drop unused source/reference meshes from the inline payload.
referenced={p['mesh'] for p in data['parts']+data['baselineParts']}
for parts in data.get('jointScenes',{}).values():referenced.update(p['mesh'] for p in parts)
data['meshes']={k:v for k,v in data['meshes'].items() if k in referenced}
for mesh in data['meshes'].values():
    # Rendering precision only. The STEP/STL review files remain unchanged.
    mesh['p']=[round(x,3) for x in mesh['p']]
# Identical earlier/current panels share one render mesh.
canonical={};aliases={};unique={}
for key,mesh in data['meshes'].items():
    digest=hashlib.sha256(json.dumps(mesh,separators=(',',':')).encode()).hexdigest()
    target=canonical.setdefault(digest,key);aliases[key]=target
    if target==key:unique[key]=mesh
for part in data['parts']+data['baselineParts']+[p for scene in data.get('jointScenes',{}).values() for p in scene]:
    part['mesh']=aliases[part['mesh']]
data['meshes']=unique

raw=json.dumps(data,separators=(',',':'),ensure_ascii=False).encode()
encoded=base64.b64encode(gzip.compress(raw,compresslevel=9,mtime=0)).decode()
fragment=template.replace('__MODEL_GZIP__',encoded).replace('__VIEWER_SCRIPT__',app)
if len(fragment.encode())>=1024*1024:raise ValueError(f'Inline preview exceeds 1 MiB: {len(fragment.encode())} bytes')
out=ROOT/'deliverables';out.mkdir(exist_ok=True)
inline=args.inline_path;inline.parent.mkdir(parents=True,exist_ok=True);inline.write_text(fragment)
html='<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>10BOX v2 · R5 clipped floor corners</title><style>html,body{margin:0;min-height:100%;background:#e8eeeb}body{padding:16px;max-width:1500px;margin:auto}.cursor-interaction{cursor:pointer}@media(max-width:600px){body{padding:0}}</style></head><body>\n'+fragment+'\n</body></html>\n'
(out/'10box-v2-r5-preview.html').write_text(html)
(ROOT/'preview-r5/viewer-data.json').write_bytes(raw)
print(json.dumps({'inline':str(inline),'download':str(out/'10box-v2-r5-preview.html'),'inline_bytes':len(fragment.encode()),'mesh_count':len(data['meshes']),'part_count':len(data['parts'])}))
