"""Chromium rendering, integrated iframe and full built-site download verification."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import hashlib, io, json, os, zipfile
ROOT = Path(__file__).resolve().parents[1]
CURRENT = json.loads((ROOT/'project/tenbox-v2/current.json').read_text())
BASE = os.environ.get('SITE_URL', 'http://localhost:4391').rstrip('/')
BUILT = os.environ.get('BUILT_URL', 'http://localhost:4393').rstrip('/')
OUT = Path(os.environ.get('EVIDENCE_DIR', str(ROOT/'.cache/tenbox-browser')))
OUT.mkdir(parents=True, exist_ok=True)
checks = []
def check(label, value):
    assert value, label
    checks.append(label)

def scene_checks(page, label):
    page.wait_for_selector('#tenbox-v2-r8[data-ready="true"]')
    check(label+' renderer', page.evaluate('tenboxStudy.renderer') == label.split('/')[0])
    check(label+' current revision', page.evaluate('tenboxStudy.state.revision') == CURRENT['current_revision'] == 'R8')
    images = set()
    scenes = ['assembly', 'lower-slot', 'rail-junction', 'side-fixings', 'side-fixing', 'inside-nuts', 'side', 'underside', 'lid-fit']
    for scene in scenes:
        page.locator(f'[data-view="{scene}"]').click()
        page.wait_for_function('(scene) => tenboxStudy.state.view === scene && tenboxStudy.visibleParts().length > 0', arg=scene)
        page.evaluate('new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
        canvas = page.locator('canvas').first
        shot = canvas.screenshot()
        images.add(hashlib.sha256(shot).hexdigest())
        check(label+'/'+scene+' canvas', len(shot) > 5000)
        if scene in ['assembly', 'lower-slot', 'inside-nuts', 'underside', 'lid-fit']:
            canvas.screenshot(path=str(OUT/f'{label.replace("/","-")}-{scene}.png'))
    check(label+' distinct rendered views', len(images) == len(scenes))
    detail = page.locator('[data-id="stageDetail"]').inner_text()
    check(label+' lid capacity and shortfall', '19.869' in detail and '7.131' in detail)
    check(label+' lid dimension overlay', page.locator('[data-id="lidDimension"]').is_visible())
    page.locator('[data-view="lower-slot"]').click()
    camera = page.evaluate('tenboxStudy.camera')
    page.locator('[data-revision="R7"]').click()
    check(label+' R7 comparison', page.evaluate('tenboxStudy.state.revision') == 'R7')
    check(label+' R7 upper-slot label', 'Upper slots' in page.locator('[data-id="stageDetail"]').inner_text())
    check(label+' comparison camera retained', page.evaluate('tenboxStudy.camera') == camera)
    page.locator('[data-revision="R8"]').click()
    check(label+' current lower-slot label', 'Lower slots' in page.locator('[data-id="stageDetail"]').inner_text())
    check(label+' current camera retained', page.evaluate('tenboxStudy.camera') == camera)

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
        response = page.goto(BUILT+CURRENT['preview']+f'?renderer={renderer}', wait_until='networkidle')
        check(renderer+' standalone HTTP', response.status == 200)
        scene_checks(page, renderer+'/standalone')
    for width in [1440, 390]:
        page.set_viewport_size({'width': width, 'height': 1000})
        response = page.goto(BASE+'/docs/tenbox-v2/preview/', wait_until='networkidle')
        check(str(width)+' document HTTP', response.status == 200)
        check(str(width)+' responsive', page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'))
        iframe = page.locator('iframe').first
        check(str(width)+' default local origin', iframe.get_attribute('src') in [CURRENT['preview'], BASE+CURRENT['preview']])
        frame = iframe.content_frame
        frame.locator('#tenbox-v2-r8[data-ready="true"]').wait_for()
        frame.locator('[data-view="underside"]').click()
        frame.locator('[data-view="lower-slot"]').click()
        check(str(width)+' embedded lower slot', 'Lower slots' in frame.locator('[data-id="stageDetail"]').inner_text())
        frame.locator('[data-view="lid-fit"]').click()
        check(str(width)+' embedded current revision', frame.locator('[data-id="stageTitle"]').inner_text().startswith('R8 · '))
        detail = frame.locator('[data-id="stageDetail"]').inner_text()
        check(str(width)+' embedded lid capacity and shortfall', '19.869' in detail and '7.131' in detail)
        page.screenshot(path=str(OUT/f'integrated-{width}.png'), full_page=True)
    check('current download inventory', set(CURRENT['downloads']) == {'print', 'review', 'source'})
    for path in CURRENT['downloads'].values():
        file = ROOT/'public'/path.lstrip('/')
        response = page.request.get(BUILT+path)
        body = response.body()
        check('full GET '+path, response.status == 200 and body == file.read_bytes())
        check('SHA256 '+path, hashlib.sha256(body).hexdigest() == hashlib.sha256(file.read_bytes()).hexdigest())
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            check('CRC '+path, archive.testzip() is None)
            rows = archive.read('MANIFEST.sha256').decode().splitlines()
            check('inventory '+path, len(rows) == len(archive.namelist())-1)
            for row in rows:
                sha, name = row.split('  ', 1)
                check('member '+path+':'+name, hashlib.sha256(archive.read(name)).hexdigest() == sha)
            if path == CURRENT['downloads']['print']:
                projects = [name for name in archive.namelist() if name.startswith('projects/') and name.endswith('.3mf')]
                check('current print bundle projects', len(projects) == 15)
                check('current print bundle common floor', 'meshes/body-bottom-common-print.stl' in archive.namelist())
    check('no browser errors', not errors)
    result = {'passed': True, 'revision': CURRENT['current_revision'], 'browser': browser.version, 'checks': checks, 'site_url': BASE, 'built_url': BUILT, 'physical_or_studio_tests': False}
    (OUT/'checks.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(f'Tenbox browser and full HTTP checks: {len(checks)} passed; Chromium {browser.version}')
    browser.close()
