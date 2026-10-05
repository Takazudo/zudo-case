#!/usr/bin/env python3
"""Build the F5 offline workbench. Uses Python standard library only."""
from pathlib import Path
import base64, json
ROOT=Path(__file__).resolve().parent
# Keep closure changes editable separately from inherited tray / stand mesh code.
(ROOT/'source/geometry.js').write_text((ROOT/'source/base-geometry.inc').read_text()+(ROOT/'source/frame-geometry.inc').read_text()+(ROOT/'source/closure.js').read_text())
html=(ROOT/'source/index.template.html').read_text()
for key,name in [('FRAMEDATA','frame-data.js'),('FRAME','frame.js'),('STYLE','style.css'),('MODEL','model.js'),('RENDERER','renderer.js'),('GEOMETRY','geometry.js'),('APP','app.js')]:
    html=html.replace('/*'+key+'*/',(ROOT/'source'/name).read_text())
p=ROOT/'reference/hinge-user-dimensions.png'
html=html.replace('/*HINGEIMAGE*/','data:image/png;base64,'+base64.b64encode(p.read_bytes()).decode())
thumbs={}
for name in ['frame','closed','trunk']:
    p=ROOT/'previews'/f'{name}-thumb.webp'
    if p.exists():thumbs[name]='data:image/webp;base64,'+base64.b64encode(p.read_bytes()).decode()
html=html.replace('/*THUMBS*/','window.FOLD_THUMBS='+json.dumps(thumbs)+';')
if any('/*'+k+'*/' in html for k in ['FRAMEDATA','FRAME','STYLE','MODEL','RENDERER','GEOMETRY','APP','THUMBS','HINGEIMAGE']):
    raise RuntimeError('Unresolved build placeholder')
(ROOT/'zudo-case-F5.html').write_text(html)
print('Built',len(html.encode()),'bytes')
