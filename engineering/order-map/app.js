(async () => {
  const $ = id => document.getElementById(id);
  try {
    const compressed = Uint8Array.from(atob('__DATA__'), c => c.charCodeAt(0));
    const data = JSON.parse(await new Response(new Blob([compressed]).stream().pipeThrough(new DecompressionStream('gzip'))).text());
    const T = window.THREE;
    const families = data.families;
    const rows = () => mode === 'aluminum' ? data.aluminum : data.parts;
    const firstPart = code => rows().find(p => p.part.startsWith(code.toLowerCase()))?.part || rows()[0].part;
    let family = 'C1', selected = data.parts[0].part, separated = true, mode = 'pa12', revision = 'revised';
    const views = [];
    function view(id) {
      const host = $(id), scene = new T.Scene();
      const renderer = new T.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
      renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); renderer.setClearColor(0xeaf0f3);
      host.prepend(renderer.domElement);
      const camera = new T.PerspectiveCamera(38, 1, .1, 5000); camera.up.set(0, 0, 1);
      const controls = new window.OrbitControls(camera, renderer.domElement); controls.enableDamping = true;
      scene.add(new T.HemisphereLight(0xffffff, 0x8199a5, 2.5));
      const light = new T.DirectionalLight(0xffffff, 3); light.position.set(150, -250, 500); scene.add(light);
      const group = new T.Group(); scene.add(group);
      const v = { host, scene, renderer, camera, controls, group, meshes: [], markers: [] };
      function resize() { renderer.setSize(host.clientWidth, host.clientHeight); camera.aspect = host.clientWidth / host.clientHeight; camera.updateProjectionMatrix(); if (v.meshes.length) fit(v); }
      new ResizeObserver(resize).observe(host); views.push(v); return v;
    }
    const whole = view('case-view'), detail = view('detail-view');
    function add(v, item, color, opacity = 1) {
      const geometry = new T.BufferGeometry(); geometry.setAttribute('position', new T.Float32BufferAttribute(item.positions, 3)); geometry.setIndex(item.indices); geometry.computeVertexNormals(); geometry.computeBoundingBox();
      const material = new T.MeshStandardMaterial({ color, roughness: .65, side: T.DoubleSide, transparent: opacity < 1, opacity, depthWrite: opacity === 1 });
      const m = new T.Mesh(geometry, material); m.userData = item; v.group.add(m); v.meshes.push(m); return m;
    }
    function clear(v) { for (const m of v.meshes) { m.geometry.dispose(); m.material.dispose(); v.group.remove(m); } v.meshes = []; }
    function fit(v) {
      const box = new T.Box3(); for (const m of v.meshes) if (m.visible) box.expandByObject(m);
      const center = box.getCenter(new T.Vector3()), size = box.getSize(new T.Vector3());
      const half = Math.min(v.camera.fov * Math.PI / 360, Math.atan(Math.tan(v.camera.fov * Math.PI / 360) * v.camera.aspect));
      const distance = size.length() / 2 / Math.sin(half) * 1.15;
      v.controls.target.copy(center);
      let direction = v === whole ? new T.Vector3(-.85, -1.2, .85) : (family === 'C1' ? new T.Vector3(1, -1.5, -.9) : new T.Vector3(1, 1.6, .9));
      if (v === detail && mode === 'aluminum') { const p=data.aluminum.find(p=>p.part===selected), a=p.thickness_axis_in_exported_step; direction=new T.Vector3(.3,.3,.3); direction.setComponent(a,1); }
      v.camera.position.copy(center).add(direction.normalize().multiplyScalar(distance)); v.controls.update();
    }
    function renderCase() {
      clear(whole);
      for (const item of data.caseMeshes) {
        const metal = ['metal', 'lidMetal'].includes(item.group), lid = ['lid', 'lidMetal'].includes(item.group);
        const active = families[family].caseParts.includes(item.id);
        const m = add(whole, item, active ? 0x008a90 : metal ? 0x9baab3 : 0xd99a37, metal && $('shell').checked ? .16 : active ? 1 : .58);
        if (lid) { m.position.z = 60; m.visible = $('lid').checked; }
        m.userData = { ...item, caseFamily: active ? family : undefined };
      }
      // The highlighted coupon region uses the saved coupon mesh, not a fabricated block.
      const f = families[family], source = f.representative && data.coupons[f.representative].meshes.find(m => m.id === f.regionPart);
      if (source) {
      const region = add(whole, source, 0x00a6ad); region.userData.caseFamily = family;
      if (family === 'C1') { region.rotation.z = -Math.PI / 2; region.position.set(-60, -167, 91); }
      }
      // C2 region is the shared guard at the body/lid seating interface, not the raised lid.
      fit(whole);
    }
    function renderDetail() {
      clear(detail);
      if (mode === 'aluminum') {
        const p=data.aluminum.find(p=>p.part===selected);
        add(detail,p.meshes[revision],0x387e88);
        $('detail-note').textContent=(revision==='revised' ? 'R9-ANODIZING-01 · actual Ø4 mm cut' : 'Original ordered geometry · no hanging hole')+' · individual manufacturing plate';
        fit(detail); return;
      }
      const key = selected.slice(0, 5).toUpperCase();
      let items = data.coupons[key].meshes;
      if (family === 'C1') items = [...items, ...data.coupons['C1-METAL'].meshes];
      for (let item of items) {
        const metalId=family==='C2' ? item.id.replace(/^c2-0[23]-/,'c2-01-') : item.id;
        const replacement=data.aluminum.find(p=>p.part===metalId);
        if(replacement && revision==='revised') item={...replacement.meshes.revised,id:item.id};
        const metal = item.group === 'metal';
        const orderedId = family === 'C2' && item.id.endsWith('-guard') ? 'c2-01-guard' : item.id;
        const m = add(detail, item, metal ? 0x9baab3 : orderedId === selected ? 0x008a90 : 0xd99a37, metal ? .68 : 1);
        m.userData = { ...item, orderedId }; m.visible = !metal || $('metal').checked;
        if (separated) {
          if (family === 'C1' && metal) m.position.x = -7;
          if (family === 'C2') { if (item.group === 'lid') m.position.z = 24; else if (item.id.endsWith('-plate')) m.position.z = 40; else if (item.group === 'guards') m.position.z = 4; }
          if (family === 'C4') { if (item.id.endsWith('-floor')) m.position.z = -5; if (item.id.endsWith('-wall')) m.position.y = 7; }
          if (family === 'C5') { if (item.id.endsWith('-front')) m.position.y = 7; else if (item.id.endsWith('-left')) m.position.x = 7; else m.position.z = 5; }
        }
        if (family === 'C1' && !metal && data.parts.find(p => p.part === selected).order_quantity === 2) {
          const second = add(detail, item, 0x008a90); second.position.y = selected.includes('06') ? 20.25 : 20; second.userData = { ...item, orderedId };
        }
      }
      $('detail-note').textContent = separated ? 'Separated for explanation · spacing is illustrative' : 'Nominal assembled relationship · rotate to inspect';
      $('separate').setAttribute('aria-pressed', String(separated)); $('assembled').setAttribute('aria-pressed', String(!separated)); fit(detail);
    }
    function updateLink() { const hash = '#part=' + encodeURIComponent(selected)+'&revision='+revision; history.replaceState(null, '', hash); $('share-link').value = location.href; }
    function select(part, writeHash = true) {
      mode=data.aluminum.some(p=>p.part===part)?'aluminum':'pa12';
      if (!rows().some(p => p.part === part)) part = rows()[0].part;
      $('material').value=mode; $('revision').value=revision;
      $('part').replaceChildren(); for(const p of rows()) $('part').add(new Option(`${p.label} · qty ${p.order_quantity}`,p.part));
      $('part-label').textContent=mode==='aluminum'?'Aluminum plate (13 pieces)':'Ordered PA12 design';
      $('count').textContent=mode==='aluminum'?'13 aluminum plates · separate metal order':'13 designs · 15 PA12 pieces';
      $('metal-controls').hidden=mode==='aluminum';
      $('detail-legend').hidden=mode==='aluminum';
      for(const id of ['separate','assembled']) $(id).disabled=mode==='aluminum';
      document.querySelectorAll('[data-family=C3]').forEach(b=>b.hidden=mode!=='aluminum');
      document.querySelectorAll('.family span').forEach(span=>{ const code=span.parentElement.dataset.family; if(!span.dataset.original)span.dataset.original=span.innerHTML; span.innerHTML=mode==='aluminum'?families[code].function+'<br>'+data.aluminum.filter(p=>p.part.startsWith(code.toLowerCase())).length+' aluminum plate(s)':span.dataset.original; });
      $('revision-note').textContent=(revision==='revised'?'R9-ANODIZING-01: one Ø4 mm hole per aluminum plate.':'Original ordered aluminum: no dedicated hanging holes.')+' PA12 is unchanged. Whole-case geometry is unchanged illustrative context.';
      selected = part; family = part.slice(0, 2).toUpperCase(); const f = families[family], p = rows().find(p => p.part === part);
      document.querySelectorAll('[data-family]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.family === family)));
      $('part').value = selected; $('family-code').textContent = family + ' / ' + f.function; $('family-title').textContent = f.title;
      for (const id of ['where', 'fits', 'priority', 'mapping', 'consistency', 'neighbors']) $(id).textContent = f[id];
      $('part-name').textContent = p.label; $('part-description').textContent = p.description;
      $('part-count').textContent = `Order quantity: ${p.order_quantity} · ${mode==='aluminum'?'One STEP/DXF pair describes one plate':'One STL describes one piece'} · Nominal envelope: ${p.dimensions_mm.map(n => Number(n.toFixed(2))).join(' × ')} mm`;
      $('detail-title').textContent = p.label + (p.order_quantity === 2 ? ' · both ordered pieces shown' : ' · selected in teal');
      $('part-list').replaceChildren();
      for (const row of rows().filter(p => p.part.startsWith(family.toLowerCase()))) { const b = document.createElement('button'); b.textContent = row.label + ' ×' + row.order_quantity; b.setAttribute('aria-pressed', String(row.part === selected)); b.onclick = () => select(row.part); $('part-list').append(b); }
      $('hole-info').hidden=mode!=='aluminum';
      if(mode==='aluminum') {
        $('hole-info').textContent=(revision==='revised'?`Ø${p.diameter_mm} mm · edge ligament ${p.checks.edge_ligament_mm} mm · local U,V = ${p.hole_center_uv_mm.join(', ')} mm`:'Original: no dedicated hanging hole')+' · functional holes/slots unchanged.';
        $('file-map').textContent=p.old_files.find(f=>f.path.endsWith('.step')).path.split('/').pop()+' → '+p.new_files.find(f=>f.path.endsWith('.step')).path.split('/').pop();
        $('revision-source').href='https://github.com/Takazudo/zudo-case/tree/d63eb70084a502746eb9a8593fa087e6fdd5a51c/engineering/r9-anodizing-01';
      } else $('file-map').textContent='Aluminum mating references use the selected revision; PA12 meshes remain the original ordered designs.';
      renderCase(); renderDetail(); if (writeHash) updateLink(); else $('share-link').value = location.href;
      window.orderMapState = { family, selected, separated, mode, revision, designs: data.parts.length, pieces: data.parts.reduce((n, p) => n + p.order_quantity, 0) };
    }
    $('material').onchange=()=>{mode=$('material').value;select(firstPart(family));};
    $('revision').onchange=()=>{revision=$('revision').value;select(selected);};
    $('part').onchange = () => select($('part').value);
    document.querySelectorAll('.family').forEach(b => b.onclick = () => select(firstPart(b.dataset.family)));
    const ns='http://www.w3.org/2000/svg', leaders=document.createElementNS(ns,'svg');leaders.style.cssText='position:absolute;inset:0;width:100%;height:100%;pointer-events:none';$('markers').append(leaders);
    const offsets={C1:[-4,-35],C2:[38,-36],C3:[-35,52],C4:[38,22],C5:[-40,14]};
    for (const [key, f] of Object.entries(families)) { const b = document.createElement('button'); b.className = 'marker'; b.dataset.family = key; b.textContent = key; b.setAttribute('aria-label', key + ': ' + f.title); b.onclick = () => select(firstPart(key)); const line=document.createElementNS(ns,'line');line.setAttribute('stroke','#466a76');line.setAttribute('stroke-width','1.5');leaders.append(line);$('markers').append(b); whole.markers.push({ button: b, line, offset:offsets[key], point: new T.Vector3(...f.point) }); }
    for (const id of ['shell', 'lid']) $(id).onchange = renderCase;
    $('metal').onchange = renderDetail;
    $('separate').onclick = () => { separated = true; renderDetail(); window.orderMapState.separated = true; };
    $('assembled').onclick = () => { separated = false; renderDetail(); window.orderMapState.separated = false; };
    $('reset-case').onclick = () => fit(whole); $('reset-detail').onclick = () => fit(detail);
    $('source').href = 'https://github.com/Takazudo/zudo-case/tree/' + data.sourceCommit + '/engineering/r9-fitfix-01/order-prep';
    $('count').textContent = `${data.parts.length} designs · ${data.parts.reduce((n, p) => n + p.order_quantity, 0)} PA12 pieces`;
    $('copy').onclick = async () => { try { await navigator.clipboard.writeText(location.href); $('copy-status').textContent = 'Link copied'; } catch { $('share-link').focus(); $('share-link').select(); $('copy-status').textContent = 'Select and copy the link above'; } };
    for (const v of views) {
      let down; const ray = new T.Raycaster();
      v.renderer.domElement.addEventListener('pointerdown', e => down = [e.clientX, e.clientY]);
      v.renderer.domElement.addEventListener('pointerup', e => {
        if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 4) return;
        const r = v.renderer.domElement.getBoundingClientRect(); ray.setFromCamera(new T.Vector2((e.clientX - r.left) / r.width * 2 - 1, -(e.clientY - r.top) / r.height * 2 + 1), v.camera);
        const hit = ray.intersectObjects(v.meshes.filter(m => m.visible)).find(h => v === detail ? rows().some(p => p.part === h.object.userData.orderedId) : h.object.userData.caseFamily);
        if (hit) select(v === detail ? hit.object.userData.orderedId : firstPart(hit.object.userData.caseFamily));
      });
    }
    const fromHash = () => { const query=new URLSearchParams(location.hash.slice(1)); revision=query.get('revision')==='original'?'original':'revised'; select(query.get('part')||data.parts[0].part); };
    // Inspect the actual displayed BufferGeometry along the sheet normal (browser regression evidence).
    window.orderMapProbe = (offset=0) => {
      const p=data.aluminum.find(p=>p.part===selected); if(mode!=='aluminum') return null;
      const axis=p.thickness_axis_in_exported_step, center=new T.Vector3(...p.hole_center_exported_step_mm);
      center.setComponent(p.flat_axes_in_exported_step[0],center.getComponent(p.flat_axes_in_exported_step[0])+offset);
      center.setComponent(axis,center.getComponent(axis)+10);
      const direction=new T.Vector3(); direction.setComponent(axis,-1); detail.group.updateMatrixWorld(true);
      return new T.Raycaster(center,direction).intersectObjects(detail.meshes).length;
    };
    window.addEventListener('hashchange', fromHash); fromHash();
    function draw() { requestAnimationFrame(draw); for (const v of views) { v.controls.update(); v.renderer.render(v.scene, v.camera); const placed=[];for (const marker of v.markers) { if(marker.button.hidden){marker.line.style.visibility='hidden';continue;} const p = marker.point.clone().project(v.camera),x=(p.x+1)*v.host.clientWidth/2,y=(1-p.y)*v.host.clientHeight/2;let bx=Math.max(28,Math.min(v.host.clientWidth-28,x+marker.offset[0])),by=Math.max(22,Math.min(v.host.clientHeight-64,y+marker.offset[1]));for(const prev of placed)if(Math.abs(bx-prev[0])<52&&Math.abs(by-prev[1])<40)by=prev[1]+43;placed.push([bx,by]);marker.button.style.left=bx+'px';marker.button.style.top=by+'px';const visible=!marker.button.hidden&&Math.abs(p.x)<=1&&Math.abs(p.y)<=1&&p.z<=1;marker.button.style.visibility=visible?'visible':'hidden';marker.line.style.visibility=visible?'visible':'hidden';for(const [k,val] of Object.entries({x1:x,y1:y,x2:bx,y2:by}))marker.line.setAttribute(k,val); } } }
    draw(); window.orderMapReady = true;
  } catch (error) { $('error').textContent = 'The interactive view could not start. Please use a WebGL-enabled browser, or open the normal engineering preview (which includes a Canvas fallback). ' + error.message; console.error(error); }
})();
