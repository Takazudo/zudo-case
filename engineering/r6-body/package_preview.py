"""Package three CAD-derived enclosures into one offline HTML and source archive."""
from pathlib import Path
import base64
import json
import zipfile

ROOT=Path(__file__).resolve().parent
OUT=ROOT.parent


def read_js_object(path, marker):
    raw=path.read_text(encoding='utf-8')
    return json.loads(raw.split(marker,1)[1].strip().removesuffix(';'))


def main():
    data=read_js_object(ROOT/'mesh-data.js','window.ZUDO_CASE_FAMILY =')
    files={}
    for stl in sorted((ROOT/'stl').rglob('*.stl')):
        if stl.name in files:
            raise ValueError('Duplicate STL filename: '+stl.name)
        files[stl.name]=base64.b64encode(stl.read_bytes()).decode('ascii')
    used={p['stlFile'] for model in data['models'].values() for variant in model['variants'].values() for p in variant['parts']}
    if used!=set(files):
        raise ValueError({'missing':sorted(used-set(files)),'unused':sorted(set(files)-used)})
    (ROOT/'stl-data.js').write_text('/* CAD-exported STL bytes for offline part downloads. */\nwindow.ZB60_STL_FILES = '+json.dumps(files,separators=(',',':'))+';\n')
    html=(ROOT/'index.html').read_text()
    license_text=(ROOT/'vendor'/'THREE-LICENSE.txt').read_text()
    html=html.replace('<head>','<!-- Bundled Three.js license:\n'+license_text+'-->\n<head>',1)
    html=html.replace('<link rel="stylesheet" href="styles.css">','<style>\n'+(ROOT/'styles.css').read_text()+'\n</style>')
    for src in ('vendor/three-bundle.js','mesh-data.js','stl-data.js','app.js'):
        script=(ROOT/src).read_text().replace('</script',r'<\/script')
        html=html.replace(f'<script src="{src}"></script>',f'<script>\n{script}\n</script>')
    # Keep the original preview deliverable identity; it now contains all three models.
    single=OUT/'zb60-case-preview.html'
    single.write_text(html)
    archive=OUT/'zb60-case-preview.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path in sorted(ROOT.rglob('*')):
            rel=path.relative_to(ROOT)
            if path.is_file() and not any(p.startswith('.') or p=='__pycache__' for p in rel.parts):
                z.write(path,str(Path('zudo-case-family-preview')/rel))
    quote_archives=[]
    for key in data['models']:
        paths=sorted((ROOT/'stl'/key/'t1p2').glob('*'))
        if not paths: raise ValueError('Missing quote STL directory: '+key)
        output=OUT/f'zudo-{key}-r6-guards-t1p2.zip'
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
            for path in paths:
                if path.is_file():z.write(path,path.name)
            z.writestr('README.txt',f'ZUDO CASE R6 / {key} / PA12-HP Nylon black / t1.2mm\nUnits: millimeters. Upload individual STL files using quantities in manifest.json.\nEach STL contains one physical part; filenames and manifest state required quantities for ONE case.\nNominal quote geometry; retention method and fit clearance still require prototype validation.\n')
        quote_archives.append(str(output))
    print(json.dumps({'single_html':str(single),'html_bytes':single.stat().st_size,'source_zip':str(archive),'zip_bytes':archive.stat().st_size,'stl_count':len(files),'quote_archives':quote_archives},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
