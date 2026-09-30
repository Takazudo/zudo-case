"""Read-only adapter for the unchanged R6 source geometry.

R9 retains these nominal placements and changes 36 panel holes to slots. This
adapter regenerates the same placements with R6, then applies the R9 slot rule.
It does not claim to execute all of the independent R9 validator or its pipeline.
No files are written into r6-body; all legacy export hooks are redirected/disabled.
"""
from pathlib import Path
import hashlib, importlib.util, json, tempfile
import cadquery as cq
from .geometry import Body, Part, solid

EXPECTED_SOURCE_BLOBS={'build_geometry.py': '77c998e0bbdd4a390604b7724d8f2f17b3618ffe', 'design-parameters.json': 'c9a2fe501928856f850a26541fe9cd3048664f5f', 'source-data/panels/panel-geometry.json': '04836d809db024613023beba1cd5d355bf5eb184', 'source-data/rail40/rail_dimensions.json': '1c60b9076473bd36aab30765cbaa8c11ac03337b', 'source-data/rail40/rail_mesh.json': '178fd2e720d83b92f2430603e5592c5854ca2087', 'source-data/rail40/nuts-v2-40hp-single.stl': 'b10e9856af6bf75967936bda7537d12525992ffc'}
EXPECTED_GIT_BLOB=EXPECTED_SOURCE_BLOBS['build_geometry.py']

def load_reference(root: Path):
    root=Path(root).resolve();source=root/'build_geometry.py';raw=source.read_bytes()
    sha=hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()
    if sha!=EXPECTED_GIT_BLOB:
        raise ValueError('Reference generator differs from pinned 7f04c5b R6 source')
    for rel,expected in EXPECTED_SOURCE_BLOBS.items():
        content=(root/rel).read_bytes()
        if hashlib.sha1(f'blob {len(content)}\0'.encode()+content).hexdigest()!=expected:
            raise ValueError(f'Pinned reference input differs: {rel}')
    # R6's module initializer creates an engineering directory. Execute verified
    # bytes in a temporary mirror, so even its import-time mkdir is read-only
    # with respect to the preserved reference tree.
    with tempfile.TemporaryDirectory(prefix='zudo-fitfix-ref-') as tmp:
        temporary=Path(tmp)
        for rel in EXPECTED_SOURCE_BLOBS:
            dst=temporary/rel;dst.parent.mkdir(parents=True,exist_ok=True)
            dst.write_bytes((root/rel).read_bytes())
        spec=importlib.util.spec_from_file_location('fitfix_readonly_r6',temporary/'build_geometry.py')
        r6=importlib.util.module_from_spec(spec)
        exec(compile(raw,str(source),'exec'),r6.__dict__)
        r6.configure('7u40')
        def capture(shape,id,name,category,group='enclosure',explode=(0,0,0),**extra):
            r6.SHAPES[id]=shape
            return dict(id=id,name=name,category=category,group=group,**extra)
        r6.mesh_part=capture
        r6.export_solid=lambda *a,**kw:None
        r6.write_dxf=lambda *a,**kw:None
        r6.write_json=lambda *a,**kw:None
        entries=r6.common_geometry()
    return r6,entries


def slotted_plates(r6,entries):
    """Current R9 5.5 x 7.5 nominal slot rule on unchanged R6 hole centers."""
    parts=[];flat=[];hole_table=[]
    for e in entries:
        if e.get('role')!='aluminumPanel':continue
        kind=e['partType'];axis=e['panelAxis'];rows=[];rounds=[]
        if kind=='bottom':width,height=r6.W,r6.D
        elif kind=='front_back':width,height=r6.W-2*r6.T,r6.H-r6.T
        else:width,height=r6.D,r6.H-r6.T
        s=cq.Solid.makeBox(width,height,r6.T)
        for num,(x,y,z) in enumerate(e['holeCenters']):
            if kind=='bottom':u,v=x+r6.W/2,y+r6.D/2;is_round=False;ang=90 if abs(x) in [abs(i) for i in r6.BOTTOM_XS] else 0
            elif kind=='front_back':u,v=x+r6.XM,z-r6.T;is_round=False;ang=90 if abs(z-(r6.T+r6.INSET))<1e-6 else 0
            else:u,v=y+r6.D/2,z-r6.T;is_round=abs(z-r6.MOUNT_Z)<1e-6;ang=90 if abs(z-(r6.T+r6.INSET))<1e-6 else 0
            if is_round:
                cut=cq.Solid.makeCylinder(2.75,r6.T+2,cq.Vector(u,v,-1));rounds.append((u,v,5.5))
            else:
                cut=cq.Workplane('XY',origin=(0,0,-1)).center(u,v).slot2D(7.5,5.5,ang).extrude(r6.T+2).val();rows.append((u,v,7.5,5.5,ang))
            s=s.cut(cut)
            hole_table.append(dict(panel=e['id'],uv_mm=[u,v],profile='round' if is_round else 'slot',angle_deg=None if is_round else ang))
        s=solid(s)
        if kind=='bottom':placed=s.translate((-r6.W/2,-r6.D/2,0))
        elif kind=='front_back':
            ypos=-r6.YM if e['id']=='metal-front' else r6.D/2
            placed=s.rotate((0,0,0),(1,0,0),90).translate((-width/2,ypos,r6.T))
        elif e['id']=='metal-right':
            placed=s.rotate((0,0,0),(1,1,1),120).translate((r6.XM,-r6.D/2,r6.T))
        else:
            right=s.rotate((0,0,0),(1,1,1),120).translate((r6.XM,-r6.D/2,r6.T));placed=right.mirror('YZ')
        parts.append(Part(e['id'],solid(placed),1,'A5052 t1.5 reference slot candidate','metal'))
        if e['id'] in ('metal-bottom','metal-front','metal-right'):
            flat.append(dict(id=kind,shape=s,width=width,height=height,quantity=1 if kind=='bottom' else 2,holes=rounds,slots=rows))
    assert len(hole_table)==46 and sum(h['profile']=='slot' for h in hole_table)==36
    return parts,flat,hole_table
