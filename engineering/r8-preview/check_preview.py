from pathlib import Path
from playwright.sync_api import sync_playwright
import json
ROOT=Path(__file__).resolve().parent
HTML=ROOT.parent/'zudo-simple-lid-preview.html'
(ROOT/'previews').mkdir(exist_ok=True)
report={'desktop':[],'mobile':[],'testMethod':'Standalone HTML injected with set_content in an offline browser context; file navigation is blocked by managed browser policy.'}
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--enable-unsafe-swiftshader','--disable-dev-shm-usage','--use-gl=angle','--use-angle=swiftshader','--ignore-gpu-blocklist'])
    context=browser.new_context(viewport={'width':1600,'height':1050},device_scale_factor=1,offline=True)
    page=context.new_page();errors=[];requests=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda r:requests.append(r.url))
    page.set_content(HTML.read_text(),wait_until='domcontentloaded',timeout=45000)
    page.wait_for_function('window.__simpleLid && window.__simpleLid.stats().frames>0',timeout=45000)
    page.wait_for_timeout(700)
    print('initial',page.evaluate('window.__simpleLid.stats()'),flush=True)
    page.screenshot(path=str(ROOT/'previews/daily.png'))
    for model in ['7u40','3u60','7u60']:
        page.evaluate('(m)=>window.__simpleLid.setModel(m)',model)
        for preset in ['daily','travel','open']:
            page.evaluate('(p)=>window.__simpleLid.setPreset(p)',preset)
            page.wait_for_timeout(450)
            stats=page.evaluate('window.__simpleLid.stats()')
            assert stats['state']['model']==model
            assert stats['locks']==0
            assert stats['bandsVisible']==(preset=='travel'),stats
            assert stats['pose'][0:2]==[0,0],stats
            assert stats['pose'][2]==(110 if preset=='open' else 0),stats
            report['desktop'].append(stats)
            if model=='7u40' or preset=='travel':
                page.screenshot(path=str(ROOT/f'previews/{model}-{preset}.png'))
    page.evaluate("window.__simpleLid.setModel('7u40');window.__simpleLid.setPreset('travel');window.__simpleLid.setLift(30)")
    assert page.evaluate('window.__simpleLid.stats().bandsVisible') is False
    page.evaluate("window.__simpleLid.setPreset('open');window.__simpleLid.setLook(true,true);window.__simpleLid.setDetail(true)")
    page.wait_for_timeout(600)
    page.screenshot(path=str(ROOT/'previews/locators-open.png'))
    page.evaluate("window.__simpleLid.setLift(8);window.__simpleLid.setView('front')")
    page.wait_for_timeout(450)
    page.screenshot(path=str(ROOT/'previews/locator-section.png'))
    report['desktopErrors']=errors
    report['requests']=requests
    assert not errors,errors
    # Real UI controls: bands, open, animation pause, hide lid, model select.
    page.evaluate('window.__simpleLid.setLook(false,false);window.__simpleLid.setDetail(false)')
    page.locator('[data-preset="travel"]').click();page.wait_for_timeout(200)
    assert page.locator('#bands').is_checked()
    page.locator('[data-preset="open"]').click();page.wait_for_function('Math.abs(window.__simpleLid.state.lift-110)<0.01',timeout=30000)
    assert not page.locator('#bands').is_checked()
    assert abs(page.evaluate('window.__simpleLid.state.lift')-110)<.01
    page.locator('#hideLid').check();assert page.evaluate('window.__simpleLid.state.hideLid')
    page.locator('#model').select_option('3u60');page.wait_for_timeout(250)
    page.locator('#resetAll').click();page.wait_for_timeout(250)
    assert page.evaluate('window.__simpleLid.state.lift')==0
    context.close()
    mobile=browser.new_context(viewport={'width':390,'height':844},device_scale_factor=1,offline=True,is_mobile=True,has_touch=True)
    page=mobile.new_page();mobile_errors=[];page.on('pageerror',lambda e:mobile_errors.append(str(e)))
    page.set_content(HTML.read_text(),wait_until='domcontentloaded',timeout=45000)
    page.wait_for_function('window.__simpleLid && window.__simpleLid.stats().frames>0',timeout=45000)
    page.wait_for_timeout(500)
    page.evaluate("window.__simpleLid.setPreset('travel')")
    page.wait_for_timeout(400);page.screenshot(path=str(ROOT/'previews/mobile.png'),full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
    page.evaluate("window.__simpleLid.setPreset('open');window.__simpleLid.setDetail(true);window.__simpleLid.setLook(true,true)")
    page.wait_for_timeout(600);page.screenshot(path=str(ROOT/'previews/mobile-detail.png'),full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
    report['mobile'].append(page.evaluate('window.__simpleLid.stats()'))
    report['mobileErrors']=mobile_errors;assert not mobile_errors
    browser.close()
(ROOT/'browser-validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print('PASS',len(report['desktop']),'desktop states, mobile + controls + offline')
