"""Selected profile packaging. Does not mark production approved."""
from pathlib import Path
import json,zipfile,hashlib,csv,shutil,html
from fitfix import io

def make(out,root,manifest,report,lid_report):
    assert report['passed'] and lid_report['passed'],'Failed nominal checks block packaging'
    manifest['status']='full-set-prototype-preparation; physical and vendor confirmation pending'
    io.write_json(out/'selected-order.json',manifest)
    from collections import Counter
    counts=Counter(r['role'] for r in manifest['existing_frame'] if r['role']!='outerWasher')
    hardware=[dict(id='source-'+role,quantity=count,procurement='existing/reused',material='original real hardware / PCB / rail',price=None) for role,count in sorted(counts.items())]
    hardware += [dict(id=id,quantity=q,procurement=proc,material=mat,price=None) for id,q,proc,mat in [
        ('L-bracket-20x20x16-t2',18,'existing/reused','metal'),('body-M5x14',34,'purchased hardware','metal screw; assumed head'),('body-M5x16',2,'purchased hardware','metal screw; assumed head'),('body-M5-nut',36,'purchased hardware','metal nylon-insert lock nut'),('lid-M5x10',8,'purchased hardware','metal screw; assumed head'),('lid-M5-nut',8,'purchased hardware','metal nylon-insert lock nut'),('feet-d10-h3-assumed',4,'purchased hardware','rubber; product not selected'),('external-strap',2,'purchased hardware','product not selected')]]
    manifest['hardware']=hardware
    manifest['existing_frame_accounting']='outerWasher instances are included in round-replacement reused20; other source roles appear once in hardware'
    io.write_json(out/'selected-order.json',manifest)
    quantities=[]
    for p in manifest['parts']:
        quantities.append(dict(id=p['id'],material=p['material'],destination=p['procurement'],quantity=p['quantity'],selected_print_quantity=p.get('selected_print_quantity',0),instances=p['quantity'],step=p['step'],stl=p['stl'],dxf=p.get('dxf','')))
    for p in hardware:quantities.append(dict(id=p['id'],material=p['material'],destination=p['procurement'],quantity=p['quantity'],selected_print_quantity=0,instances=p['quantity'],step='',stl='',dxf=''))
    with (out/'BOM.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=quantities[0].keys());w.writeheader();w.writerows(quantities)
    text='''# R10-FULLSET-01 — ONE 7U40 prototype / 注文相談の入口

選定: `7u40-t1-groove1p70-m5`。この版だけで1台分。量産承認ではない (`production_approved=false`)。旧R9/R2クーポンと混ぜない。

| パッケージ | 材料・仕上げ | 実数量 | 使用形式 |
|---|---|---:|---|
| R10-FULLSET-01-aluminum.zip | A5052 t1.5、バリ取り、加工後黒アルマイト | 6枚 | STEP または DXF（同じ部品） |
| R10-FULLSET-01-pa12.zip | MJF PA12-HP、黒染め | 20個 | 各STLが単体1個。STEPは参考 |
| R10-FULLSET-01-home-print.zip | 家庭印刷・黒ASA | 新規72個 | mm、単体STL、Z=0をベッドへ |

アルミ: 底1・前1・後1・左1・右1・M5蓋1。36長穴＋10レール穴＋8蓋穴が機能穴、別に各板φ4吊り穴1個（計6）。加工用穴を取付穴として使わない。各ファイル名のqty1はSTEPとDXFを二重計上する意味ではない。各材質フォルダーのquantity-finish.csvがその業者向けの数量・仕上げ表。共通BOMの他材質や再使用品をその業者へ発注しない。
PA12: 上4・下8（左右の中央継ぎに下耳/上耳の別あり）・縦4・M5蓋枠4。左右反転部品を同じファイルとして扱わない。
ASA: 縦角16、下辺10、内側保護36、底面10。円形20個は既存底金具裏10＋レール外10の交換用ファイルで、選定印刷数量0。供給先へ渡さない。

## ワッシャー調整

`home-print/parameters.json` をコピーして幅・長さ・穴径・偏心・角R・XY穴補正・入口面取りを変更する。金属穴は自動で変更しない。リポジトリのルートで:

```sh
uv run --locked --project engineering/r9-prototype-01 python engineering/r10-fullset-01/build.py --washers-only --washer-parameters /absolute/path/to/parameters.json --out /tmp/my-washers
```

下辺14×16は外形中心を穴より板の内側へ1mm。底面20×12は外形中心を穴よりケース中心へ3mm（R2のガード干渉修正）。内側20×12は中心穴。各STLは穴中心をXY原点に置く。偏心を逆に組まない。ASAをPA12や購入ナイロンと混同しない。

## 組立と実ハードウェア

壁側ねじを先に締結してから底板ねじを取り付け、最後にレールユニットを組み込む。底板ねじを先に入れると壁側の直線工具経路に当たるため、後日の壁側締め直しでは底板ねじを外す。パネル/ブラケットの両接触面にt1保護材。36箇所のうち中央重ね継ぎ2箇所はM5×16、残34はM5×14を公称候補とする。金具t2、ナットh5、低頭1.4を使う積層で、詳しくはhardware-stacks.json。蓋はM5×10を8本、AF8.4/有効5.5のポケット、座金なしの候補。頭径や工具、実際の製品形状は未確定。
既存18金具、204mmレール6本、元fixer2枚/padder6枚、8mmスペーサー10、レール固定ボルト/ナット10組、レール端ボルト12本を再使用。スペーサーの再印刷はengineering/home-print-spacer-01を参照。ねじ・ナット・レール・PCBは印刷代用品ではない。
仮ゴム脚φ10×3は4個、圧縮前の底ネジとの公称差0.6mm。外周ストラップ2本は品番未選定。蓋と本体をロックしない。蓋を組み、まっすぐ持ち上げて着脱する。

## 次の行動

1. この一式の材料・仕上げ・DFM・φ4吊り穴位置と治具跡・価格・税送料・納期を業者と確認する。価格は未見積でnull。
2. ユーザーが発注・支払いを別途判断する。この実装から注文は行わない。
3. 一式の到着後、組立・調整域・蓋嵌合・ノブ包絡・脚圧縮・バンド・運搬を現物で評価する。

追加の有料クーポン注文やASAの事前印刷合格は、一式準備の前提ではない。薄肉部1mm、溝1.70mmは試作選定値。荷重・トルク・クリープ・輸送寿命を検証したものではない。
'''
    (out/'ORDER-START-HERE.md').write_text(text)
    (out/'home-print/README.md').write_text(text[text.index('## ワッシャー調整'):])
    (out/'home-print/orientation.svg').write_text('''<svg xmlns="http://www.w3.org/2000/svg" width="600" height="240" viewBox="0 0 600 240"><rect width="600" height="240" fill="white"/><g stroke="black" fill="none"><rect x="60" y="40" width="140" height="160" rx="15"/><circle cx="130" cy="130" r="27.5"/><rect x="350" y="25" width="120" height="200" rx="60"/><circle cx="410" cy="155" r="27.5"/><path d="M130 90V50l-8 12m8-12 8 12M410 90V50l-8 12m8-12 8 12"/></g><g font-family="sans-serif" font-size="14"><text x="15" y="20">Lower cap: centre +1mm inward</text><text x="305" y="20">Floor cap: centre +3mm inward</text><text x="10" y="235">Arrow: toward panel interior / case centre. Bore remains on bolt axis.</text></g></svg>''')
    hole_table=json.loads((out/'hole-table.json').read_text())
    drawings=out/'drawings';drawings.mkdir(exist_ok=True)
    for part in manifest['parts']:
        if part['procurement']!='aluminum':continue
        w,h,_=part['dimensions_mm'];els=[f'<rect x="0" y="0" width="{w}" height="{h}" rx="{3 if part['id']=='lid-plate' else 0}" fill="none" stroke="black" stroke-width=".5"/>']
        for row in [r for r in hole_table if r['part']==part['id']]:
            x,y=row['local_uv']
            if row.get('slot_length'):
                els.append(f'<rect x="{x-5.25}" y="{y-2.75}" width="10.5" height="5.5" rx="2.75" fill="none" stroke="blue" stroke-width=".3" transform="rotate({row["angle"]} {x} {y})"/>')
            else:els.append(f'<circle cx="{x}" cy="{y}" r="2.75" fill="none" stroke="blue" stroke-width=".3"/>')
        x,y=part['hanging_hole_uv'];els.append(f'<circle cx="{x}" cy="{y}" r="2" fill="none" stroke="red" stroke-width=".5"/>')
        els.append(f'<text x="2" y="{h+8}" font-size="5">{part["id"]} / {w:.3f} x {h:.3f} x 1.5 mm / qty1 / red D4 processing hole / local XY origin top-left in diagram</text>')
        (drawings/(part['id']+'.svg')).write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-5 -5 {w+10} {h+20}">'+''.join(els)+'</svg>')
    def zipit(name,files):
        with zipfile.ZipFile(out/name,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for file in sorted(set(files)):
                info=zipfile.ZipInfo(file,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16;z.writestr(info,(out/file).read_bytes())
    mapping=[]
    for p in manifest['parts']:
        old=(root.parent/'r9-lid-m5-01/lidm5/geometry.py') if p['id'].startswith('lid-') else (root/'reference/r2-build_geometry.py')
        mapping.append(dict(part=p['id'],old_source=old.relative_to(root.parent.parent).as_posix(),old_sha256=io.digest(old),new_step=p['step'],new_sha256=io.digest(out/p['step']),change='New integrated R10 geometry; see selected parameters and local correction notes'))
    io.write_json(out/'old-to-new.json',mapping)
    common=['old-to-new.json','source-datums.json','ORDER-START-HERE.md' ,'selected-order.json','BOM.csv','hardware-stacks.json','joint-checks.json','hanging-hole-checks.json','lid-checks.json','validation.json']
    for dest in ['aluminum','pa12']:
        rows=[r for r in manifest['parts'] if r['procurement']==dest]
        table=f'{dest}/quantity-finish.csv'
        with (out/table).open('w') as f:
            writer=csv.writer(f);writer.writerow(['part','quantity','material_finish','primary_file','alternative_or_reference_file'])
            for r in rows:writer.writerow([r['id'],r['quantity'],r['material'],r['step'] if dest=='aluminum' else r['stl'],r['dxf'] if dest=='aluminum' else r['step']])
        files=[table]+[r[k] for r in rows for k in (('step','dxf') if dest=='aluminum' else ('stl','step'))]
        if dest=='aluminum':files+=['hole-table.json']+[f'drawings/{r["id"]}.svg' for r in rows]
        zipit('R10-FULLSET-01-'+dest+'.zip',files+common)
    shutil.copyfile(root/'fullset/home_washers.py',out/'home-print/washer-source.py')
    zipit('R10-FULLSET-01-home-print.zip',[p.relative_to(out).as_posix() for p in (out/'home-print').rglob('*') if p.is_file()]+common)
    inputs=[]
    for p in sorted([root/'parameters.json',root/'washers.json',root/'build.py',*root.glob('fullset/*.*'),root.parent/'r9-prototype-01/uv.lock',root.parent/'r9-lid-m5-01/parameters.json',root.parent/'r6-body/build_geometry.py',root.parent/'r6-body/design-parameters.json',* (root.parent/'r6-body/source-data').rglob('*.json'),root.parent/'r6-body/source-data/rail40/nuts-v2-40hp-single.stl',* (root.parent/'r9-fitfix-01/fitfix').glob('*.py'),* (root.parent/'r9-lid-m5-01/lidm5').glob('*.py')]):
        inputs.append(dict(path=str(p.relative_to(root.parent.parent)),sha256=io.digest(p)))
    io.write_json(out/'outputs-manifest.json',dict(revision='R10-FULLSET-01',production_approved=False,inputs=inputs,files=[dict(path=p.relative_to(out).as_posix(),sha256=io.digest(p),bytes=p.stat().st_size) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='outputs-manifest.json']))
