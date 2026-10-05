const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=__dirname;
globalThis.TwoWaySpec=JSON.parse(fs.readFileSync(path.resolve(root,'../../../project/two-way/study-spec.json')));
for(const f of ['frame-data.js','frame.js','model.js','renderer.js'])vm.runInThisContext(fs.readFileSync(path.join(root,'source',f),'utf8'),{filename:f});
vm.runInThisContext(['base-geometry.inc','frame-geometry.inc','closure.js'].map(f=>fs.readFileSync(path.join(root,'source',f),'utf8')).join('\n'),{filename:'geometry'});
module.exports={M:FoldModel,F:FoldFrame,G:FoldGeometry,R:FoldRenderer,D:ZudoFrameData};
