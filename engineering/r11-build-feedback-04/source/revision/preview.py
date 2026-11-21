"""Mesh the exact CAD for a self-contained, dependency-free review viewer.

Close-up meshes are actual BRep sections, not illustrative proxy geometry.
The original rail-frame meshes are preserved verbatim in the assembled scene.
Only their close-up copies are clipped against the indicated view box.
"""
from __future__ import annotations
import hashlib, json, math
from pathlib import Path
import cadquery as cq
from .core import ROOT, P, box, bounds


def intersects(a, b):
    return all(min(a[k + 3], b[k + 3]) > max(a[k], b[k]) + 1e-7 for k in range(3))


def clip_mesh(mesh, bb):
    """Sutherland-Hodgman clipping of source triangles to six section planes."""
    points, faces = [], []
    raw, indices = mesh['p'], mesh['i']
    lookup = {}
    def vertex(p):
        p = tuple(round(float(c), 5) for c in p)
        if p not in lookup:
            lookup[p] = len(points) // 3
            points.extend(p)
        return lookup[p]
    for i in range(0, len(indices), 3):
        poly = [raw[3*j:3*j+3] for j in indices[i:i+3]]
        for axis in range(3):
            for is_min in (True, False):
                if not poly: break
                value = bb[axis if is_min else axis + 3]
                def inside(p): return p[axis] >= value - 1e-9 if is_min else p[axis] <= value + 1e-9
                result = []
                a = poly[-1]
                for b in poly:
                    ai, bi = inside(a), inside(b)
                    if ai != bi:
                        t = (value - a[axis]) / (b[axis] - a[axis])
                        result.append([a[k] + t * (b[k] - a[k]) for k in range(3)])
                    if bi: result.append(b)
                    a = b
                poly = result
        if len(poly) < 3: continue
        for j in range(1, len(poly) - 1):
            tri = [vertex(v) for v in (poly[0], poly[j], poly[j+1])]
            if len(set(tri)) == 3: faces.extend(tri)
    return dict(p=points, i=faces)


def mesh_bounds(mesh):
    p=mesh['p']
    return [min(p[k::3]) for k in range(3)] + [max(p[k::3]) for k in range(3)]


