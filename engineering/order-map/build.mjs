import fs from 'node:fs';
import { createHash } from 'node:crypto';
import { gzipSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('../../', import.meta.url));
const read = p => fs.readFileSync(root + p);
const json = p => JSON.parse(read(p));
const base = 'engineering/r9-fitfix-01/';
const hash = b => createHash('sha256').update(b).digest('hex');
export const sourceCommit = '541eca7f8ebc2e6da4375108b0d66773a0868b00';
export const families = {
 C1: { function: 'Straight upper edge', title: 'A channel over the metal wall edge', point: [-40,-168,93], caseParts: ['t1p2-top-a-a'], representative: 'C1-01', regionPart: 'c1-01-guard',
 where: 'The upper U guard wraps the top edge of a vertical aluminum wall. The teal segment marks one representative straight section of the case perimeter.',
 fits: 'The metal edge enters the U channel. The roof underside bears directly on that edge; the two side faces control the mating space.',
 priority: 'Compare channel fit and preserved thin walls. C1-06 and C1-07 also compare two-piece end joints. Keep roof and end faces intact.',
 mapping: 'Shared cross-section, not a literal cutout at this position. The 40 mm samples and short pairs use the same guard_section function as the case design.',
 consistency: 'Use one consistent relative build orientation across C1-01–07. The shown camera direction is not a print-orientation instruction.',
 neighbors: 'Mating reference: one reusable 40 × 20 mm aluminum edge coupon. It is not included in this 15-piece PA12 print order.' },
 C2: { function: 'Lift-off lid interface', title: 'The lid seats on the top guard', point: [35,-168,100], caseParts: ['lid-frame-fr','t1p2-top-a-b'], representative: 'C2-01', regionPart: 'c2-01-guard',
 where: 'At the front wall, the lid frame rests on the top guard. Its inward locator extends below the seat into the case opening. The full lid is raised here to expose this relationship.',
 fits: 'The frame bearing underside meets the guard top. The locator clears the guard inner return. The upper ledge supports the aluminum lid plate.',
 priority: 'Preserve the seat, locator face and plate ledge. Compare frame locator clearance: C2-01 0.7 mm, C2-02 0.5 mm, C2-03 0.9 mm (nominal CAD).',
 mapping: 'Source-confirmed front clip: X = 20–50 mm. The small wall, guard, frame and plate retain their saved assembly coordinates before explanatory separation.',
 consistency: 'Keep the three C2 frame variants in one consistent relative build orientation. One unmarked C2-01 guard is reused for all three trials.',
 neighbors: 'Mating references: reusable aluminum wall and lid plate, plus the one ordered PA12 guard. Other C2 guard/wall/plate variants are not extra ordered pieces.' },
 C4: { function: 'Lower floor/wall interface', title: 'An L cover under the bottom joint', point: [35,-169,2], caseParts: ['t1p2-lower-width-half-b'], representative: 'C4-01', regionPart: 'c4-01-lower-guard',
 where: 'The lower guard covers the outside of the front wall and turns underneath the aluminum floor. The wall stands on the floor in the case assembly.',
 fits: 'The horizontal flange top bears against the floor underside. The inner vertical face leaves the intended space to the outside of the wall.',
 priority: 'Preserve the thin horizontal flange, floor-bearing face and vertical wall clearance. This is an L cover, not an inverted upper U channel.',
 mapping: 'Source-confirmed lower-front clip: X = 20–50 mm. The coupon uses the actual lower-width guard, floor and wall solids.',
 consistency: 'C4 does not need the same build orientation as C1 or C2. JLC selects and records orientation based on these fit surfaces.',
 neighbors: 'Mating references: separate aluminum floor and wall coupons. Their geometry explains the joint; they are not PA12 items in this order.' },
 C5: { function: 'Upper two-wall corner', title: 'A U-return around the upper corner', point: [-114.7,-167,94], caseParts: ['t1p2-top-a-a'], representative: 'C5-01', regionPart: 'c5-01-upper-guard',
 where: 'At the upper front-left corner, two vertical aluminum walls meet. The guard follows both wall edges and turns inward on both legs.',
 fits: 'Both metal edges enter the corner channels. The roof underside bears on them; the inner returns stay inside the two-wall cavity.',
 priority: 'Preserve both mating channels, the roof datum, the corner cavity and thin inner returns. Do not fill or thicken them automatically.',
 mapping: 'Source-confirmed upper front-left clip from the nested guard perimeter. It is a small corner fit test, not a full-length perimeter guard.',
 consistency: 'C5 is a separate family; its build orientation need not match C1/C2/C4. The camera angle is illustrative only.',
 neighbors: 'Mating references: front and left aluminum wall coupons. They are separate metal fixtures, not additional PA12 pieces.' }
};
export function makeData() {
 const plan = json(base + 'order-prep/order-plan.json').pa12;
 if (plan.unique_parts !== 13 || plan.quantity !== 15 || plan.parts.length !== 13 || plan.parts.reduce((n,p)=>n+p.order_quantity,0)!==15) throw Error('Unexpected PA12 order');
 const source = json(base + 'out/scene.json');
 const descriptions = ['Baseline channel; principal flat wall 1.2 mm.', 'Channel comparison: side allowance 0.25 mm.', 'Channel comparison: side allowance 0.40 mm.', 'Channel comparison: side allowance 0.15 mm.', 'Thin-wall comparison: principal flat wall 1.0 mm.', 'Joint pair: 19.75 mm each; nominal total split gap 0.5 mm.', 'Joint pair: 20 mm each; nominal zero split gap. Do not force the fit.'];
 const parts = plan.parts.map(p => ({ ...p, label: p.part.toUpperCase().replace('-LOWER-GUARD',' lower guard').replace('-UPPER-GUARD',' upper guard').replace('-GUARD',' guard').replace('-FRAME',' frame'), description: p.part.startsWith('c1') ? descriptions[Number(p.part.slice(3,5))-1] : p.part.endsWith('frame') ? families.C2.priority : p.part==='c2-01-guard' ? 'One unmarked common guard, reused across C2 frame trials.' : families[p.part.slice(0,2).toUpperCase()].priority }));
 for (const p of parts) { const key=p.part.slice(0,5).toUpperCase(); if (!source.coupons[key]?.meshes.some(m=>m.id===p.part)) throw Error('Missing mesh '+p.part); }
 return { sourceCommit, parts, families, caseMeshes: [...source.reference.filter(m=>m.group==='metal'), ...source.variants.t1p2.meshes], coupons: source.coupons };
}
export function build() {
 const data=makeData();
 const payload=gzipSync(JSON.stringify(data),{mtime:0}).toString('base64');
 const app=read('engineering/order-map/app.js').toString().replace('__DATA__',payload);
 const vendor=read(base+'vendor/three-bundle.js').toString().replaceAll('</script','<\\/script');
 const html=read('engineering/order-map/order-map.html').toString().replace('__VENDOR__',()=>vendor).replace('__APP__',()=>app);
 const paths=['order-prep/order-plan.json','fitfix/coupons.py','fitfix/geometry.py','out/scene.json'];
 const provenance={sourceCommit,order:'W2026100405546498',designs:13,pieces:15,sources:paths.map(path=>({path:base+path,sha256:hash(read(base+path))})),note:'No CAD regeneration or model changes. Existing mesh coordinates are preserved; explanatory display offsets only.'};
 return new Map([['public/previews/r9-order-map.html',html],['engineering/order-map/provenance.json',JSON.stringify(provenance,null,2)+'\n']]);
}
if (process.argv[1]===fileURLToPath(import.meta.url)) {
 const check=process.argv.includes('--check');
 for(const [p,b] of build()) { if(check) { if(!read(p).equals(Buffer.from(b)))throw Error('Order map drift: '+p); } else fs.writeFileSync(root+p,b); }
 console.log(`Order map ${check?'verified':'built'}: 13 designs / 15 PA12 pieces.`);
}
