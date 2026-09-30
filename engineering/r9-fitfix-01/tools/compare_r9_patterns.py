#!/usr/bin/env python3
"""Read-only local comparison: the unchanged body DXF patterns must match R9.

Usage: uv run --project ../../r9-prototype-01 python compare_r9_patterns.py
Run from any CWD; paths derive from this file. --upstream/--fixed override dirs.
This tests drawing entities, not mechanical adequacy or vendor tolerances.
"""
import argparse,json,hashlib
from pathlib import Path
import ezdxf
ROOT=Path(__file__).resolve().parents[1]

def signature(path):
    doc=ezdxf.readfile(path)
    if doc.units!=4:raise ValueError(f'Not mm: {path}')
    out=[]
    def n(x):return round(float(x),6)
    for e in doc.modelspace():
        t=e.dxftype()
        if t=='LINE':out.append([t,sorted([[n(x) for x in e.dxf.start],[n(x) for x in e.dxf.end]])])
        elif t=='ARC':out.append([t,[n(x) for x in e.dxf.center],n(e.dxf.radius),n(e.dxf.start_angle%360),n(e.dxf.end_angle%360)])
        elif t=='CIRCLE':out.append([t,[n(x) for x in e.dxf.center],n(e.dxf.radius)])
        elif t=='LWPOLYLINE':out.append([t,bool(e.closed),sorted([[n(x) for x in row] for row in e.get_points('xyb')])])
        else:raise ValueError(f'Unaccounted geometric entity {t}: {path}')
    return sorted(out,key=lambda x:json.dumps(x,sort_keys=True))

def main():
    p=argparse.ArgumentParser();p.add_argument('--upstream',type=Path,default=ROOT.parent/'r9-prototype-01/out/aluminum');p.add_argument('--fixed',type=Path,default=ROOT/'out/aluminum/body');a=p.parse_args()
    rows=[]
    for old,new,qty in [('bottom','bottom',1),('front-back','front_back',2),('left-right','left_right',2)]:
        upstream=a.upstream/f'7u40-r9-al-{old}-qty{qty}-mm.dxf'
        fixed=a.fixed/f'7u40-r9f-body-{new}-qty{qty}-mm.dxf'
        repo=ROOT.parents[1]
        def record(p):
            try: name=p.resolve().relative_to(repo).as_posix()
            except ValueError: name=str(p.resolve())
            return dict(path=name,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        rows.append(dict(upstream=record(upstream),fixed=record(fixed),matched=signature(upstream)==signature(fixed)))
    print(json.dumps({'scope':'body drawing geometry only','patterns':rows,'passed':all(x['matched'] for x in rows)},indent=2))
    if not all(x['matched'] for x in rows):raise SystemExit(1)
if __name__=='__main__':main()
