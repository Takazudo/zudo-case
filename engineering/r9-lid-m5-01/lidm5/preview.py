"""R9-LID-M5-01 preview: the R9-FITFIX-01 viewer with M5 lid parts and fastener envelopes.

The fitfix HTML template is reused read-only and patched by exact replacement;
every replacement must match once, so a changed template fails loudly.
"""
from pathlib import Path
import base64, gzip, json
from fitfix.preview import HTML as BASE

PATCHES = [
    ('<title>ZUDO CASE · R9 FITFIX</title>', '<title>ZUDO CASE · R9 LID M5</title>'),
    ('<h1>ZUDO CASE / R9 FITFIX</h1><p>7U · 40HP — 実肉厚・下辺断面・着座面の修正版</p>',
     '<h1>ZUDO CASE / R9-LID-M5-01</h1><p>7U · 40HP — 天板とPA12枠の組立をM5ネジ＋ロックナットへ（本体・ガードはR9-FITFIX-01のまま）</p>'),
    ('Ordered fit tests / 注文パーツの位置 ↗', '元注文の試験片位置（履歴） ↗'),
    ('<span class="badge">未承認 / 修正候補</span>', '<span class="badge">未承認 / M5改訂候補</span>'),
    ('<label><input id="transparent" type="checkbox"> 外板・天板を透過</label>',
     '<label><input id="transparent" type="checkbox"> 外板・天板・フタ枠を透過</label>'),
    ("hardware:0x8492a0};", "hardware:0x8492a0,fastener:0x9fa9b2,nut:0xd9a520};"),
    ("metalness:['metal','lidMetal','pcb'].includes(item.group)", "metalness:['metal','lidMetal','pcb','fastener','nut'].includes(item.group)"),
    ("for(const id of ['t1p2','t1p0','lift','open','closed','travel','section'])$(id).disabled=mode!=='case';",
     "for(const id of ['t1p2','t1p0','lift','open','closed','travel'])$(id).disabled=mode!=='case';"),
    ("const transparent=$('transparent').checked&&['metal','lidMetal'].includes(kind);",
     "const transparent=$('transparent').checked&&['metal','lidMetal','lid'].includes(kind);"),
    ("m.position.z=mode==='case'&&['lid','lidMetal'].includes(kind)?Number($('lift').value):0}",
     "m.position.z=mode==='case'&&['lid','lidMetal','fastener','nut'].includes(kind)?Number($('lift').value):0}"),
    ("\\n全高とZ座標は別管理`;", "\\n${data.m5summary}\\n本体・ガードはR9-FITFIX-01のまま`;"),
    ("if(mode!=='case')$('info').textContent=`試験片 ${mode}\\n部品をクリックして外形を確認。\\nC1-05は1.0mm、その他は基本案。\\n金属とPA12を別発注。\\n必要数量・材質・比較条件は\\nBOMと各manifestを参照。\\n現物結果は未記入。`}",
     "if(mode!=='case')$('info').textContent=data.coupons[mode].info}"),
    ("function fill(){dispose();",
     "function fill(){dispose();const sec=mode!=='case'&&data.coupons[mode].section;if(sec){clipPlane.normal.set(...sec.normal);clipPlane.constant=sec.constant}else{clipPlane.normal.set(1,0,0);clipPlane.constant=0}"),
    ("{'C1':'上端','C2':'蓋の着座','C4':'下辺 / 底＋壁','C5':'上端 / 2立板'}[id.slice(0,2)]",
     "{'C2':'蓋の着座＋M5','N1':'ナット収納ラダー','LI':'全体フタのM5部'}[id.slice(0,2)]"),
    ("if(mode!=='case'){$('section').checked=false;$('lift').value=0;}", "if(mode!=='case'){$('section').checked=true;$('lift').value=0;}else $('section').checked=false;"),
    ("a.download='zudo-r9-fitfix-'+mode+'.png'", "a.download='zudo-r9-lid-m5-'+mode+'.png'"),
    ('上端ガードは金属上端に直接着座。蓋もガード上面に着座。隙間は垂直な接着面にだけ設定し、実肉厚は別に保持しています。<br><br>',
     'R9-LID-M5-01は天板とPA12枠の組立ネジだけをM5＋ナイロンロックナットへ変更した候補です。フタの座面・位置決め段差・真上への脱着、本体・ガード・バンド方式はR9-FITFIX-01のままです。灰色のネジ（頭φ10×高さ5、長さ10mm）と黄色のナット（対辺8.0×全高5.0）は干渉確認用の仮定包絡で、実部品の形状ではありません。試験片と「全体フタのM5部」はネジ軸を通る断面で開きます。<br><br>'),
]


def make_preview(data, vendor, path):
    html = BASE
    for old, new in PATCHES:
        if html.count(old) != 1:
            raise AssertionError(f'Preview template changed: {old[:60]}')
        html = html.replace(old, new)
    payload = base64.b64encode(gzip.compress(json.dumps(data, separators=(',', ':')).encode(), mtime=0)).decode()
    html = html.replace('__VENDOR__', Path(vendor).read_text().replace('</script', '<\\/script')).replace('__DATA__', payload)
    Path(path).write_text(html, encoding='utf-8')
