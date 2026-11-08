"""Chromium rendering, integrated iframe and full built-site download verification."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import hashlib, io, json, os, zipfile
ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get('SITE_URL', 'http://localhost:4391').rstrip('/')
BUILT = os.environ.get('BUILT_URL', 'http://localhost:4393').rstrip('/')
OUT = Path(os.environ.get('EVIDENCE_DIR', str(ROOT/'.cache/tenbox-browser')))
OUT.mkdir(parents=True, exist_ok=True)
checks = []
def check(label, value):
    assert value, label
    checks.append(label)

def scene_checks(page, label):
    page.wait_for_function('window.tenboxStudy && document.querySelector("[data-ready=true]")')
    check(label+' renderer', page.evaluate('tenboxStudy.renderer') == label.split('/')[0])
    images = set()
    for scene in ['assembly', 'insert', 'front-joint', 'floor-joint', 'rail-gap', 'lid-fit', 'lid-ledge', 'floor-top', 'underside', 'floor-fit', 'h2d']:
        page.locator(f'[data-view="{scene}"]').click()
        page.wait_for_function('(scene) => tenboxStudy.state.view === scene && tenboxStudy.visibleParts().length > 0', arg=scene)
        page.evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
        canvas = page.locator('canvas').first
        shot = canvas.screenshot()
        images.add(hashlib.sha256(shot).hexdigest())
        check(label+'/'+scene+' canvas', len(shot) > 5000)
        if scene in ['assembly', 'floor-top', 'underside', 'floor-fit', 'h2d']:
            canvas.screenshot(path=str(OUT/f'{label.replace("/","-")}-{scene}.png'))
    check(label+' distinct rendered views', len(images) == 11)

with sync_playwright() as pw:
    launch = {'headless': True, 'args': ['--no-sandbox', '--enable-unsafe-swiftshader']}
    if os.environ.get('CHROMIUM_EXECUTABLE'):
        launch['executable_path'] = os.environ['CHROMIUM_EXECUTABLE']
    browser = pw.chromium.launch(**launch)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    for renderer in ['canvas', 'webgl']:
        # A built static server serves the actual artifact without dev HTML injection.
        response = page.goto(BUILT+f'/previews/tenbox-v2-r5.html?renderer={renderer}', wait_until='networkidle')
        check(renderer+' standalone HTTP', response.status == 200)
        scene_checks(page, renderer+'/standalone')
    for width in [1440, 390]:
        page.set_viewport_size({'width': width, 'height': 1000})
        response = page.goto(BASE+'/docs/tenbox-v2/preview/', wait_until='networkidle')
        check(str(width)+' document HTTP', response.status == 200)
        check(str(width)+' responsive', page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'))
        iframe = page.locator('iframe').first
        check(str(width)+' default local origin', iframe.get_attribute('src') in ['/previews/tenbox-v2-r5.html', BASE+'/previews/tenbox-v2-r5.html'])
        frame = iframe.content_frame
        frame.locator('[data-view="underside"]').click()
        frame.locator('[data-view="floor-fit"]').click()
        frame.locator('[data-view="h2d"]').click()
        check(str(width)+' embedded roof', frame.locator('[data-id="stageTitle"]').inner_text() == 'H2D · flat roof, one nozzle')
        page.screenshot(path=str(OUT/f'integrated-{width}.png'), full_page=True)
    for file in sorted((ROOT/'public/downloads/candidate').glob('tenbox-v2-r5*.zip')) + sorted((ROOT/'public/downloads/candidate/tenbox-v2-r5').glob('*.3mf')):
        path = '/'+file.relative_to(ROOT/'public').as_posix()
        response = page.request.get(BUILT+path)
        body = response.body()
        check('full GET '+path, response.status == 200 and body == file.read_bytes())
        check('SHA256 '+path, hashlib.sha256(body).hexdigest() == hashlib.sha256(file.read_bytes()).hexdigest())
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            check('CRC '+path, archive.testzip() is None)
            if file.suffix == '.zip':
                rows = archive.read('MANIFEST.sha256').decode().splitlines()
                check('inventory '+path, len(rows) == len(archive.namelist())-1)
                for row in rows:
                    sha, name = row.split('  ', 1)
                    check('member '+path+':'+name, hashlib.sha256(archive.read(name)).hexdigest() == sha)
    check('no browser errors', not errors)
    result = {'passed': True, 'browser': browser.version, 'checks': checks, 'site_url': BASE, 'built_url': BUILT, 'physical_or_studio_tests': False}
    (OUT/'checks.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(f'Tenbox browser and full HTTP checks: {len(checks)} passed; Chromium {browser.version}')
    browser.close()
