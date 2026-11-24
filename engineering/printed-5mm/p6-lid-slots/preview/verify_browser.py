"""Real Chromium checks for the P6 CAD-mesh lid preview (no geometry regeneration)."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8126')
    parser.add_argument('--output', type=Path, default=Path('artifacts/p6-browser'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    checks = []
    errors = []

    def check(name, passed, **details):
        checks.append({'check':name, 'passed':bool(passed), **details})
        assert passed, name

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width':900, 'height':720}, device_scale_factor=1)
        page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            response = page.goto(args.base_url.rstrip('/') + '/previews/printed-5mm-p6-lid-slots.html', wait_until='load')
            check('viewer responds', response and response.ok)
            root = page.locator('#p6-lid-preview')
            page.wait_for_function("document.querySelector('#p6-lid-preview')?.dataset.rendered === 'true'")
            meshes = root.evaluate('(r)=>r.p6Study.meshes')
            check('four edges, eight brackets, two roof plates', len(meshes) == 14)
            check('P6 printable roof hashes', {x['sha256'] for x in meshes if x['id'].startswith('lid-top-')} == {
                'd2fa82159ee07ec829d49eb74547cef3ee7c2182c178d70dceed3a973157ec95',
                'ddd7ed45fd2a397baf9c2a92219c14ec0ad9113257cc6e1a1cdb23f8cefed088',
            })
            for view in ['lid', 'plates', 'slot']:
                page.locator('button[data-view="'+view+'"]').click()
                page.wait_for_function('(v)=>document.querySelector("#p6-lid-preview").dataset.view===v', arg=view)
                check('selected view '+view, page.locator('button[data-view="'+view+'"]').get_attribute('aria-pressed') == 'true')
                pixels = page.locator('canvas').evaluate('(c)=>{const d=c.getContext("2d").getImageData(0,0,c.width,c.height).data;let n=0;for(let i=3;i<d.length;i+=4)if(d[i])n++;return n}')
                check('nonempty mesh raster '+view, pixels > 1000, opaque_pixels=pixels)
                page.screenshot(path=str(args.output / (view+'.png')))
            before = root.evaluate('(r)=>r.p6Study.camera.yaw')
            rect = page.locator('canvas').bounding_box()
            x, y = rect['x'] + rect['width']/2, rect['y'] + rect['height']/2
            page.mouse.move(x, y)
            page.mouse.down()
            page.mouse.move(x+70, y+30, steps=4)
            page.mouse.up()
            check('drag rotates CAD mesh', root.evaluate('(r)=>r.p6Study.camera.yaw') != before)
            span = root.evaluate('(r)=>r.p6Study.camera.span')
            page.get_by_role('button', name='拡大', exact=True).click()
            check('accessible zoom works', root.evaluate('(r)=>r.p6Study.camera.span') < span)
            page.set_viewport_size({'width':360, 'height':720})
            page.locator('button[data-view="plates"]').click()
            page.wait_for_function('document.querySelector("#p6-lid-preview").dataset.view === "plates"')
            check('mobile does not overflow', page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            page.screenshot(path=str(args.output / 'mobile.png'))
            page.emulate_media(color_scheme='dark')
            page.locator('button[data-view="slot"]').click()
            page.wait_for_function('document.querySelector("#p6-lid-preview").dataset.view === "slot"')
            page.screenshot(path=str(args.output / 'dark-slot.png'))
            check('no JavaScript errors', len(errors) == 0, errors=errors)
        finally:
            (args.output / 'verification.json').write_text(json.dumps({'checks':checks, 'errors':errors}, ensure_ascii=False, indent=2)+'\n')
            browser.close()
    print(json.dumps({'passed':all(c['passed'] for c in checks), 'checks':len(checks)}, indent=2))


if __name__ == '__main__':
    main()
