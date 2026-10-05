#!/usr/bin/env python3
"""Optional viewing-only GLB export. Dependencies: numpy, trimesh.
Run node export-models.cjs first. Inputs are mm/Z-up; glTF output is m/Y-up.
These triangle meshes omit a manufacturing definition and must not be ordered.
"""
from pathlib import Path
import json
import numpy as np
import trimesh
ROOT=Path(__file__).resolve().parent
manifest={'revision':'F5','manufacturingApproved':False,'units':'metres','upAxis':'Y','scope':'A/B/C source-frame inspection and playing configurations. Source rails retained without scale; PCB outer contours/placement from source, rounded cutouts approximated for display. Independent placements; no manufacturing or strength approval. JSON in mm/Z-up, GLB in m/Y-up. Text labels omitted.','models':[]}
for id in json.loads((ROOT/'models/export-jobs.json').read_text()):
    raw=json.loads((ROOT/'models'/f'{id}-mesh-tmp.json').read_text())
    scene=trimesh.Scene()
    scene.metadata.update({'study':'ZUDO CASE F5','manufacturingApproved':False,'units':'m','sourceCommit':raw['sourceCommit'],'railGeometry':raw['railGeometry'],'pcbGeometry':raw['pcbGeometry'],'caseFamily':raw['caseFamily'],'pose':raw['pose']})
    faces_total=0
    for key,values in raw['groups'].items():
        if not values:continue
        a=np.asarray(values,dtype=np.float32).reshape(-1,9)
        vertices=a[:,[0,2,1]].copy()/1000;vertices[:,2]*=-1
        normals=a[:,[3,5,4]].copy();normals[:,2]*=-1
        colors=np.column_stack((np.clip(a[:,6:9]*255,0,255).astype(np.uint8),np.full(len(a),255,dtype=np.uint8)))
        faces=np.arange(len(a),dtype=np.int32).reshape(-1,3)
        mesh=trimesh.Trimesh(vertices=vertices,faces=faces,vertex_normals=normals,vertex_colors=colors,process=False)
        scene.add_geometry(mesh,node_name=key,geom_name=key)
        faces_total+=len(faces)
    target=ROOT/'models'/f'{id}-F5.glb'
    target.write_bytes(scene.export(file_type='glb'))
    restored=trimesh.load(target,force='scene',process=False)
    assert len(restored.geometry)==len(scene.geometry)
    assert np.allclose(restored.bounds,scene.bounds,atol=1e-6)
    manifest['models'].append({'id':id,'file':target.name,'triangles':faces_total,'bytes':target.stat().st_size,'roundtripBoundsMatch':True})
    print(target.name,target.stat().st_size)
for tmp in (ROOT/'models').glob('*-mesh-tmp.json'):tmp.unlink()
(ROOT/'models'/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
