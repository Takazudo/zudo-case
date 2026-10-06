import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {makeData,build,sourceCommit} from '../engineering/order-map/build.mjs';
test('pinned PA12 order has exact designs, quantities and saved meshes',()=>{
 const d=makeData();assert.equal(sourceCommit,'541eca7f8ebc2e6da4375108b0d66773a0868b00');
 assert.equal(d.parts.length,13);assert.equal(d.parts.reduce((n,p)=>n+p.order_quantity,0),15);
 assert.deepEqual(d.parts.filter(p=>p.order_quantity===2).map(p=>p.part),['c1-06-guard','c1-07-guard']);
 assert.equal(d.parts.filter(p=>p.part.startsWith('c2')&&p.part.endsWith('guard')).length,1);
 const pinned={'order-prep/order-plan.json':'abe2a40e4bd85d784761eb1e899dec435fe2c454de98b1ca0dcd11ffb5b9bf98','fitfix/coupons.py':'ef02b1a4dcf7bb5d78aa83f2159b0dcbbb752557c1fd8c06ed5eedf021d40eea','fitfix/geometry.py':'e25a1f72dc356cffb2989ae9c444e929309bd6d50020c5c81e4f82431eaedb9c','out/scene.json':'884ead72c7661be55705b958a7c54b78afec3d4006fddf158d311c6901ca4354'};
 for(const [p,h] of Object.entries(pinned))assert.equal(createHash('sha256').update(readFileSync(new URL('../engineering/r9-fitfix-01/'+p,import.meta.url))).digest('hex'),h,p);
 for(const [id,f] of Object.entries(d.families)) {assert.ok(d.coupons[f.representative].meshes.some(m=>m.id===f.regionPart),id);for(const part of f.caseParts)assert.ok(d.caseMeshes.some(m=>m.id===part),part);}
});
test('checked-in standalone map is reproducible and all assets are embedded',()=>{
 for(const [path,content] of build())assert.equal(readFileSync(new URL('../'+path,import.meta.url),'utf8'),content,path);
 const html=readFileSync(new URL('../public/previews/r9-order-map.html',import.meta.url),'utf8');
 assert.ok(html.includes('lang="en"'));assert.ok(!html.includes('__DATA__'));assert.ok(!html.includes('<script src='));
});
