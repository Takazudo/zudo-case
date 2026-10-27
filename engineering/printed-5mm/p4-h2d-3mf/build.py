"""Build one editable, unsliced H2D project per P4 printable type."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys,zipfile
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
import bambu_3mf as b

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,value):p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);p.add_argument('--studio',type=Path);a=p.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    if any(out.iterdir()):raise SystemExit('Output must be empty')
    for folder in ('projects','manifests','verification'):(out/folder).mkdir()
    for folder in ('input-stl','template'):shutil.copytree(ROOT/folder,out/folder)
    receipt=json.loads((ROOT/'SOURCE-RECEIPT.json').read_text())
    for f in receipt['sources']:assert digest(ROOT/f['path'])==f['sha256'],f['path']
    inventory=json.loads((ROOT/'inventory.json').read_text());summary=[]
    original=b.read_archive(ROOT/'template/h2d-empty-original.3mf');original_cfg=b.settings(original)
    assert hashlib.sha256(original[b.SETTINGS]).hexdigest()==receipt['template_project_settings_sha256']
    studio=a.studio.resolve() if a.studio else None
    for row in inventory:
        pid=row['id'];right=pid in ('wall-left','wall-right')
        template_name='h2d-empty-right.3mf' if right else 'h2d-empty-original.3mf'
        template=out/'template'/template_name
        vertices,triangles,stats=b.read_mesh(str(ROOT/'input-stl'/f'{pid}.stl'),ROOT)
        lo,hi=b.bbox(vertices);w,h,z=[hi[i]-lo[i] for i in range(3)]
        # Keep flat P4 meshes without additional rotation/scaling; move the 341mm walls into Right's 325mm region.
        xy=[25+(325-w)/2,5] if right else [25+(300-w)/2,(310-h)/2]
        manifest={'schema_version':1,'title':f'P4 {pid} / H2D / unsliced','description':'P4 geometry unchanged. Settings retained; user will configure print details. No toolpaths.','margin_mm':5,'gap_mm':6,'objects':[{'name':f'P4 {pid}','mesh':f'../input-stl/{pid}.stl','filament':1,'position_mm':xy,'rotate_z_degrees':0}]}
        mf=out/'manifests'/f'{pid}.json';write(mf,manifest)
        filename=f'p4-{pid}-h2d-'+('right-' if right else '')+'pla06.3mf'
        target=out/'projects'/filename
        generated=b.create(template,mf,target);generated.pop('output',None)
        data=b.read_archive(target);cfg=b.settings(data)
        expected_changes={'filament_map','filament_map_mode'} if right else set()
        changed={k for k in cfg.keys()|original_cfg.keys() if cfg.get(k)!=original_cfg.get(k)}
        assert changed==expected_changes,(pid,changed)
        if not right:assert data[b.SETTINGS]==original[b.SETTINGS]
        else:
            plate=b.parse_xml(data[b.OBJECTS],b.OBJECTS).find('plate')
            assert any(m.get('key')=='filament_map_mode' and m.get('value')=='Manual' for m in plate.findall('metadata'))
            assert cfg['filament_map']==['2','2']
        assert generated['contains_toolpaths'] is False and len(generated['build_items'])==1
        generated['original_template_changed_keys']=sorted(changed)
        studio_result={'verified':False}
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
        summary.append({'part':pid,'file':'projects/'+filename,'sha256':digest(target),'objects_in_project':1,'structural':not pid.startswith(('pad-','washer-')),'quantity_in_p4_inventory':row['quantity'],'right_only':right,'source_rotation_degrees':row['rotation_degrees'],'additional_rotation_degrees':0,'bed_bounds_mm':generated['build_items'][0]['bounds_mm'],'settings_bytes_unchanged_from_original_template':not right,'studio_load_export_verified':studio_result['verified']})
        print('PASS',pid,'Right-only' if right else 'Original template',flush=True)
    assert len(summary)==15 and sum(r['structural'] for r in summary)==12
    write(out/'PROJECTS.json',{'revision':'P4-H2D-3MF-PLA06-R1','unsliced':True,'projects':summary})
    print('All 15 printable types generated; no print job sent.')
if __name__=='__main__':main()
