import { h } from 'preact';
import rows from './two-way-data.js';
const size = values => values.map(v => Number(v.toFixed(2))).join(' × ');
export function TwoWayTable() {
  const columns = ['構成', '各トレー / 合計', '金属外形 W × D × H', '完成包絡 W × D × H', '本体 / 蓋の深さ'];
  return h('div', { style: { overflowX: 'auto' } }, h('table', null,
    h('thead', null, h('tr', null, columns.map(x => h('th', { key:x }, x)))),
    h('tbody', null, rows.map(r => h('tr', { key:r.id },
      h('td', null, `${r.letter} / ${r.id}`),
      h('td', null, `${r.perTrayU}U・${r.hp}HP / ${r.totalU}U`),
      h('td', null, size(r.metal)), h('td', null, size(r.complete)),
      h('td', null, `${r.baseDepth} / ${r.lidDepth}`))))));
}
export function TwoWayFrameTable() {
  return h('table', null,
    h('thead', null,h('tr', null, ['構成','各トレー レール / fixer / padder / スペーサー','前面から後端 / 蓋背板の余裕'].map(x=>h('th',{key:x},x)))),
    h('tbody',null, rows.map(r=>h('tr',{key:r.id},h('td',null,r.letter),h('td',null,['rail','fixer','padder','spacer'].map(k=>r.countsPerTray[k]).join(' / ')),h('td',null,`${r.frameReach.toFixed(6)} / ${r.frameRearClearLid.toFixed(6)} mm`)))));
}