def make_preview(parts, body_meta, lid_meta, out):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    reference = json.loads((ROOT / 'reference' / 'source-frame.json').read_text())
    meshes = dict(reference['meshes'])
    full, solids = [], {}
    def add_mesh(mesh):
        key = hashlib.sha256(json.dumps(mesh, separators=(',', ':')).encode()).hexdigest()[:16]
        meshes.setdefault(key, mesh)
        return key
    def cad_item(p, shape=None, suffix=''):
        shape = p['shape'] if shape is None else shape
        # Keep display meshing independent of finer STL-export triangulations.
        display_shape=shape.copy(mesh=False)
        vs, ts = display_shape.tessellate(.09, .26)
        mesh = dict(p=[round(float(v), 5) for pt in vs for v in pt.toTuple()], i=[i for t in ts for i in t])
        q = {k: v for k, v in p.items() if k != 'shape'}
        q.update(id=p['id']+suffix, mesh=add_mesh(mesh), box=[round(v, 5) for v in bounds(shape)],
                 volume_mm3=round(shape.Volume(), 5), solids=len(shape.Solids()))
        if suffix:
            q['source_part_id'] = p['id']
            q['note'] = '切り出し表示（端面は表示用）。' + q.get('note', '')
        return q
    for p in parts:
        q=cad_item(p);full.append(q);solids[p['id']]=p
    source = reference['items']
    assembly = full + source
    def crop(key, bb, include=None, sources=False):
        cutter = box(bb[0], bb[3], bb[1], bb[4], bb[2], bb[5])
        items=[]
        for q in full:
            if include and not include(q): continue
            if not intersects(q['box'], bb): continue
            p=solids[q['id']]
            cut=p['shape'].intersect(cutter)
            if cut.Volume()>1e-6:items.append(cad_item(p,cut,'@'+key))
        if sources:
            for q in source:
                if not intersects(q['box'],bb):continue
                m=clip_mesh(meshes[q['mesh']],bb)
                if not m['i']:continue
                items.append(dict(q,id=q['id']+'@'+key,source_part_id=q['id'],mesh=add_mesh(m),box=mesh_bounds(m),
                                  note=q.get('note','')+' / clipped source mesh for this view'))
        return items
    no_lid = lambda q: not q['cat'].startswith('lid')
    scenes={
        'lidguides':[q for q in full if q['cat']=='lidFrame'],
        'lidfit':crop('lidfit',[104,70,74,117,115,97],sources=True),
        'inside':[q for q in full if q['cat'] in ('corner','span','panels')],
        'assembly':assembly,
        'nylon':[q for q in full if q['cat'] in ('corner','span')],
        'panels':[q for q in full if q['cat']=='panels'],
        'lid':[q for q in full if q['cat'].startswith('lid')],
        'corner':crop('corner',[75,-171,-3,119,-125,94],lambda q:no_lid(q) and q['role']!='foot'),
        'top':crop('top',[39,-172,60,80,-143,96],no_lid,True),
        'lap':crop('lap',[39,-174,-4,80,-130,35],no_lid),
        'lidjoint':crop('lidjoint',[17,-173,78,54,-141,130],lambda q:q['cat'].startswith('lid')),
        'slots':crop('slots',[40,-168,0,114,-164,91],lambda q:q['cat']=='panels'),
        'rail':crop('rail',[91,-82,57,123,-52,91],no_lid,True),
    }
    # Illustrative local separation: the close-ups must reveal both leaves,
    # rather than translating two mating lid pieces by the same vector.
    for view in ('top','lap'):
        for q in scenes[view]:
            if q['cat']=='panels':q['explode']=[0,0,0]
            elif q['cat']=='span':q['explode']=[0,0,3] if view=='top' else [-1.5,-2,-1.5]
            elif q['cat']=='corner':q['explode']=[1.3,-1,0] if view=='top' else [1.5,-1,-.5]
            elif q['cat']=='brackets':q['explode']=[0,1,1]
            elif q['cat']=='sourceFrame':q['explode']=[0,0,0]
    for q in scenes['lidjoint']:
        ident=q['id']
        if q['cat']=='lidFrame':q['explode']=[-1.3,-1.5,0] if 'corner' in ident else [1.3,1.5,0]
        elif q['cat']=='lidMetal':q['explode']=[0,0,3]
        elif 'plate-screw' in ident:q['explode']=[0,0,5]
        elif 'plate-nut' in ident:q['explode']=[0,0,-3]
        elif 'wall-screw' in ident:q['explode']=[0,-3,0]
        elif 'wall-nut' in ident:q['explode']=[0,3,0]
        elif 'outer' in ident:q['explode']=[0,-2.5,0]
        elif 'inner' in ident:q['explode']=[0,2.5,0]
    for q in scenes['lidfit']:
        q['explode']=[0,0,2] if q['cat'].startswith('lid') else [0,0,0]
    parameters=dict(P)
    parameters['viewer_rows']=[
        ['本体外形','229.4 × 334 × 91 mm'],['板厚','1.5 mm'],
        ['本体 / 蓋の3DP部品','12 / 8'],['長穴','15.5 × 5.5 mm'],
        ['追加方向','板端から内側へ +5 mm'],['本体の重ね耳','1 + 1 mm'],
        ['位置決め壁 / 板間','0.8 / 1.0 mm'],['丸ワッシャー','Ø15 / Ø5 / t1 mm'],
        ['側面の接合位置','Y ±95 mm'],['蓋の重ね耳','1.5 + 1.5 mm'],
        ['追加した内側の耳','32箇所'],['本体内側の独立ワッシャー','上端8個'],
        ['内側の耳','1.0 mm'],
        ['蓋の内側ガイド','前・後・左・右'],['ガイドの掛かり / 厚さ','12 / 2 mm'],
        ['ガイドの公称隙間','0.7 mm'],['内側金具の逃げ','18 mm × 8箇所'],
    ]
    data=dict(revision=P['revision'],parameters=parameters,meshes=meshes,scenes=scenes,
              body_metadata=body_meta,lid_metadata=lid_meta,
              coordinates='millimetres; X width, Y depth, Z up; floor underside Z=0',
              source=reference['provenance'])
    raw=json.dumps(data,ensure_ascii=False,separators=(',',':'))
    (out/'scene.json').write_text(raw,encoding='utf-8')
    html=(ROOT/'revision/viewer.html').read_text()
    assert html.count('__MODEL__')==1
    (out/'preview.html').write_text(html.replace('__MODEL__',raw.replace('</','<\\/')),encoding='utf-8')
    report=dict(scene_parts={k:len(v) for k,v in scenes.items()},mesh_count=len(meshes),
                triangles=sum(len(m['i'])//3 for m in meshes.values()),scene_json_bytes=len(raw.encode()),
                source_frame_meshes_unchanged=all(meshes[k]==m for k,m in reference['meshes'].items()),
                prototype='CAD-derived mesh viewer; cropped scenes are inspection sections, not additional physical parts')
    (out/'preview-manifest.json').write_text(json.dumps(report,indent=2))
    return report
