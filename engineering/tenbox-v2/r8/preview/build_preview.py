"""Build a self-contained R8 review from the versioned CAD meshes.

Only display meshes are rounded/deduplicated; source STEP/STL bytes are not
modified. The exact renderer is reused from the frozen R5 dependency.
"""
from pathlib import Path
import argparse
import base64
import copy
import gzip
import hashlib
import json

ROOT = Path(__file__).resolve().parent
R5 = ROOT.parents[1] / 'r5/source'


def encode_payload(data):
    """Losslessly delta-code triangle indices before gzip; retain all geometry."""
    wire = copy.deepcopy(data)
    wire['meshEncoding'] = {'indices':'delta-v1','positions':'millimeters'}
    for shape in wire['meshes'].values():
        indices = shape['i']
        deltas = [value-(indices[index-1] if index else 0) for index,value in enumerate(indices)]
        total = 0
        for value,delta in zip(indices,deltas):
            total += delta
            if total != value:
                raise ValueError('Triangle-index encoding changed the source topology')
        shape['i'] = deltas
    raw = json.dumps(wire,separators=(',',':'),ensure_ascii=False).encode()
    return base64.b64encode(gzip.compress(raw,compresslevel=9,mtime=0)).decode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--inline-out', type=Path)
    parser.add_argument('--data-out', type=Path)
    args = parser.parse_args()
    original = json.loads(args.model.read_text())
    data = {k:copy.deepcopy(original[k]) for k in ['schema','revision','units','coordinates','production_approved','meshes','parts','baselineParts','dimensions','mountParameters','sideFixingParameters','bracketParameters','jointScenes','baselineJointScenes','railLayout','previewMetadata','lidClearance'] if k in original}
    data.setdefault('jointScenes', {})
    data.setdefault('baselineJointScenes', {})
    data.setdefault('previewMetadata', {}).update({'sourceModelSha256':hashlib.sha256(args.model.read_bytes()).hexdigest(), 'physicalFitVerified':False})
    if not data.get('baselineParts'):
        raise ValueError('The CAD model must include the exact R7 baseline assembly.')
    body_ids = {'body-left','body-right','body-front','body-back','body-bottom-front','body-bottom-back'}
    records = data['parts'] + data['baselineParts'] + [p for scenes in [data['jointScenes'],data['baselineJointScenes']] for scene in scenes.values() for p in scene]
    for part in records:
        part.setdefault('sourceId',part['id'])
        if part['sourceId'] in body_ids:
            part['cat'] = 'floor' if 'bottom' in part['sourceId'] else 'panels'
            part['group'] = 'body'
        elif part['sourceId'].startswith('lid-'):
            part['group'] = 'lid'
            part['cat'] = 'lidRoof' if 'top' in part['sourceId'] else 'lidEdges'
        elif part['sourceId'].startswith('stand-'):
            part['group'] = 'stand'
        if max(abs(v) for v in part.get('explode',[0,0,0])) > 3:
            part['explode'] = [v/65 for v in part['explode']]
    referenced = {p['mesh'] for p in records}
    # Keep the three inspectable detail scenes, including their exact R7 comparison.
    for key in ['jointScenes','baselineJointScenes']:
        data[key] = {k:v for k,v in data[key].items() if k in ['side-fixing','rail-junction','lower-slot']}
    records = data['parts'] + data['baselineParts'] + [p for scenes in [data['jointScenes'],data['baselineJointScenes']] for scene in scenes.values() for p in scene]
    referenced = {p['mesh'] for p in records}
    placements = [(part, part['mesh'], list(part.get('staticOffset',[0,0,0]))) for part in records]
    unique, aliases, canonical, origins = {}, {}, {}, {}
    maximum_rebase_error = 0.0
    for key in sorted(referenced):
        mesh = data['meshes'][key]
        world = [round(float(x),3) for x in mesh['p']]
        origin = [min(world[axis::3]) for axis in range(3)]
        local = [round(value-origin[index%3],3) for index,value in enumerate(world)]
        local = [0.0 if value == 0 else value for value in local]
        maximum_rebase_error = max(maximum_rebase_error, max(abs(value+origin[index%3]-world[index]) for index,value in enumerate(local)))
        origins[key] = origin
        rounded = {'p':local, 'i':mesh['i']}
        digest = hashlib.sha256(json.dumps(rounded,separators=(',',':')).encode()).hexdigest()
        target = canonical.setdefault(digest,key)
        aliases[key] = target
        if key == target: unique[key] = rounded
    # Exact rigid translations allow identical fasteners/rails to share one mesh.
    # The same existing 0.001 mm display precision is kept; CAD exports are untouched.
    assert maximum_rebase_error < 1e-7
    for part in records:
        origin = origins[part['mesh']]
        part['staticOffset'] = [part.get('staticOffset',[0,0,0])[axis]+origin[axis] for axis in range(3)]
        part['box'] = [value-origin[index%3] for index,value in enumerate(part['box'])]
        part['mesh'] = aliases[part['mesh']]
    maximum_world_error = 0.0
    for part, old_key, old_offset in placements:
        source, packed = data['meshes'][old_key], unique[part['mesh']]
        if source['i'] != packed['i'] or len(source['p']) != len(packed['p']):
            raise ValueError('Display mesh topology changed for '+part['id'])
        maximum_world_error = max(maximum_world_error, max(abs(value+part['staticOffset'][index%3]-source['p'][index]-old_offset[index%3]) for index,value in enumerate(packed['p'])))
    if maximum_world_error > 0.0005001:
        raise ValueError(f'Display placement differs from CAD by {maximum_world_error} mm')
    data['previewMetadata']['meshInstancing'] = {'maximumRebaseErrorMm':maximum_rebase_error, 'sourceMeshCount':len(referenced), 'uniqueMeshCount':len(unique), 'displayPrecisionMm':0.001}
    data['previewMetadata']['meshIdentity'] = {'partsCompared':len(records),'triangleIndicesPreserved':True,'maximumWorldVertexErrorMm':maximum_world_error,'sourceGeometryRescaled':False}
    data['meshes'] = unique
    raw = json.dumps(data, separators=(',',':'), ensure_ascii=False).encode()
    encoded = encode_payload(data)
    reference = (R5 / 'research/zudo-case/viewer-template.html').read_text()
    core = reference[reference.index('const vsrc='):reference.index('function sceneKey()')]
    render = reference[reference.index('function drawPart('):reference.index('function tick()')]
    render = render.replace('gl.clearColor(.918,.941,.945,1)','gl.clearColor(.87451,.91373,.90588,1)')
    render = render.replace('rgba[k]=234;rgba[k+1]=240;rgba[k+2]=241','rgba[k]=223;rgba[k+1]=233;rgba[k+2]=231')
    render = render.replace('vv=V.norm(V.sub(eye,centroid))','vv=state.ortho?V.mul(forward,-1):V.norm(V.sub(eye,centroid))')
    render = render.replace("['panels','floor','lidRoof']","['panels','floor','lidRoof','lidEdges']")
    app = (ROOT / 'viewer-app.js').read_text().replace('__ENGINE_CORE__',core).replace('__ENGINE_RENDER__',render)
    fragment = (ROOT / 'tenbox-v2-template.html').read_text().replace('__MODEL_GZIP__',encoded).replace('__VIEWER_SCRIPT__',app)
    html = '<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>10BOX v2 · R8 lower-slot mounting and R7 comparison</title><style>html,body{margin:0;min-height:100%;background:#e8eeeb}body{padding:16px;max-width:1500px;margin:auto}.cursor-interaction{cursor:pointer}@media(max-width:600px){body{padding:0}}</style></head><body>\n'+fragment+'\n</body></html>\n'
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(html)
    inline_fragment = fragment
    if args.inline_out:
        # R7 and R8 reuse the exact same printed geometry and source meshes.
        # Keep both versions available inline; deduplication above preserves
        # triangle topology and proves every world-space vertex within 0.001 mm.
        inline_fragment = fragment
        if len(inline_fragment.encode()) >= 1024*1024:
            raise ValueError(f'Inline preview exceeds 1 MiB: {len(inline_fragment.encode())} bytes')
        args.inline_out.parent.mkdir(parents=True,exist_ok=True)
        args.inline_out.write_text(inline_fragment)
    if args.data_out:
        args.data_out.parent.mkdir(parents=True,exist_ok=True)
        args.data_out.write_bytes(raw)
    print(json.dumps({'html':str(args.out),'html_bytes':len(html.encode()),'inline_bytes':len(inline_fragment.encode()),'mesh_count':len(unique),'part_count':len(data['parts']),'source_sha256':data['previewMetadata']['sourceModelSha256']}))

if __name__ == '__main__':main()
