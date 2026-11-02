"""Accepted J3 additions to freshly generated P4 solids; millimetres/world axes."""
import cadquery as cq


def box(x0, x1, y0, y1, z0, z1):
    return cq.Solid.makeBox(x1-x0, y1-y0, z1-z0, cq.Vector(x0,y0,z0))


def validate(p):
    expected={'end_tab_centers_z':[24,55],'floor_tab_centers_y':[-100,-60,60,100],
              'slot_clearance_each':.2,'receiver_corner_radius':.4,'shoulder_x':113.05,
              'tab_root_x':112.9,'tab_tip_x':117.9,
              'outline_yz':[[-170.5,-3.5],[-170.5,10],[-174.5,14],[-174.5,78.5],
                            [-170.5,82.5],[-170.5,94.5],[170.5,94.5],[170.5,82.5],
                            [174.5,78.5],[174.5,14],[170.5,10],[170.5,-3.5]]}
    if p.get('joint') != expected or p['printer']['brim_allowance_each_side'] != 0:
        raise ValueError('Unreviewed J3 joint or brim parameters')


def apply(s, pid, p):
    validate(p)
    j = p['joint']
    if pid in ('wall-left', 'wall-right'):
        x = 113.2 if pid == 'wall-right' else -118.2
        # Add only outside the original slab, retaining its small corner radii.
        regions = [
            [(-170.5,-3.5),(170.5,-3.5),(170.5,5),(-170.5,5)],
            [(-170.5,10),(-174.5,14),(-174.5,78.5),(-170.5,82.5)],
            [(170.5,10),(174.5,14),(174.5,78.5),(170.5,82.5)],
        ]
        for region in regions:
            wire = cq.Wire.makePolygon([cq.Vector(x,y,z) for y,z in region],close=True)
            s = s.fuse(cq.Solid.extrudeLinear(wire,[],cq.Vector(5,0,0)))
        windows = [(y,z,5,12) for y in (-168,168) for z in j['end_tab_centers_z']]
        windows += [(y,2.5,20,5) for y in j['floor_tab_centers_y']]
        for y,z,w,h in windows:
            c = j['slot_clearance_each']
            cutter = (cq.Workplane('YZ',origin=(x-1,y,z)).rect(w+2*c,h+2*c)
                      .extrude(7).edges('|X').fillet(j['receiver_corner_radius']).val())
            s = s.cut(cutter)
    elif pid in ('wall-front', 'wall-back', 'floor-1', 'floor-2'):
        s = s.intersect(box(-j['shoulder_x'],j['shoulder_x'],-180,180,-1,100))
        for sign in (-1,1):
            x0,x1 = sorted((sign*j['tab_root_x'],sign*j['tab_tip_x']))
            if pid.startswith('floor'):
                ys = [y for y in j['floor_tab_centers_y'] if (y<0)==(pid=='floor-1')]
                tabs = [box(x0,x1,y-10,y+10,0,5) for y in ys]
            else:
                y0,y1 = (-170.5,-165.5) if pid=='wall-front' else (165.5,170.5)
                tabs = [box(x0,x1,y0,y1,z-6,z+6) for z in j['end_tab_centers_z']]
            for tab in tabs:
                if s.intersect(tab).Volume() <= 0:
                    raise ValueError('Disconnected tab root: '+pid)
                s = s.fuse(tab)
    return s.clean()
