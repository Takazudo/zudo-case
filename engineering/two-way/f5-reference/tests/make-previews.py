"""Render current offline viewer and an A/B/C comparison. Requires Playwright and Pillow."""
from pathlib import Path
import json, base64
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'previews';OUT.mkdir(exist_ok=True)
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage'])
    page=b.new_page(viewport={'width':1500,'height':1060},device_scale_factor=1)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content((ROOT/'zudo-case-F5.html').read_text(),wait_until='load')
    page.wait_for_function('window.FoldApp?.ready')
    def state(v):
        page.evaluate('(v)=>FoldApp.setState(v)',v)
        page.wait_for_function('!FoldApp.pending');page.wait_for_timeout(160)
    def canvas_image(path):
        data=page.evaluate('document.getElementById("viewer").toDataURL("image/png")')
        path.write_bytes(base64.b64decode(data.split(',',1)[1]))
    for fam in ['compact','performance','twin40']:
        page.locator(f'[data-family="{fam}"]').click()
        for pose in ['frame','play','closed']:
            state({'pose':pose,'view':'iso','frameExplode':0,'cutaway':False,'structure':False})
            page.locator('#stage').screenshot(path=str(OUT/f'{fam}-{pose}.png'))
            canvas_image(OUT/f'{fam}-{pose}-canvas.png')
    page.locator('[data-family="performance"]').click()
    for pose in ['frame','closed','trunk']:
        state({'pose':pose,'view':'iso','frameExplode':0})
        canvas_image(OUT/f'{pose}-thumb-source.png')
    state({'pose':'frame','frameExplode':10})
    page.locator('#stage').screenshot(path=str(OUT/'B-exploded.png'))
    page.locator('[data-family="twin40"]').click()
    state({'pose':'frame','view':'side','frameExplode':0})
    page.locator('#stage').screenshot(path=str(OUT/'C-frame-side.png'))
    state({'lidDepth':48,'pose':'closed','cutaway':True,'structure':True})
    page.screenshot(path=str(OUT/'C-rejected-48mm.png'))
    page.locator('[data-family="performance"]').click()
    state({'pose':'joint','view':'side','jointLift':10,'cutaway':False,'structure':False})
    page.locator('#stage').screenshot(path=str(OUT/'B-joint.png'))
    page.locator('#reset').click();page.wait_for_function('!FoldApp.pending');page.wait_for_timeout(300)
    page.screenshot(path=str(OUT/'workbench-desktop.png'))
    page.set_viewport_size({'width':390,'height':940});page.wait_for_timeout(300)
    page.screenshot(path=str(OUT/'workbench-mobile.png'))
    assert not errors,errors
    (OUT/'preview-render.json').write_text(json.dumps({'revision':'F5','renderer':page.evaluate('FoldApp.viewer.mode'),'javascriptErrors':errors},indent=2)+'\n')
    b.close()

def tight(im):
    a=np.asarray(im.convert('RGB'));bg=a[0,0].astype(int)
    ys,xs=np.where(np.max(np.abs(a.astype(int)-bg),axis=2)>25)
    if not len(xs):return im
    pad=25
    return im.crop((max(0,int(xs.min())-pad),max(0,int(ys.min())-pad),min(im.width,int(xs.max())+pad),min(im.height,int(ys.max())+pad)))

def font(size,bold=False):
    return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans'+('-Bold' if bold else '')+'.ttf',size)

BG='#eff1ed';INK='#22302c';MUTED='#68736c';LINE='#cbd1c9';ACCENT='#a64c24'
canvas=Image.new('RGB',(1800,1370),BG);draw=ImageDraw.Draw(canvas)
draw.text((48,30),'ZUDO CASE / F5',font=font(19,True),fill=MUTED)
draw.text((48,65),'Original rail frames, in both trays',font=font(38,True),fill=INK)
draw.text((48,117),'Source rails are unscaled. Frames below are shown per tray; playing views show the complete instrument.',font=font(19),fill=MUTED)
cols=[('compact','A  /  3U + 3U · 60HP','One original 3U frame per tray','48 mm lid rear depth'),('performance','B  /  6U + 6U · 60HP','Two original 3U frames per tray','48 mm lid · 1 mm frame-to-frame gap'),('twin40','C  /  7U + 7U · 40HP','Original 7U side board + row padders','70 mm lid · full-depth board retained')]
for i,(fam,title,desc,note) in enumerate(cols):
    x=48+i*576
    draw.line((x,168,x+552,168),fill=LINE,width=2)
    draw.text((x,186),title,font=font(24,True),fill=INK)
    draw.text((x,222),desc,font=font(17),fill=MUTED)
    im=tight(Image.open(OUT/f'{fam}-frame-canvas.png').convert('RGB'))
    im.thumbnail((552,450),Image.Resampling.LANCZOS)
    canvas.paste(im,(x+(552-im.width)//2,250+(450-im.height)//2))
    draw.text((x,720),'PLAYING ARRANGEMENT',font=font(15,True),fill=MUTED)
    im=tight(Image.open(OUT/f'{fam}-play-canvas.png').convert('RGB'))
    im.thumbnail((552,430),Image.Resampling.LANCZOS)
    canvas.paste(im,(x+(552-im.width)//2,751+(430-im.height)//2))
    draw.text((x,1203),note,font=font(17,True),fill=ACCENT)
draw.line((48,1252,1752,1252),fill=LINE,width=2)
draw.text((48,1274),'PINNED SOURCE 6a13d80   ·   1.6 + 1.6 mm PCB layers   ·   8 mm side spacers',font=font(18),fill=INK)
draw.text((48,1306),'PCB rounded cutouts are display approximations. This is a dimensional study, not manufacturing or load approval.',font=font(17),fill=MUTED)
canvas.save(OUT/'F5-frame-overview.png')
for name in ['frame','closed','trunk']:
    im=tight(Image.open(OUT/f'{name}-thumb-source.png').convert('RGB'))
    im.thumbnail((600,400),Image.Resampling.LANCZOS)
    im.save(OUT/f'{name}-thumb.webp',quality=84)
print('Rendered final F5 views, clean workbench screenshots, overview and three thumbnails.')
