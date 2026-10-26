"""Live local MDX integration, responsive pages, iframe origin and download bytes."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import hashlib,json,os
root=Path(__file__).resolve().parents[1];base=os.environ.get('SITE_URL','http://localhost:4391');out=root/'.cache/p4-site-evidence';out.mkdir(exist_ok=True)
checks=[]
def check(label,passed):
    assert passed,label
    checks.append(label)
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True,args=['--no-sandbox','--enable-unsafe-swiftshader'])
    page=browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    for width in [1440,390,320]:
        page.set_viewport_size({'width':width,'height':1000})
        for slug in ['', 'p4-design/','p4-preview/','p4-print-files/','ventilation/']:
            response=page.goto(base+'/docs/printed-5mm/'+slug,wait_until='networkidle')
            check(f'{width}/{slug} HTTP',response.status==200)
            check(f'{width}/{slug} responsive',page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
            if slug=='p4-preview/':
                iframe=page.locator('iframe').first
                src=iframe.get_attribute('src')
                check(f'{width} same origin P4',src==base+'/previews/printed-5mm-p4-uniform-vents.html' or src=='/previews/printed-5mm-p4-uniform-vents.html')
                frame=iframe.content_frame
                frame.locator('[data-view="panel-front"]').click()
                frame.locator('#compareP3').check();frame.locator('#compareP3').uncheck()
                page.screenshot(path=str(out/f'docs-preview-{width}.png'),full_page=True)
    registry=json.loads((root/'project/printed-5mm/p4-uniform-vents/files.json').read_text())
    for f in registry['files']:
        if f['path'].startswith('public/'):
            response=page.request.get(base+'/'+f['path'][7:]);check('GET '+f['path'],response.status==200 and hashlib.sha256(response.body()).hexdigest()==f['sha256'])
    check('no page errors',not errors)
    (out/'checks.json').write_text(json.dumps({'passed':True,'checks':checks,'browser':browser.version},indent=2)+'\n')
    print('P4 local docs:',len(checks),'checks passed')
    browser.close()
