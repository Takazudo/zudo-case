"""Build the self-contained preview. Python standard library only."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent

def build():
    text=(ROOT/'index.html').read_text(encoding='utf-8')
    text=text.replace('<link rel="stylesheet" href="styles.css">','<style>\n'+(ROOT/'styles.css').read_text()+'\n</style>')
    for name in ['three-bundle.js','model-data.js','app.js']:
        js=(ROOT/name).read_text(encoding='utf-8').replace('</script','<\\/script')
        text=text.replace(f'<script src="{name}"></script>','<script>\n'+js+'\n</script>')
    license=(ROOT/'THREE-LICENSE.txt').read_text()
    text=text.replace('<head>','<!--\n'+license+'\n-->\n<head>',1)
    path=ROOT.parent/'zudo-simple-lid-preview.html';path.write_text(text,encoding='utf-8')
    return path
if __name__=='__main__':print(build())
