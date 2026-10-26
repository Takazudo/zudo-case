"""P4 browser regression. Tests real self-contained HTML; no external assets."""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json,os,time
ROOT=Path(__file__).resolve().parents[1];HTML=ROOT/'zudo-case-printed-5mm-p4-uniform-vents.html'
records=[];errors=[]
def ok(name,passed,**kw):
 records.append(dict(check=name,passed=bool(passed),**kw));print(('PASS ' if passed else 'FAIL ')+name,flush=True)
 if not passed:raise AssertionError(name)
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM'),headless=True,args=['--no-sandbox','--disable-dev-shm-usage','--enable-unsafe-swiftshader'])
 page=browser.new_page(viewport={'width':1440,'height':1000},device_scale_factor=1,accept_downloads=True)
 page.on('pageerror',lambda e:errors.append(str(e)))
 url=os.environ.get('TEST_URL',HTML.as_uri())+'?renderer='+os.environ.get('RENDERER','canvas')
 page.goto(url,wait_until='load',timeout=60000)
 file_result={'attempted':url.startswith('file:'),'succeeded':url.startswith('file:')}
 page.wait_for_function('window.study&&study.frames>0',timeout=60000)
 renderer=page.evaluate('study.glInfo()');ok('requested renderer available',('WebGL' in renderer['version']) if os.environ.get('RENDERER')=='webgl' else renderer['version']=='Canvas 2D');ok('initial render',page.evaluate('study.parts.length>0'))
 ok('source rails visible by default',page.evaluate('study.visibleParts().filter(p=>p.cat==="rails").length===6'))
 ok('old frame envelope entirely removed',page.evaluate('study.parts.every(p=>p.cat!=="frame"&&p.id!=="frame-envelope")'))
 ok('source PCB count 2+6',page.evaluate('study.parts.filter(p=>p.cat==="railPCB").length===2 && study.parts.filter(p=>p.cat==="railPads").length===6'))
 ok('10 spacers / 12 rail-end bolts',page.evaluate('study.parts.filter(p=>p.role==="spacer").length===10 && study.parts.filter(p=>p.role==="rail-end-bolt").length===12'))
 for role in ['mount-bolt','mount-nut','mount-washer']:
  ok('ten '+role,page.evaluate('(r)=>study.parts.filter(p=>p.role===r).length===10',role))
 ok('original 204mm rails retained',page.evaluate('study.parts.filter(p=>p.cat==="rails").every(p=>Math.abs(p.box[3]-p.box[0]-204)<1e-6)'))
 ok('three rows have two rails',page.evaluate('[0,1,2].every(r=>study.parts.filter(p=>p.cat==="rails"&&p.row===r).length===2)'))
 ok('P2 seam strips absent',page.evaluate('study.parts.every(p=>!p.id.includes("splice")&&p.cat!=="splices")'))
 ok('P2 equal floor dimensions',page.evaluate('JSON.stringify(study.dimensions.floor_half_size)==="[236.4,170.35,5]"'))
 ok('P2 paired supports',page.evaluate('JSON.stringify(study.dimensions.paired_support_y)==="[-25,25]"'))
 ok('P2 28 L brackets',page.evaluate('study.parts.filter(p=>p.cat==="brackets").length===28'))
 ok('reference rail objects not new print parts',page.locator('#printPart option').evaluate_all('(es)=>es.every(e=>!e.value.startsWith("rail-"))'))
 page.locator('#stage').screenshot(path=str(ROOT/'evidence/assembly.png'))
 page.screenshot(path=str(ROOT/'evidence/assembly-ui.png'))
 views=['assembly','rails','railMount','bed','edge','seams','pair','lid','reference','panel-front','panel-back','panel-right','panel-left','inside-right']
 for view in views:
  page.locator(f'[data-view="{view}"]').click();page.wait_for_timeout(100)
  ok('view '+view,page.evaluate('study.state.view')==view)
  ok('nonempty geometry '+view,page.evaluate('study.parts.length>0'))
  ok('active tab '+view,page.locator(f'[data-view="{view}"]').get_attribute('aria-pressed')=='true')
  page.locator('#stage').screenshot(path=str(ROOT/f'evidence/{view}.png'))
  if view in ['rails','railMount']:page.screenshot(path=str(ROOT/f'evidence/{view}-ui.png'))
 for side in ['front','back','right','left']:
  page.locator(f'[data-view="panel-{side}"]').click()
  ok('vent metadata '+side,page.evaluate('(side)=>study.parts.find(p=>p.id==="wall-"+side).ventilation.count',side)==(25 if side in ['left','right'] else 16))
  mesh=page.evaluate('(side)=>study.parts.find(p=>p.id==="wall-"+side).mesh',side)
  page.locator('#compareP3').check()
  ok('P3 comparison mesh '+side,page.evaluate('(side)=>study.parts.find(p=>p.id==="wall-"+side).mesh',side)!=mesh)
  page.locator('#compareP3').uncheck()
  ok('P4 restored '+side,page.evaluate('(side)=>study.parts.find(p=>p.id==="wall-"+side).mesh',side)==mesh)
 page.locator('[data-view="rails"]').click()
 ok('rail-only view contains complete66 components',page.evaluate('study.parts.length===66 && study.parts.every(p=>p.existingReference===true)'))
 ok('rail spacing readout','210.4' in page.locator('#measure').inner_text())
 page.locator('[data-view="railMount"]').click()
 ok('actual middle mounting local section',page.evaluate('study.parts.some(p=>p.id==="mount-rail-spacer-right-3")&&study.parts.every(p=>p.note.includes("Cut through"))'))
 ok('mount stack readout','15.6' in page.locator('#measure').inner_text())
 page.locator('[data-view="pair"]').click();ok('paired support closeup unchanged',page.evaluate('study.parts.filter(p=>p.cat==="brackets").length===2'))
 page.locator('[data-view="seams"]').click();ok('both equal floor halves retained',page.evaluate('study.parts.filter(p=>p.cat==="floor").length===2'))
 page.locator('[data-view="bed"]').click()
 for id in page.locator('#printPart option').evaluate_all('(els)=>els.map(e=>e.value)'):
  page.locator('#printPart').select_option(id);page.wait_for_timeout(50)
  ok('bed scene '+id,page.evaluate('study.scene')=='bed-'+id)
  ok('bed footprint '+id,'STL is already flat and rotated.' in page.locator('#bedReport').inner_text())
  ok('brim display '+id,page.evaluate('study.parts.some(p=>p.cat==="brim")'))
 page.locator('[data-view="assembly"]').click()
 ok('lid absent initially to expose rails',not page.evaluate('study.state.lidVisible'))
 page.locator('#lidVisible').check();ok('lid restored with one toggle',page.evaluate('study.visibleParts().some(p=>p.group==="lid")'))
 for button,expected in [('closedBtn',0),('openBtn',65)]:
  page.locator('#'+button).click();ok(button,page.evaluate('study.state.lidLift')==expected)
  ok('rail stays installed with '+button,page.evaluate('study.parts.filter(p=>p.cat==="rails").every(p=>study.partOffset(p).every(v=>v===0))'))
 page.locator('#stage').screenshot(path=str(ROOT/'evidence/open-lid.png'))
 page.locator('#closedBtn').click();page.locator('#blackBtn').click();page.locator('#stage').screenshot(path=str(ROOT/'evidence/closed-black.png'))
 page.locator('#lidVisible').uncheck();page.locator('#stage').screenshot(path=str(ROOT/'evidence/installed-black.png'))
 page.locator('#colorBtn').click();page.locator('#explodeBtn').click();ok('explode state',page.evaluate('study.state.explode')==20)
 ok('rail group moves coherently',page.evaluate('study.parts.filter(p=>["rails","railPCB","railPads"].includes(p.cat)).every(p=>JSON.stringify(study.partOffset(p))==="[0,0,30]"||JSON.stringify(study.partOffset(p))==="[0,0,30]" )'))
 page.locator('#stage').screenshot(path=str(ROOT/'evidence/exploded.png'))
 page.locator('#assembleBtn').click();ok('reassemble',page.evaluate('study.state.explode')==0)
 for id in ['xray','pins','section']:
  start=page.locator('#'+id).is_checked();page.locator('#'+id).set_checked(not start)
  ok('toggle '+id,page.evaluate('(k)=>study.state[k]',id)==(not start));page.locator('#'+id).set_checked(start)
 # Aggregate visibility honors initially hidden lid as well as category layers.
 page.locator('#allBtn').click();ok('show all from partial',page.evaluate('study.state.hidden.length===0&&study.state.lidVisible'))
 page.locator('#allBtn').click();ok('hide all',page.evaluate('study.visibleParts().length===0'))
 page.locator('#allBtn').click();ok('show all',page.evaluate('study.visibleParts().length===study.parts.length'))
 for cat in ['rails','railPCB','railPads','railSpacers','railHardware']:
  page.locator(f'[data-cat="{cat}"]').uncheck();ok('hide category '+cat,page.evaluate('(cat)=>study.visibleParts().every(p=>p.cat!==cat)',cat));page.locator(f'[data-cat="{cat}"]').check()
 page.locator('[data-view="rails"]').click()
 page.locator('#layerRows .solo').first.click();ok('solo category',page.evaluate('new Set(study.visibleParts().map(p=>p.cat)).size===1'));page.locator('#allBtn').click()
 # Real mesh picking and Solo part.
 page.locator('#topBtn').click();page.locator('#fitBtn').click();page.wait_for_timeout(100)
 # Deterministic pointer picking over displayed source rails, with fallbacks to several locations.
 r=page.locator('#canvas').bounding_box();picked=False
 for x,y in [(0.5,.35),(.5,.5),(.45,.25),(.5,.72),(.3,.5),(.7,.5)]:
  page.mouse.click(r['x']+r['width']*x,r['y']+r['height']*y)
  if page.evaluate('study.state.selected!==null'):picked=True;break
 ok('click source geometry selects a part',picked)
 page.locator('#selectedSolo').click();ok('solo picked part',page.evaluate('study.visibleParts().length===1'));page.locator('#clearSelection').click()
 page.locator('[data-view="assembly"]').click();page.locator('#lidVisible').uncheck()
 with page.expect_download() as di:page.locator('#saveBtn').click()
 dest=ROOT/'evidence/exported-settings.json';di.value.save_as(dest);j=json.loads(dest.read_text());ok('settings schema',j['schema']=='zudo-case-printed-p4-uniform-vents/1')
 page.locator('#fileInput').set_input_files(str(dest));page.wait_for_timeout(100);ok('settings roundtrip',page.evaluate('study.state.view')==j['state']['view'] and page.evaluate('study.state.lidVisible')==j['state']['lidVisible'])
 bad=ROOT/'evidence/invalid-settings.json';j['state']['lidVisible']='yes';bad.write_text(json.dumps(j));old=page.evaluate('JSON.stringify(study.state)')
 page.locator('#fileInput').set_input_files(str(bad));page.wait_for_timeout(100);ok('reject invalid visibility type',page.evaluate('JSON.stringify(study.state)')==old and 'Invalid' in page.locator('#toast').inner_text());bad.unlink()
 for label,mutate in [('inherited view',lambda j:j['state'].update(view='__proto__')),('inherited category',lambda j:j['state'].update(hidden=['constructor'])),('comparison',lambda j:j['state'].update(compareP3='yes')),('camera',lambda j:j['cam'].update(span=-1)),('pattern',lambda j:j.update(schema='rejected-pattern-02')),('stale P3',lambda j:j.update(schema='zudo-case-printed-p3/1'))]:
  j=json.loads((ROOT/'evidence/exported-settings.json').read_text());mutate(j);bad.write_text(json.dumps(j));old=page.evaluate('JSON.stringify(study.state)');page.locator('#fileInput').set_input_files(str(bad));page.wait_for_timeout(100)
  ok('invalid settings '+label,page.evaluate('JSON.stringify(study.state)')==old);bad.unlink()
 page.locator('#projectBtn').click();ok('perspective switch',not page.evaluate('study.state.ortho'));page.locator('#projectBtn').click()
 yaw=page.evaluate('study.camera.yaw');page.locator('#canvas').focus();page.keyboard.press('ArrowRight');ok('keyboard orbit',page.evaluate('study.camera.yaw')!=yaw)
 page.locator('#fitBtn').click();ok('finite fitted camera',page.evaluate('Number.isFinite(study.camera.span)&&study.camera.span>0'))
 with page.expect_download() as di:page.locator('#shotBtn').click()
 dest=ROOT/'evidence/png-export.png';di.value.save_as(dest);ok('PNG export header',dest.read_bytes()[:8]==b'\x89PNG\r\n\x1a\n')
 (ROOT/'evidence/browser-partial.json').write_text(json.dumps({'checks':records,'renderer':renderer},indent=2))
 for width in [390,320]:
  print('Mobile viewport '+str(width),flush=True)
  page.set_viewport_size({'width':width,'height':900})
  for view in views:
   print('Mobile view '+view,flush=True);page.evaluate('(v)=>study.setView(v)',view);page.wait_for_timeout(80)
   ok(f'no page horizontal overflow {width}/{view}',page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
  page.evaluate('study.setView("assembly")');page.screenshot(path=str(ROOT/f'evidence/mobile-{width}.png'),full_page=True)
 ok('no runtime errors',not errors,errors=errors)
 result={'checks':records,'count':len(records),'renderer':renderer,'browser_version':browser.version,'page_errors':errors,'file_url':file_result,'display_method':'file URL' if file_result['succeeded'] else 'same HTML via page.set_content','webgl_verified':renderer['version']!='Canvas 2D'}
 (ROOT/('evidence/browser-'+os.environ.get('RENDERER','canvas')+'-checks.json')).write_text(json.dumps(result,indent=2));print('PASS',len(records),'checks;',renderer,'file_url:',file_result)
 browser.close()
