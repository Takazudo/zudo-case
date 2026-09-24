/* ZB60 local 3D viewer. All geometry, rendering dependencies and STL data are local. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const all = selector => Array.from(document.querySelectorAll(selector));
  const fail = error => {
    $('loadingState').hidden = true;
    $('webglError').hidden = false;
    $('errorDetails').textContent = error && error.message ? error.message : String(error);
    $('sceneStatus').textContent = '3D表示エラー';
    console.error(error);
  };
  try {
    if (!window.THREE || !window.ZUDO_CASE_FAMILY) throw new Error('同梱ファイルを読み込めません。ZIPをすべて展開してindex.htmlを開いてください。');
    start();
  } catch (error) { fail(error); }

  function start() {
    const THREE = window.THREE;
    const family = window.ZUDO_CASE_FAMILY;
    const modelLabels = {'3u60':'3U / 60HP','7u40':'7U / 40HP','7u60':'7U / 60HP'};
    const layoutLabels = {'3u60':'3U × 1列','7u40':'3U＋3U＋1U','7u60':'3U＋3U＋1U'};
    let data = family.models[family.defaultModel || '7u40'];
    const CATEGORIES = ['metal', 'guards', 'rails', 'spacers', 'feet', 'brackets', 'fasteners'];
    const categoryNames = {metal:'アルミ外板',guards:'PA12ガード',rails:'レール・固定パネル',spacers:'スペーサー・ワッシャー',feet:'ゴム脚',brackets:'L字ブラケット',fasteners:'ボルト・ナット'};
    const colored = {metal:0x879cac,guards:0xe8b264,rails:0x59b9b0,spacers:0xb79bd0,feet:0x947862,brackets:0x6b93c0,fasteners:0xd7dce3};
    const finished = {metal:0x383d43,guards:0x181a1e,rails:0xb6bdc6,spacers:0x25292c,feet:0x1e2328,brackets:0x90969e,fasteners:0xc0c5ce};
    const state = {model:family.defaultModel || '7u40',variant:'t1p2',explode:0,railLift:0,finish:'black',opacity:1,section:'none',edges:true,dimensions:false,
      visible:Object.fromEntries(CATEGORIES.map(x=>[x,true])),selected:null,view:'iso'};
    const viewport=$('viewport');
    const renderer=new THREE.WebGLRenderer({antialias:true,alpha:false,preserveDrawingBuffer:true});
    renderer.setPixelRatio(Math.min(window.devicePixelRatio||1,2));
    renderer.setClearColor(0xeef1f5,1);
    renderer.outputColorSpace=THREE.SRGBColorSpace;
    renderer.toneMapping=THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure=1.25;
    renderer.shadowMap.enabled=true;
    renderer.shadowMap.type=THREE.PCFSoftShadowMap;
    renderer.shadowMap.autoUpdate=false;
    renderer.localClippingEnabled=true;
    renderer.domElement.setAttribute('aria-label','回転・拡大できるZUDOケース。右側の操作欄から部品を切り替えられます。');
    renderer.domElement.setAttribute('role','img');
    viewport.appendChild(renderer.domElement);
    const scene=new THREE.Scene();
    const camera=new THREE.PerspectiveCamera(35,1,0.1,10000);
    camera.up.set(0,0,1);
    camera.position.set(440,-540,370);
    const controls=new window.OrbitControls(camera,renderer.domElement);
    controls.target.set(0,0,45);
    controls.enableDamping=true;
    controls.dampingFactor=.10;
    controls.minDistance=22;
    controls.maxDistance=3500;
    controls.maxPolarAngle=Math.PI-.005;
    controls.minPolarAngle=.005;
    controls.screenSpacePanning=true;
    const environment=new window.RoomEnvironment();
    const pmrem=new THREE.PMREMGenerator(renderer);
    const environmentTarget=pmrem.fromScene(environment,.04);
    scene.environment=environmentTarget.texture;
    environment.dispose?.();
    pmrem.dispose();
    scene.add(new THREE.HemisphereLight(0xffffff,0x6d7684,1.35));
    const key=new THREE.DirectionalLight(0xffffff,3.0);
    key.position.set(-180,-260,520);
    key.castShadow=true;
    key.shadow.mapSize.set(2048,2048);
    key.shadow.camera.left=-430;key.shadow.camera.right=430;
    key.shadow.camera.top=400;key.shadow.camera.bottom=-400;
    key.shadow.camera.near=1;key.shadow.camera.far=1300;
    key.shadow.bias=-.00035;key.shadow.normalBias=.4;
    scene.add(key);
    const fill=new THREE.DirectionalLight(0xdde9ff,1.4);fill.position.set(300,160,240);scene.add(fill);
    const floor=new THREE.Mesh(new THREE.PlaneGeometry(3000,3000),new THREE.MeshStandardMaterial({color:0xeef1f5,roughness:1,metalness:0}));
    floor.position.z=-3.5;floor.receiveShadow=true;scene.add(floor);
    const grid=new THREE.GridHelper(1000,40,0x9faaba,0xc5ccd5);
    grid.rotation.x=Math.PI/2;grid.material.transparent=true;grid.material.opacity=.22;grid.position.z=-3.47;scene.add(grid);
    const modelGroup=new THREE.Group();scene.add(modelGroup);
    const dimsGroup=new THREE.Group();scene.add(dimsGroup);
    const raycaster=new THREE.Raycaster();
    const pointer=new THREE.Vector2();
    let meshes=[], outline=null, frameCount=0, renderQueued=false;
    let fitOnNextResize=true, pointerDown=null;
    const fromHash=new URLSearchParams(window.location.hash.slice(1));
    if(family.models[fromHash.get('model')]){state.model=fromHash.get('model');data=family.models[state.model];}
    if(data.variants[fromHash.get('variant')])state.variant=fromHash.get('variant');
    if(['black','parts','silver'].includes(fromHash.get('finish')))state.finish=fromHash.get('finish');

    function requestRender() {
      if(renderQueued)return;
      renderQueued=true;
      requestAnimationFrame(()=>{
        renderQueued=false;
        controls.update();
        floor.visible=state.explode===0&&camera.position.z>floor.position.z+.1;
        grid.visible=floor.visible;
        renderer.render(scene,camera);
        frameCount++;
      });
    }

    function variant() { return data.variants[state.variant]; }
    function stats() {
      const s=variant().stats||{};
      return {volume:s.volumeCm3??s.totalVolumeCm3??0,thickness:s.thicknessMm??(state.variant==='t1p0'?1:1.2),
        coverage:s.coverageMm??s.coverMm??5,count:s.totalGuardParts??s.partCount??variant().parts.length,
        outer:s.outerDimensions??s.outerEnvelopeMm??data.meta.metalEnvelopeMm,feetOuter:s.feetIncludedEnvelopeMm};
    }
    const number=(n,d=1)=>Number(n).toFixed(d).replace(/(\.\d*?[1-9])0+$|\.0+$/,'$1');
    function setHash() { try { history.replaceState(null,'','#'+new URLSearchParams({model:state.model,variant:state.variant,finish:state.finish})); } catch (_) {} }
    function partColor(p) {
      if(state.finish==='parts')return {rail:0x59b9b0,fixer:0x6b93c0,padder:0xd7a477,innerSpacer:0xb79bd0,outerWasher:0xd6bcea,mountBolt:0xc3d1dd,mountNut:0xc3d1dd}[p.role]??colored[p.category];
      if(p.role==='rail')return 0x292d32;
      if(p.role==='fixer')return 0x343941;
      if(p.role==='padder')return 0x444950;
      if(state.finish==='silver'&&p.category==='metal')return 0xbac3cc;
      return finished[p.category];
    }
    function materialFor(p) {
      const metal=['metal','brackets','fasteners'].includes(p.category);
      return new THREE.MeshStandardMaterial({color:finished[p.category]??0x888888,metalness:metal?.75:.02,
        roughness:p.category==='guards'?.91:metal?.42:.85,envMapIntensity:metal?1.2:.75,side:THREE.DoubleSide});
    }
    function makeMesh(p) {
      const g=new THREE.BufferGeometry();
      g.setAttribute('position',new THREE.Float32BufferAttribute(p.positions,3));
      if(p.indices?.length)g.setIndex(p.indices);
      if(p.normals?.length===p.positions.length)g.setAttribute('normal',new THREE.Float32BufferAttribute(p.normals,3));
      else g.computeVertexNormals();
      g.computeBoundingBox();g.computeBoundingSphere();
      const mesh=new THREE.Mesh(g,materialFor(p));
      mesh.name=p.id;mesh.userData.part=p;mesh.castShadow=true;mesh.receiveShadow=true;
      const line=new THREE.LineSegments(new THREE.EdgesGeometry(g,28),new THREE.LineBasicMaterial({color:0x5c646e,transparent:true,opacity:.4}));
      line.name='edge-lines';line.userData.isEdge=true;mesh.add(line);
      return mesh;
    }
    function disposeMesh(mesh) { mesh.geometry.dispose();mesh.material.dispose();mesh.children.forEach(c=>{c.geometry?.dispose();c.material?.dispose();}); }
    function rebuild() {
      selectPart(null);
      for(const mesh of meshes){modelGroup.remove(mesh);disposeMesh(mesh);}
      meshes=[...(data.commonParts||[]),...variant().parts].map(makeMesh);
      meshes.forEach(m=>modelGroup.add(m));
      buildPartTable();
      buildDimensions();
      update();
    }
    function clippingPlanes() {
      if(state.section==='front')return [new THREE.Plane(new THREE.Vector3(0,1,0),0)];
      if(state.section==='right')return [new THREE.Plane(new THREE.Vector3(-1,0,0),0)];
      return [];
    }
    function update() {
      const planes=clippingPlanes();
      for(const mesh of meshes){
        const p=mesh.userData.part;
        const e=p.explode||[0,0,0];
        mesh.position.set(e[0]*state.explode,e[1]*state.explode,e[2]*state.explode);
        if(p.group==='railUnit')mesh.position.z+=state.railLift;
        if(['spacers','outerWashers','mountBolts','mountNuts','mountFasteners'].includes(p.group)) {
          const c=p.center||[0,0,0],sign=c[0]<0?-1:1;
          const distance={spacers:26,outerWashers:42,mountNuts:58,mountBolts:-35,mountFasteners:47}[p.group];
          mesh.position.x+=sign*Math.min(state.railLift/22,1)*distance;
        }
        mesh.visible=!!state.visible[p.category];
        const mat=mesh.material;
        const color=partColor(p);
        mat.color.setHex(color??0x888888);
        mat.opacity=p.category==='metal'?state.opacity:1;
        mat.transparent=mat.opacity<1;
        mat.depthWrite=!mat.transparent;
        mat.clippingPlanes=planes;
        mat.clipShadows=true;
        mat.needsUpdate=true;
        mat.emissive.setHex(p.id===state.selected?0x267e87:0x000000);
        mat.emissiveIntensity=p.id===state.selected?.40:0;
        const line=mesh.children[0];line.visible=state.edges;
        line.material.opacity=p.category==='metal'?Math.min(.45,state.opacity*.55):.48;
        line.material.color.setHex(state.finish==='parts'?0x384754:0x59636e);
        line.material.clippingPlanes=planes;line.material.needsUpdate=true;
      }
      modelGroup.updateMatrixWorld(true);
      const box=visibleBounds();
      floor.position.z=(box.isEmpty()?-3:box.min.z)-.25;grid.position.z=floor.position.z+.03;
      floor.visible=state.explode===0;grid.visible=floor.visible;
      dimsGroup.visible=state.dimensions;
      if(outline)outline.update();
      if(state.selected&&!meshes.find(m=>m.name===state.selected)?.visible)selectPart(null);
      renderer.shadowMap.needsUpdate=true;
      requestRender();
      syncUI();
    }
    function syncUI() {
      const s=stats();
      all('[data-model]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.model===state.model)));
      $('modelBadge').textContent=modelLabels[state.model];
      $('modelSubtitle').textContent=layoutLabels[state.model]+' / '+(state.model.endsWith('40')?'40HP':'60HP')+' / アルミ５枚';
      $('modelSize').innerHTML=data.meta.metalEnvelopeMm.map(x=>number(x,1)).join(' × ')+' <small>mm · 金属外形 W × D × H</small>';
      $('modelDescription').textContent=state.model==='3u60'?'前後の余白を約8mmに詰めた、１列のケースです。':'３列が同じ高さに並ぶ、奥行のあるトレー形状です。';
      all('[data-variant]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.variant===state.variant)));
      $('volumeValue').innerHTML=number(s.volume,3)+' <small>cm³</small>';
      $('coverageValue').innerHTML=number(s.coverage)+' <small>mm</small>';
      $('quoteNote').textContent=`１台分のガード ${s.count}個 · 新寸法／再見積用`;
      $('variantBadge').textContent=variant().label||('R6 / '+number(s.thickness,1)+' mm');
      $('finishBadge').textContent={black:'黒アルマイト',parts:'部品の識別色',silver:'シルバーで確認'}[state.finish];
      $('explodeSlider').value=Math.round(state.explode*100);$('explodeValue').textContent=Math.round(state.explode*100)+'%';
      $('railLiftSlider').value=state.railLift;$('railLiftValue').textContent=number(state.railLift,0)+' mm';
      $('opacitySlider').value=Math.round(state.opacity*100);$('opacityValue').textContent=Math.round(state.opacity*100)+'%';
      $('finishSelect').value=state.finish;$('sectionSelect').value=state.section;
      $('edgesCheck').checked=state.edges;$('dimensionsCheck').checked=state.dimensions;
      syncSpecs(s);
      all('[data-category]').forEach(input=>{input.checked=state.visible[input.dataset.category];});
      all('[data-count]').forEach(el=>{el.textContent=meshes.filter(m=>m.userData.part.category===el.dataset.count).length;});
      all('[data-swatch]').forEach(el=>{const c=state.finish==='parts'?colored[el.dataset.swatch]:finished[el.dataset.swatch];el.style.backgroundColor='#'+c.toString(16).padStart(6,'0');});
      all('[data-preset]').forEach(b=>{
        const active=b.dataset.preset==='assembled'?state.explode===0&&state.railLift===0:b.dataset.preset==='exploded'?state.explode>=.65&&state.railLift===0:state.explode===0&&state.railLift>0;
        b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active));
      });
      all('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===state.view));
      $('sceneStatus').textContent=`${meshes.filter(m=>m.visible).length} / ${meshes.length} パーツ表示`+(state.section!=='none'?' · 断面表示':'');
      setHash();
    }
    function syncSpecs(s) {
      const m=data.meta,fmt=a=>a.map(x=>number(x,3)).join(' × ')+' mm', mountCount=data.commonParts.filter(p=>p.role==='innerSpacer').length;
      const rows=[
        ['構成',layoutLabels[state.model]],
        ['アルミ外形',fmt(m.metalEnvelopeMm)],
        ['アルミ板厚',number(m.metalThicknessMm,3)+' mm'],
        ['ガード外形（脚・ネジ除く）',fmt(s.outer)],
        ['脚を含む高さ',number(s.feetOuter?.[2]??(m.metalEnvelopeMm[2]+s.thickness+3),1)+' mm（仮の脚3mm）'],
        ['底面の脚','φ10 × 3 mm、４個（仮配置）'],
        ['レール長',number(m.railLengthMm,3)+' mm'],
        ['レールユニット外幅',number(m.railFrameWidthMm,3)+' mm'],
        ['fixer / padder厚',number(m.fixerThicknessMm,3)+' / '+number(m.padderThicknessMm,3)+' mm（PCB）'],
        ['内側スペーサー',number(m.spacerThicknessMm,3)+' mm × '+mountCount+'個'],
        ['外側ワッシャー',number(m.outerWasherThicknessMm,3)+' mm × '+mountCount+'個'],
        ['締付積層長',number(m.mountingGripMm,3)+' mm'],
        ['外箱取付ネジの頭', '厚さ1.4mm（ユーザー実測）'],
        ['前後の余白',number((m.metalEnvelopeMm[1]-2*m.metalThicknessMm-(m.railUnitDepthMm || (state.model==='3u60'?134.53186:314.754456)))/2,3)+' mm / 片側'],
        ['取付軸の高さ',`底板下面から ${number(m.railMountZMm,3)} mm`],
        ['外板の穴',`φ5.5 × ${m.panelHoleCount}か所`]
      ];
      const signature=JSON.stringify(rows);
      if($('specTable').dataset.signature===signature)return;
      $('specTable').dataset.signature=signature;
      $('specTable').replaceChildren();
      for(const row of rows){const tr=document.createElement('tr');for(const cell of row){const td=document.createElement('td');td.textContent=cell;tr.appendChild(td);}$('specTable').appendChild(tr);}
      $('stackFixerName').textContent=(state.model==='3u60'?'3U':'7U')+' fixer';
      $('stackFixer').textContent='PCB '+number(m.fixerThicknessMm,3)+' mm';
      $('assumptionsList').replaceChildren();
      const notes=m.assumptions||['PCB厚1.6mm、平頭ネジの頭厚1.4mmを反映。','ブラケット厚は実測2mm、干渉確認は2.2mm。ブラケット穴中心と頭の直径は仮設定。'];
      for(const note of notes){const li=document.createElement('li');li.textContent=note;$('assumptionsList').appendChild(li);}
    }
    function visibleBounds(onlySelected=false) {
      const b=new THREE.Box3();
      for(const mesh of meshes){
        if(!mesh.visible||(onlySelected&&mesh.name!==state.selected))continue;
        b.union(mesh.geometry.boundingBox.clone().applyMatrix4(mesh.matrixWorld));
      }
      if(b.isEmpty()){const [w,d,h]=data.meta.metalEnvelopeMm;b.set(new THREE.Vector3(-w/2,-d/2,0),new THREE.Vector3(w/2,d/2,h));}
      return b;
    }
    function fit(direction=null,onlySelected=false) {
      // Consume any residual orbit/pan damping before moving to a fixed view.
      const damping=controls.enableDamping;
      controls.enableDamping=false;
      controls.update();
      modelGroup.updateMatrixWorld(true);
      const box=visibleBounds(onlySelected),center=box.getCenter(new THREE.Vector3());
      const dir=direction?new THREE.Vector3(...direction).normalize():camera.position.clone().sub(controls.target).normalize();
      const right=new THREE.Vector3().crossVectors(camera.up,dir).normalize();
      const up=new THREE.Vector3().crossVectors(dir,right).normalize();
      const tanV=Math.tan(THREE.MathUtils.degToRad(camera.fov/2)),tanH=tanV*camera.aspect;
      let distance=0;
      for(const x of [box.min.x,box.max.x])for(const y of [box.min.y,box.max.y])for(const z of [box.min.z,box.max.z]){
        const p=new THREE.Vector3(x,y,z).sub(center);
        distance=Math.max(distance,p.dot(dir)+Math.max(Math.abs(p.dot(right))/tanH,Math.abs(p.dot(up))/tanV));
      }
      distance=Math.max(distance*(onlySelected?1.40:1.30),40);
      controls.target.copy(center);camera.position.copy(center).addScaledVector(dir,distance);
      camera.lookAt(center);controls.update();
      controls.enableDamping=damping;
      requestRender();
    }
    function setView(name) {
      const views={iso:[1,-1.3,.92],front:[0,-1,.0001],side:[1,0,.0001],top:[0,-.005,1],bottom:[0,-.005,-1]};
      state.view=name;fit(views[name]||views.iso);syncUI();
    }
    function setPreset(name) {
      state.explode=name==='exploded'?.8:0;state.railLift=name==='rail'?118:0;
      state.section='none';state.opacity=1;
      CATEGORIES.forEach(c=>state.visible[c]=true);
      update();setView('iso');
    }
    function downloadStl(file) {
      const source=window.ZB60_STL_FILES?.[file];
      if(!source)return;
      const raw=atob(source),bytes=new Uint8Array(raw.length);
      for(let i=0;i<raw.length;i++)bytes[i]=raw.charCodeAt(i);
      const url=URL.createObjectURL(new Blob([bytes],{type:'model/stl'}));
      const a=document.createElement('a');a.href=url;a.download=file;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
    }
    function buildPartTable() {
      const body=$('partsTable');body.replaceChildren();
      const groups=new Map();
      for(const p of variant().parts){
        const key=p.stlFile||p.partType||p.name;
        if(!groups.has(key))groups.set(key,{part:p,count:0});groups.get(key).count++;
      }
      for(const {part:p,count} of groups.values()){
        const tr=document.createElement('tr'),nameCell=document.createElement('td'),qtyCell=document.createElement('td'),downloadCell=document.createElement('td');
        const button=document.createElement('button');button.type='button';button.className='part-name-button';
        const labels={top_corner_a:'上端L字 A',top_corner_b:'上端L字 B',lower_width_half:'前後の下辺・半分',lower_depth_full:'左右の下辺',lower_depth_half_a:'左右の下辺・半分 A',lower_depth_half_b:'左右の下辺・半分 B',top_u:'上端U字',lower_half:'下辺・半分',lower_side:'左右の下辺',vertical_corner:'縦辺の角',top_rim:'上端一体枠',lower_long:'前後の下辺',lower_short_notched:'左右の下辺'};
        button.textContent=labels[p.partType]||p.name.replace(/［.*?］|\(.*?\)|（.*?）/g,'');
        button.addEventListener('click',()=>{state.visible.guards=true;update();selectPart(p.id);});nameCell.appendChild(button);
        qtyCell.textContent=String(count);
        if(p.stlFile&&window.ZB60_STL_FILES?.[p.stlFile]){
          const dl=document.createElement('button');dl.type='button';dl.className='stl-button';dl.textContent='STL';dl.setAttribute('aria-label',button.textContent+'のSTLを保存');dl.addEventListener('click',()=>downloadStl(p.stlFile));downloadCell.appendChild(dl);
        }else downloadCell.textContent='—';
        tr.append(nameCell,qtyCell,downloadCell);body.appendChild(tr);
      }
    }
    function selectPart(id) {
      if(outline){scene.remove(outline);outline.geometry.dispose();outline.material.dispose();outline=null;}
      state.selected=id;
      meshes.forEach(m=>{m.material.emissive.setHex(m.name===id?0x267e87:0);m.material.emissiveIntensity=m.name===id?.4:0;});
      const mesh=meshes.find(m=>m.name===id);
      $('selectedCard').classList.toggle('hidden',!mesh);
      requestRender();
      if(!mesh)return;
      const p=mesh.userData.part;
      $('selectedCategory').textContent=categoryNames[p.category]||p.category;
      $('selectedName').textContent=p.name;
      const size=mesh.geometry.boundingBox.getSize(new THREE.Vector3());
      $('selectedDimensions').textContent=[size.x,size.y,size.z].map(x=>number(x,2)).join(' × ')+' mm';
      $('selectedNote').textContent=p.note||(p.category==='guards'?'STLと同じ形状。保持方法と取付公差は未設計です。':'構造確認用のモデルです。');
      $('downloadPartButton').hidden=!(p.stlFile&&window.ZB60_STL_FILES?.[p.stlFile]);
      outline=new THREE.BoxHelper(mesh,0x339da8);outline.material.depthTest=false;outline.material.transparent=true;outline.material.opacity=.8;outline.renderOrder=100;scene.add(outline);
    }
    function addDimension(a,b,label,offset) {
      const color=0x546677;
      const vertices=[...a,...b];
      const line=new THREE.Line(new THREE.BufferGeometry().setAttribute('position',new THREE.Float32BufferAttribute(vertices,3)),new THREE.LineBasicMaterial({color,depthTest:false}));
      line.renderOrder=40;dimsGroup.add(line);
      const delta=new THREE.Vector3(...b).sub(new THREE.Vector3(...a)).normalize();
      for(const [point,direction] of [[a,delta],[b,delta.clone().negate()]]){
        const arrow=new THREE.ArrowHelper(direction,new THREE.Vector3(...point),8,color,6,3);arrow.line.material.depthTest=false;arrow.cone.material.depthTest=false;arrow.renderOrder=40;dimsGroup.add(arrow);
      }
      const canvas=document.createElement('canvas');canvas.width=512;canvas.height=128;const ctx=canvas.getContext('2d');
      ctx.fillStyle='rgba(238,241,245,0.95)';ctx.fillRect(0,0,512,128);ctx.fillStyle='#324d60';ctx.font='500 56px system-ui';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(label,256,66);
      const texture=new THREE.CanvasTexture(canvas);texture.colorSpace=THREE.SRGBColorSpace;
      const sprite=new THREE.Sprite(new THREE.SpriteMaterial({map:texture,depthTest:false,transparent:true}));sprite.scale.set(66,16.5,1);
      sprite.position.copy(new THREE.Vector3(...a).add(new THREE.Vector3(...b)).multiplyScalar(.5)).add(new THREE.Vector3(...offset));sprite.renderOrder=45;dimsGroup.add(sprite);
    }
    function buildDimensions() {
      for(const c of [...dimsGroup.children]){c.traverse(o=>{o.geometry?.dispose();if(o.material){o.material.map?.dispose();o.material.dispose();}});dimsGroup.remove(c);}
      const [metalW,metalD,metalH]=data.meta.metalEnvelopeMm;
    addDimension([-metalW/2,-metalD/2-25,-7],[metalW/2,-metalD/2-25,-7],number(metalW,1)+' mm',[0,-6,-3]);
    addDimension([metalW/2+25,-metalD/2,-7],[metalW/2+25,metalD/2,-7],number(metalD,1)+' mm',[15,0,-3]);
    addDimension([metalW/2+27,metalD/2+20,0],[metalW/2+27,metalD/2+20,metalH],number(metalH,1)+' mm',[13,9,0]);
    dimsGroup.visible=state.dimensions;
    }

    function setModel(key) {
      if(!family.models[key])return;
      state.model=key;data=family.models[key];state.selected=null;
      if(!data.variants[state.variant])state.variant='t1p2';
      rebuild();setView(state.view==='custom'?'iso':state.view);
    }
    all('[data-model]').forEach(b=>b.addEventListener('click',()=>setModel(b.dataset.model)));
    all('[data-variant]').forEach(b=>b.addEventListener('click',()=>{state.variant=b.dataset.variant;rebuild();fit();}));
    all('[data-preset]').forEach(b=>b.addEventListener('click',()=>setPreset(b.dataset.preset)));
    all('[data-view]').forEach(b=>b.addEventListener('click',()=>setView(b.dataset.view)));
    $('explodeSlider').addEventListener('input',e=>{state.explode=Number(e.target.value)/100;update();fit();});
    $('railLiftSlider').addEventListener('input',e=>{state.railLift=Number(e.target.value);update();fit();});
    $('opacitySlider').addEventListener('input',e=>{state.opacity=Number(e.target.value)/100;update();});
    $('finishSelect').addEventListener('change',e=>{state.finish=e.target.value;update();});
    $('sectionSelect').addEventListener('change',e=>{state.section=e.target.value;update();});
    $('edgesCheck').addEventListener('change',e=>{state.edges=e.target.checked;update();});
    $('dimensionsCheck').addEventListener('change',e=>{state.dimensions=e.target.checked;update();});
    all('[data-category]').forEach(input=>input.addEventListener('change',()=>{state.visible[input.dataset.category]=input.checked;update();}));
    $('showAllButton').addEventListener('click',()=>{CATEGORIES.forEach(c=>state.visible[c]=true);update();});
    $('guardsOnlyButton').addEventListener('click',()=>{CATEGORIES.forEach(c=>state.visible[c]=c==='guards');update();fit();});
    $('insideButton').addEventListener('click',()=>{CATEGORIES.forEach(c=>state.visible[c]=true);state.visible.metal=false;state.visible.guards=false;state.explode=0;state.railLift=0;update();setView('iso');});
    $('clearSelection').addEventListener('click',()=>selectPart(null));
    $('focusPartButton').addEventListener('click',()=>fit(null,true));
    $('downloadPartButton').addEventListener('click',()=>{const p=meshes.find(m=>m.name===state.selected)?.userData.part;if(p?.stlFile)downloadStl(p.stlFile);});
    $('fitButton').addEventListener('click',()=>fit());
    $('resetButton').addEventListener('click',()=>{Object.assign(state,{variant:'t1p2',explode:0,railLift:0,finish:'black',opacity:1,section:'none',edges:true,dimensions:false,view:'iso'});CATEGORIES.forEach(c=>state.visible[c]=true);rebuild();setView('iso');});
    $('helpButton').addEventListener('click',()=>{$('helpDetails').open=!$('helpDetails').open;if($('helpDetails').open)$('helpSection').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'nearest'});});
    $('screenshotButton').addEventListener('click',()=>{renderer.render(scene,camera);const a=document.createElement('a');a.download='zudo-'+state.model+'-r6-'+state.variant+'-'+(state.explode?'exploded':state.railLift?'rail-lift':'assembled')+'.png';a.href=renderer.domElement.toDataURL('image/png');a.click();});
    renderer.domElement.addEventListener('pointerdown',e=>{pointerDown={x:e.clientX,y:e.clientY,button:e.button};});
    renderer.domElement.addEventListener('pointerup',e=>{
      if(!pointerDown||pointerDown.button!==0||Math.hypot(e.clientX-pointerDown.x,e.clientY-pointerDown.y)>5){pointerDown=null;return;}
      pointerDown=null;
      const rect=renderer.domElement.getBoundingClientRect();pointer.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);
      raycaster.setFromCamera(pointer,camera);
      const planes=clippingPlanes();
      const hit=raycaster.intersectObjects(meshes.filter(m=>m.visible),false).find(h=>planes.every(p=>p.distanceToPoint(h.point)>=0));
      selectPart(hit?.object.name||null);
    });
    renderer.domElement.addEventListener('webglcontextlost',e=>{e.preventDefault();fail(new Error('WebGLコンテキストが失われました。ページを再読み込みしてください。'));});
    controls.addEventListener('start',()=>{state.view='custom';all('[data-view]').forEach(b=>b.classList.remove('active'));});
    controls.addEventListener('change',requestRender);
    const resize=()=>{
      const width=viewport.clientWidth,height=viewport.clientHeight;
      if(!width||!height)return;
      renderer.setSize(width,height,false);camera.aspect=width/height;camera.updateProjectionMatrix();
      if(fitOnNextResize){fitOnNextResize=false;setView('iso');}
      requestRender();
    };
    rebuild();resize();
    new ResizeObserver(resize).observe(viewport);
    requestRender();
    $('loadingState').hidden=true;
    window.ZB60_VIEWER={
      ready:true,
      setModel,
      getState:()=>({...JSON.parse(JSON.stringify(state)),stats:stats(),meshCount:meshes.length,visibleCount:meshes.filter(m=>m.visible).length,
        frameCount,webgl:renderer.capabilities.isWebGL2?'WebGL2':'WebGL',canvasSize:[renderer.domElement.width,renderer.domElement.height],
        parts:meshes.map(m=>({id:m.name,category:m.userData.part.category,role:m.userData.part.role,group:m.userData.part.group,visible:m.visible,position:m.position.toArray(),stlFile:m.userData.part.stlFile})),
        camera:camera.position.toArray(),target:controls.target.toArray()}),
      setVariant:key=>{if(data.variants[key]){state.variant=key;rebuild();fit();}},setPreset,setView,selectPart,
      projectPart:id=>{const mesh=meshes.find(m=>m.name===id);if(!mesh)return null;const point=mesh.geometry.boundingBox.getCenter(new THREE.Vector3()).add(mesh.position).project(camera);const r=renderer.domElement.getBoundingClientRect();return {x:r.left+(point.x+1)*r.width/2,y:r.top+(1-point.y)*r.height/2};}
    };
  }
})();
