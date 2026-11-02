"""Build one editable, unsliced H2D project per P5 printable type."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys,zipfile
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
import bambu_3mf as b

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,value):p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);p.add_argument('--studio',type=Path);p.add_argument('--cad',required=True,type=Path);a=p.parse_args()
    bom=json.loads((a.cad/'BOM.json').read_text())
    assert bom['revision']=='P5-PRINTED-5MM-TAB-JOINTS-J3', 'Expected P5 CAD output'
    manifest=json.loads((a.cad/'outputs-manifest.json').read_text())
    assert manifest['revision']==bom['revision']
    for f in manifest['files']:
        assert digest(a.cad/f['path'])==f['sha256'],f['path']
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    if any(out.iterdir()):raise SystemExit('Output must be empty')
    for folder in ('projects','manifests','verification'):(out/folder).mkdir()
    shutil.copytree(a.cad/'stl',out/'input-stl')
    shutil.copytree(ROOT/'template',out/'template')
    inventory=json.loads((a.cad/'BOM.json').read_text())['printed'];summary=[]
    original=b.read_archive(ROOT/'template/h2d-empty-original.3mf');original_cfg=b.settings(original)
    assert hashlib.sha256(original[b.SETTINGS]).hexdigest()=='99b34023dcf3d8142abb119f426ca54d499a4d07026c7e406e2b062147c7a356'
    studio=a.studio.resolve() if a.studio else None
    for row in inventory:
        pid=row['id'];right=pid in ('wall-left','wall-right')
        template_name='h2d-empty-right.3mf' if right else 'h2d-empty-original.3mf'
        template=out/'template'/template_name
        vertices,triangles,stats=b.read_mesh(str(out/'input-stl'/f'{pid}.stl'),ROOT)
        lo,hi=b.bbox(vertices);w,h,z=[hi[i]-lo[i] for i in range(3)]
        # Keep flat P5 meshes without additional rotation/scaling; move the 341mm walls into Right's 325mm region.
        xy=[25+(325-w)/2,(320-h)/2] if right else [25+(300-w)/2,(310-h)/2]
        manifest={'schema_version':1,'title':f'P5 {pid} / H2D / unsliced','description':'P5 geometry unchanged. Settings retained; user will configure print details. No toolpaths.','margin_mm':0,'settings':{'brim_type':'no_brim','brim_width':'0'},'gap_mm':6,'objects':[{'name':f'P5 {pid}','mesh':f'../input-stl/{pid}.stl','filament':1,'position_mm':xy,'rotate_z_degrees':0}]}
        mf=out/'manifests'/f'{pid}.json';write(mf,manifest)
        filename=f'p5-{pid}-h2d-'+('right-' if right else '')+'pla06.3mf'
        target=out/'projects'/filename
        generated=b.create(template,mf,target);generated.pop('output',None)
        data=b.read_archive(target);cfg=b.settings(data)
        model=b.parse_xml(data[b.MODEL],b.MODEL)
        mesh=model.find('.//'+b.q('mesh'))
        actual_vertices=[[float(v.get(axis)) for axis in ('x','y','z')] for v in mesh.findall(b.q('vertices')+'/'+b.q('vertex'))]
        actual_triangles=[tuple(int(t.get(axis)) for axis in ('v1','v2','v3')) for t in mesh.findall(b.q('triangles')+'/'+b.q('triangle'))]
        normalized=[[v[i]-lo[i] for i in range(3)] for v in vertices]
        assert actual_triangles==triangles
        assert len(actual_vertices)==len(normalized)
        assert max(abs(x-y) for a0,b0 in zip(actual_vertices,normalized) for x,y in zip(a0,b0))<1e-5
        generated['source_mesh_fingerprint']=hashlib.sha256(json.dumps({'vertices':normalized,'triangles':triangles},separators=(',',':')).encode()).hexdigest()
        generated['mesh_identity_verified']=True
        expected_changes={'filament_map','filament_map_mode','brim_type','brim_width'} if right else {'brim_type','brim_width'}
        changed={k for k in cfg.keys()|original_cfg.keys() if cfg.get(k)!=original_cfg.get(k)}
        assert changed==expected_changes,(pid,changed)
        if right:
            plate=b.parse_xml(data[b.OBJECTS],b.OBJECTS).find('plate')
            assert any(m.get('key')=='filament_map_mode' and m.get('value')=='Manual' for m in plate.findall('metadata'))
            assert cfg['filament_map']==['2','2']
        assert generated['contains_toolpaths'] is False and len(generated['build_items'])==1
        generated['original_template_changed_keys']=sorted(changed)
        generated['settings_diff']={k:{'before':original_cfg.get(k),'after':cfg.get(k)} for k in sorted(changed)}
        assert cfg['brim_type']=='no_brim' and cfg['brim_width']=='0'
        for name,payload in data.items():
            if name.endswith('.config') and name!=b.SETTINGS:
                xml=b.parse_xml(payload,name)
                for item in xml.iter('metadata'):
                    if item.get('key') in ('brim_type','brim_width'):
                        assert item.get('value')=={'brim_type':'no_brim','brim_width':'0'}[item.get('key')]

        studio_result={'verified':False,'status':'NOT RUN: Studio executable unavailable' if not studio else 'pending'}
        if studio:
            dest=out/'verification'/f'{pid}.studio.3mf'
            cmd=[str(studio),'--datadir',str(out/'verification/studio-data'),'--arrange','0','--export-3mf',str(dest),str(target)]
            run=subprocess.run(cmd,cwd=out/'verification',capture_output=True,text=True)
            (out/'verification'/f'{pid}.studio.log').write_text(run.stdout+run.stderr)
            assert run.returncode==0 and dest.exists(),(pid,run.returncode,run.stderr)
            normalized=b.read_archive(dest);norm_cfg=b.settings(normalized)
            # Studio adds preset bookkeeping, but must not change any requested/generated setting.
            delta={k:{'before':cfg[k],'after':norm_cfg.get(k)} for k in cfg if cfg[k]!=norm_cfg.get(k)}
            assert not delta,(pid,delta)
            # This headless Studio can load/export but cannot initialize thumbnail OpenGL.
            # Remove only generated preview/cache references from a validation copy; never alter delivered projects.
            models_before={k:v for k,v in normalized.items() if k.endswith('.model')}
            b.clear_generated_data(normalized,geometry_changed=True)
            normalized[b.OBJECTS]=b.xml_bytes(b.clean_plate_cache(b.parse_xml(normalized[b.OBJECTS],b.OBJECTS),True))
            assert all(normalized[k]==v for k,v in models_before.items())
            norm=b.validate_project(normalized,layout=True)
            assert not norm['contains_toolpaths'] and len(norm['build_items'])==1
            for aa,bb in zip(generated['build_items'][0]['bounds_mm'],norm['build_items'][0]['bounds_mm']):
                assert all(abs(x-y)<0.002 for x,y in zip(aa,bb)),pid
            assert sum(m['triangles'] for m in norm['meshes'])==stats['triangles']
            plate=b.parse_xml(normalized[b.OBJECTS],b.OBJECTS).find('plate')
            if right:assert any(m.get('key')=='filament_map_mode' and m.get('value')=='Manual' for m in plate.findall('metadata'))
            studio_result={'verified':True,'version':'02.08.02.61','exit_code':0,'generated_settings_unchanged':True,'added_bookkeeping_keys':sorted(set(norm_cfg)-set(cfg)),'geometry_bounds_preserved_tolerance_mm':.002,'triangles_preserved':True,'contains_toolpaths':False,'slicing_performed':False,'thumbnail_generation_verified':False,'validation_copy_generated_preview_references_removed':True}
        write(out/'verification'/f'{pid}.json',{'generated':generated,'studio':studio_result})
        summary.append({'part':pid,'file':'projects/'+filename,'sha256':digest(target),'objects_in_project':1,'structural':not pid.startswith(('pad-','washer-')),'quantity_in_p4_inventory':row['quantity'],'right_only':right,'source_rotation_degrees':row['rotation_degrees'],'additional_rotation_degrees':0,'bed_bounds_mm':generated['build_items'][0]['bounds_mm'],'settings_bytes_unchanged_from_original_template':False,'source_stl_sha256':digest(out/'input-stl'/f'{pid}.stl'),'brim_mm':0,'studio_load_export_verified':studio_result['verified']})
        print('PASS',pid,'Right-only' if right else 'Original template',flush=True)
    assert len(summary)==15 and sum(r['structural'] for r in summary)==12
    write(out/'PROJECTS.json',{'revision':'P5-H2D-3MF-PLA06-R1','unsliced':True,'projects':summary})
    print('All 15 printable types generated; no print job sent.')
if __name__=='__main__':main()
