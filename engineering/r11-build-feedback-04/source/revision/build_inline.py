#!/usr/bin/env python3
"""Create a compact conversation view from the same CAD mesh data.

The full standalone preview remains the complete assembly. This inline version
omits bulk rail/hardware/bracket/washer instances only in the assembly scene.
All detail scenes retain their hardware. Mesh coordinates round to 0.001 mm.
"""
from __future__ import annotations
import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', type=Path, default=HERE.parent / 'out' / 'scene.json')
    parser.add_argument('--output', type=Path, default=Path('/workspace/zudo-case-r11-lid-guides.html'))
    args = parser.parse_args()
    source_bytes = args.model.read_bytes()
    source = json.loads(source_bytes)
    omitted = {'sourceFrame', 'hardware', 'lidHardware', 'brackets', 'washer'}
    fields = ['id', 'name', 'cat', 'mesh', 'box', 'role', 'explode']
    scenes = {
        name: [{key: part[key] for key in fields if key in part} for part in parts
               if name != 'assembly' or part['cat'] not in omitted]
        for name, parts in source['scenes'].items()
    }
    used = {part['mesh'] for parts in scenes.values() for part in parts}
    meshes = {key: {'p': [round(value, 3) for value in mesh['p']], 'i': mesh['i']}
              for key, mesh in source['meshes'].items() if key in used}
    metadata = {'revision': source['revision'], 'source': 'Same R11 CAD meshes as the full viewer',
                'source_scene_sha256': hashlib.sha256(source_bytes).hexdigest(),
                'coordinate_precision_mm': 0.001,
                'assembly_omissions': sorted(omitted),
                'detail_scenes_keep_hardware': True}
    payload = json.dumps({'scenes': scenes, 'meshes': meshes, 'metadata': metadata}, ensure_ascii=False, separators=(',', ':')).encode()
    compressed = gzip.compress(payload, compresslevel=9, mtime=0)
    views = {
        'lidguides': {'label': '蓋・四辺の内側ガイド', 'yaw': .75, 'pitch': -.70, 'hardware': False, 'lid': True,
                      'detail': '四辺のガイド · 掛かり12 mm · 厚さ2 mm · 公称隙間0.7 mm'},
        'lidfit': {'label': '側面ガイドのはまり', 'yaw': -1.1, 'pitch': .30, 'lid': True, 'hidden': ['sourceFrame'],
                   'detail': '側面Y＋95 mmの切り出し · 分解すると蓋だけが上へ移動'},
        'inside': {'label': '内側の固定耳', 'yaw': .75, 'pitch': .80, 'hardware': False,
                   'detail': '内側耳32箇所を追加 · この表示では金具・ネジを省略'},
        'assembly': {'label': '全体（主要部品）', 'yaw': .75, 'pitch': .63, 'lid': True,
                     'detail': '同じCADの主要部品 · レール・金具は詳細ビューと完全版で確認'},
        'nylon': {'label': '本体の3DP部品', 'yaw': .75, 'pitch': .70, 'hardware': False,
                  'detail': '内外の固定耳を維持 · 本体12部品はR11-03から変更なし'},
        'corner': {'label': '角・位置決め壁', 'yaw': -2.35, 'pitch': .52, 'xray': True,
                   'detail': '内側の位置決め壁0.8 mm · 板間1.0 mm'},
        'top': {'label': '上端の内外の耳', 'yaw': 2.5, 'pitch': .37, 'hidden': ['sourceFrame'],
                'detail': '上端8箇所は従来の内側耳＋丸座金を維持'},
        'lap': {'label': '共通ネジの重ね接合', 'yaw': -.65, 'pitch': .36,
                'detail': '内側L字耳 t1 mm · L字金具は維持 · 下辺の内側座金を省略'},
        'lid': {'label': '蓋の8部品', 'yaw': .75, 'pitch': .70, 'lid': True,
                'detail': '四辺の内側ガイド · 蓋板8本＋側壁8本で接合 · 真上に取り外し'},
        'lidjoint': {'label': '蓋の継ぎ目', 'yaw': 2.55, 'pitch': .42, 'lid': True,
                     'detail': '天面と側壁の2方向を締結 · ナットは内側'},
        'panels': {'label': 'パネルの穴配置', 'yaw': .75, 'pitch': .55, 'hardware': False,
                   'detail': '前後X±59.5 · 側板Y±95 · 下辺中央4長穴と専用Ø4穴6個を削除'},
        'slots': {'label': '長穴＋5 mm', 'yaw': -.3, 'pitch': .12, 'hardware': False,
                  'detail': '幅5.5 × 全長15.5 mm · 板端側を保ち内側へ5 mm延長'},
        'rail': {'label': 'レールの外側ナット', 'yaw': 2.35, 'pitch': .37,
                 'detail': 'レールとケースの接続だけ外側ナット · モジュール側の空間を確保'}
    }
    standalone = (HERE / 'viewer.html').read_text()
    core = standalone[standalone.index('      const V = {'):standalone.index('      function toast(')]
    old_color = core[core.index('      function partColor('):core.index('      function partBox(')]
    core = core.replace(old_color, "      function partColor(part) { return part.id === state.selected ? selectionColor : category(part.cat).color; }\n")
    core = core.replace("if (state.hidden.includes(part.cat)) return false;", "if (state.hidden.includes(part.cat) || (!state.metal && PANEL_CATS.includes(part.cat))) return false;")
    core = core.replace("color: [0.50, 0.57, 0.58]", "color: foreground")
    core = core.replace("alpha: false, preserveDrawingBuffer", "alpha: true, preserveDrawingBuffer")
    core = core.replace("pixels[i] = 234; pixels[i + 1] = 240; pixels[i + 2] = 241;", "pixels[i] = background[0]*255; pixels[i + 1] = background[1]*255; pixels[i + 2] = background[2]*255;")
    core = core.replace("gl.clearColor(234 / 255, 240 / 255, 241 / 255, 1)", "gl.clearColor(background[0], background[1], background[2], 1)")
    core = core.replace("gl.uniform4f(uniforms.Color, selected ? 0.51 : 0.19, selected ? 0.32 : 0.27, selected ? 0.10 : 0.29, transparent ? 0.28 : selected ? 0.70 : 0.20)", "gl.uniform4f(uniforms.Color, lineColor[0], lineColor[1], lineColor[2], transparent ? 0.28 : selected ? 0.70 : 0.20)")
    core = core.replace("function tick() { render(); requestAnimationFrame(tick); }", "function tick() { if (!root.isConnected) return; try { render(); requestAnimationFrame(tick); } catch(error) { showError(error); } }")
    interaction = standalone[standalone.index('      function rayTriangle('):standalone.index('      function setExplode(')]
    interaction = interaction.replace("canvas.focus({ preventScroll: true }); ", "")
    template = (HERE / 'inline-template.html').read_text()
    result = (template.replace('__MODEL_GZIP__', base64.b64encode(compressed).decode())
              .replace('__VIEWS__', json.dumps(views, ensure_ascii=False, separators=(',', ':')))
              .replace('__CORE__', core).replace('__INTERACTION__', interaction))
    assert len(result.encode()) < 1_000_000, f'Inline size {len(result.encode())} exceeds budget'
    assert all(token not in result for token in ['__MODEL_GZIP__', '__VIEWS__', '__CORE__', '__INTERACTION__'])
    args.output.write_text(result)
    print(json.dumps({'output': str(args.output), 'bytes': len(result.encode()), 'gzip_bytes': len(compressed),
                      'meshes': len(meshes), 'scene_parts': {key: len(value) for key, value in scenes.items()}, 'metadata': metadata}, indent=2))


if __name__ == '__main__':
    main()
