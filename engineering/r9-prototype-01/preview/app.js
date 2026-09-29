(async () => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  try {
    if (!window.DecompressionStream) throw new Error('gzip展開に対応したブラウザーを使用してください。');
    if (!window.ZUDO_R9_MODEL_GZIP) throw new Error('R9 preview mesh is missing.');
    const bytes = Uint8Array.from(atob(window.ZUDO_R9_MODEL_GZIP), (char) => char.charCodeAt(0));
    const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
    const model = JSON.parse(await new Response(stream).text());
    if (model.revision !== 'R9-PROTOTYPE-01' || model.model !== '7u40' || model.units !== 'mm') {
      throw new Error('R9 preview metadata does not match this page.');
    }
    run(model);
  } catch (error) {
    $('loading').hidden = true;
    $('error').hidden = false;
    $('errorText').textContent = error.message;
    console.error(error);
  }

  function run(model) {
    const T = window.THREE;
    if (!T) throw new Error('内蔵3Dライブラリーを読み込めませんでした。');
    const state = { lift: 0, travel: false, knobs: false, thinGuards: false, transparency: 0, view: 'iso' };
    const palette = {
      aluminum: 0x20252a,
      guard: 0x26333a,
      hardware: 0x88939c,
      pcb: 0x76684c,
      lid: 0x282d32,
      rail: 0x87919a,
      'provisional-envelope': 0xe2a25d,
      band: 0x252a2f,
    };
    const meshes = [];
    const ray = new T.Raycaster();
    const pointer = new T.Vector2();
    let down = null;
    let resizeObserver;
    const viewer = $('mainCanvas');
    const renderer = new T.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.setClearColor(0xe9edf1, 1);
    renderer.outputColorSpace = T.SRGBColorSpace;
    viewer.appendChild(renderer.domElement);

    const scene = new T.Scene();
    const camera = new T.PerspectiveCamera(34, 1, 0.1, 5000);
    camera.up.set(0, 0, 1);
    const controls = new window.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.screenSpacePanning = true;
    controls.minDistance = 90;
    controls.maxDistance = 2400;
    scene.add(new T.HemisphereLight(0xffffff, 0x778798, 2.2));
    const key = new T.DirectionalLight(0xffffff, 2.5);
    key.position.set(150, -270, 370);
    scene.add(key);
    const fill = new T.DirectionalLight(0xe8f1ff, 1.25);
    fill.position.set(-190, 200, 190);
    scene.add(fill);

    const floor = new T.Mesh(new T.PlaneGeometry(1800, 1800),
      new T.MeshStandardMaterial({ color: 0xe0e5e9, roughness: 1 }));
    floor.position.z = -3.8;
    scene.add(floor);
    const grid = new T.GridHelper(900, 45, 0xc1ccd5, 0xd2dbe2);
    grid.rotation.x = Math.PI / 2;
    grid.position.z = -3.65;
    grid.material.transparent = true;
    grid.material.opacity = 0.22;
    scene.add(grid);

    const root = new T.Group();
    const lidRoot = new T.Group();
    const strapRoot = new T.Group();
    const knobRoot = new T.Group();
    root.add(lidRoot, strapRoot, knobRoot);
    scene.add(root);

    const colorFor = (part) => palette[part.category] ?? 0x777777;
    for (const part of model.parts) {
      const geometry = new T.BufferGeometry();
      geometry.setAttribute('position', new T.Float32BufferAttribute(part.positions, 3));
      geometry.setIndex(part.indices);
      geometry.computeVertexNormals();
      const material = new T.MeshStandardMaterial({
        color: colorFor(part),
        roughness: ['aluminum', 'lid', 'rail'].includes(part.category) ? 0.55 : 0.83,
        metalness: ['aluminum', 'lid', 'rail', 'hardware'].includes(part.category) ? 0.35 : 0.02,
        side: T.DoubleSide,
      });
      if (part.category === 'provisional-envelope') {
        material.transparent = true;
        material.opacity = 0.2;
        material.depthWrite = false;
      }
      const mesh = new T.Mesh(geometry, material);
      mesh.userData = {
        partId: part.partId,
        instanceId: part.instanceId,
        name: part.name,
        dimensionsMm: part.dimensionsMm,
        category: part.category,
        variant: part.variant,
        defaultVisible: part.defaultVisible !== false,
        baseColor: colorFor(part),
        baseMaterial: material,
      };
      if (part.category === 'lid') lidRoot.add(mesh);
      else if (part.category === 'provisional-envelope') knobRoot.add(mesh);
      else root.add(mesh);
      meshes.push(mesh);
      if (['aluminum', 'guard', 'lid'].includes(part.category) && part.positions.length < 90000) {
        const edges = new T.LineSegments(new T.EdgesGeometry(geometry, 35),
          new T.LineBasicMaterial({ color: 0x253441, transparent: true, opacity: 0.18 }));
        edges.userData.edge = true;
        mesh.add(edges);
      }
    }

    const bounds = new T.Box3().setFromObject(root);
    const size = bounds.getSize(new T.Vector3());
    const target = new T.Vector3(0, 0, Math.max(55, (bounds.min.z + bounds.max.z) / 2));
    controls.target.copy(target);
    setView('iso', false);

    const selectInfo = (mesh) => {
      const { name, partId, dimensionsMm, instanceId, category } = mesh.userData;
      const dimensions = dimensionsMm.map((value) => `${Number(value).toFixed(1)} mm`).join(' × ');
      $('partInfo').innerHTML = '';
      const title = document.createElement('strong');
      title.textContent = name;
      const id = document.createElement('code');
      id.textContent = partId;
      const detail = document.createElement('span');
      detail.textContent = `${dimensions} · ${instanceId} · ${category} · 未承認`;
      $('partInfo').append(title, id, detail);
      $('selection').textContent = `${name} · ${partId} · ${dimensions}`;
      $('selection').hidden = false;
    };

    renderer.domElement.addEventListener('pointerdown', (event) => {
      down = { x: event.clientX, y: event.clientY };
    });
    renderer.domElement.addEventListener('pointerup', (event) => {
      if (!down || Math.hypot(event.clientX - down.x, event.clientY - down.y) > 5) return;
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.set((event.clientX - rect.left) / rect.width * 2 - 1,
        -((event.clientY - rect.top) / rect.height) * 2 + 1);
      ray.setFromCamera(pointer, camera);
      const hit = ray.intersectObjects(root.children, true).find((entry) =>
        entry.object.userData.partId && isVisible(entry.object));
      if (hit) selectInfo(hit.object);
      else $('selection').hidden = true;
    });

    function isVisible(object) {
      for (let current = object; current; current = current.parent) if (!current.visible) return false;
      return true;
    }

    function disposeGroup(group) {
      for (const child of [...group.children]) {
        group.remove(child);
        child.traverse((item) => {
          if (item.geometry) item.geometry.dispose();
          if (item.material) item.material.dispose();
        });
      }
    }

    function makeBands() {
      disposeGroup(strapRoot);
      const body = meshes.filter((item) => item.userData.category === 'aluminum' &&
        item.userData.partId.startsWith('7U40-R9-AL-'));
      const width = Math.max(...body.map((item) => item.userData.dimensionsMm[0]));
      const depths = body.map((item) => item.userData.dimensionsMm[1]);
      const depth = Math.max(...depths);
      const span = Math.min(width, depth) + 2.4;
      const height = 127;
      const strapWidth = 20;
      const thickness = 1.4;
      const material = new T.MeshStandardMaterial({ color: palette.band, roughness: 0.92, metalness: 0.01 });
      for (const station of [-100.2, 100.2]) {
        const band = new T.Group();
        const bar = (w, d, h, x, y, z) => {
          const mesh = new T.Mesh(new T.BoxGeometry(w, d, h), material.clone());
          mesh.position.set(x, y, z);
          mesh.userData.name = '運搬用外周バンド（模式）';
          band.add(mesh);
        };
        bar(span, strapWidth, thickness, 0, station, height + thickness / 2);
        bar(span, strapWidth, thickness, 0, station, -1.8);
        bar(thickness, strapWidth, height, -span / 2, station, (height - 1.8) / 2);
        bar(thickness, strapWidth, height, span / 2, station, (height - 1.8) / 2);
        strapRoot.add(band);
      }
      strapRoot.visible = state.travel && state.lift === 0;
    }

    function updateStateButtons(active) {
      $$('[data-state]').forEach((button) => {
        const selected = button.dataset.state === active;
        button.classList.toggle('selected', selected);
        button.setAttribute('aria-pressed', String(selected));
      });
    }

    function applyState(label) {
      if (label === 'travel') {
        state.travel = true;
        state.lift = 0;
      } else if (label === 'open') {
        state.travel = false;
        state.lift = Math.max(state.lift, 110);
      } else {
        state.travel = false;
        state.lift = 0;
      }
      lidRoot.position.z = state.lift;
      makeBands();
      $('lift').value = String(state.lift);
      $('liftValue').textContent = `${state.lift} mm`;
      $('statusText').textContent = label === 'travel' ? '運搬 / バンド2本' : label === 'open' ? '開放' : '日常';
      $('motionText').textContent = `蓋 +${state.lift} mm`;
      $('statusDot').style.background = label === 'travel' ? '#b1824d' : label === 'open' ? '#598ca8' : '#77916b';
      $('stateNote').textContent = label === 'travel'
        ? '幅20 mmの外周バンドを2本、表示しています。市販品・保持性能は未確認です。'
        : label === 'open'
          ? '蓋は+Z方向へ移動します。スライダーで0〜150 mmを指定できます。'
          : '載せ蓋です。ケースとの固定ロックはありません。';
      updateStateButtons(label);
    }

    function updateLift(value) {
      state.lift = Math.max(0, Math.min(150, Math.round(value)));
      if (state.lift > 0) state.travel = false;
      lidRoot.position.z = state.lift;
      strapRoot.visible = state.travel && state.lift === 0;
      $('liftValue').textContent = `${state.lift} mm`;
      $('statusText').textContent = state.lift > 0 ? '開放' : state.travel ? '運搬 / バンド2本' : '日常';
      $('motionText').textContent = `蓋 +${state.lift} mm`;
      if (state.lift > 0) updateStateButtons('open');
      else if (state.travel) updateStateButtons('travel');
      else updateStateButtons('daily');
    }

    function applyAppearance() {
      for (const mesh of meshes) {
        const { category, variant, defaultVisible, baseColor, baseMaterial } = mesh.userData;
        mesh.visible = category === 'provisional-envelope' ? true
          : variant === 't1p0' ? state.thinGuards : defaultVisible;
        const isOuter = category === 'aluminum' || category === 'lid';
        const opacity = isOuter ? 1 - state.transparency / 100 : category === 'provisional-envelope' ? 0.2 : 1;
        baseMaterial.color.setHex(baseColor);
        baseMaterial.transparent = opacity < 1 || category === 'provisional-envelope';
        baseMaterial.opacity = opacity;
        baseMaterial.depthWrite = opacity >= 1;
        baseMaterial.needsUpdate = true;
        mesh.children.forEach((edge) => { if (edge.userData.edge) edge.material.opacity = opacity < 1 ? 0.08 : 0.18; });
      }
      knobRoot.visible = state.knobs;
    }

    function setView(view, update = true) {
      state.view = view;
      const span = Math.max(size.x, size.y, size.z, 230);
      const aspect = viewer.clientWidth / Math.max(1, viewer.clientHeight);
      let distance = span / (2 * Math.tan(camera.fov * Math.PI / 360)) * 1.38;
      if (aspect < 1) distance /= Math.max(0.62, aspect);
      const direction = {
        iso: [1, -1.25, 1.05],
        front: [0, -1, 0.22],
        top: [0.001, -0.001, 1],
        bottom: [0.15, -0.2, -1],
      }[view] || [1, -1.25, 1.05];
      const unit = new T.Vector3(...direction).normalize();
      controls.target.copy(target);
      camera.position.copy(target).add(unit.multiplyScalar(distance));
      controls.update();
      $$('[data-view]').forEach((button) => button.classList.toggle('selected', button.dataset.view === view));
      if (update) render();
    }

    function resize() {
      const width = viewer.clientWidth;
      const height = viewer.clientHeight;
      if (!width || !height) return;
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    }

    function render() {
      renderer.render(scene, camera);
      requestAnimationFrame(render);
    }

    function uniqueParts() {
      const selected = new Map();
      for (const mesh of meshes) {
        const record = mesh.userData;
        if (record.category === 'provisional-envelope' || record.variant === 't1p0') continue;
        if (!selected.has(record.partId)) selected.set(record.partId, mesh);
      }
      return [...selected.values()].sort((a, b) => a.userData.partId.localeCompare(b.userData.partId));
    }

    function renderParts() {
      const list = $('partList');
      for (const mesh of uniqueParts()) {
        const button = document.createElement('button');
        const title = document.createElement('strong');
        const id = document.createElement('span');
        title.textContent = mesh.userData.name;
        id.textContent = mesh.userData.partId;
        button.append(title, id);
        button.dataset.partId = mesh.userData.partId;
        button.onclick = () => selectInfo(mesh);
        list.append(button);
      }
    }

    function renderFileTable() {
      const table = $('fileTable').querySelector('tbody');
      for (const part of (window.ZUDO_R9_FILE_TABLE?.parts ?? [])) {
        const row = document.createElement('tr');
        const id = document.createElement('td');
        id.textContent = part.partId;
        const file = document.createElement('td');
        file.innerHTML = part.formats.map((entry) =>
          `${entry.format.toUpperCase()} · <code>${entry.path.split('/').slice(-1)[0]}</code>`).join('<br>');
        const pack = document.createElement('td');
        pack.textContent = part.packageZip ?? '表示用 / ZIP対象外';
        row.append(id, file, pack);
        table.append(row);
      }
    }

    function renderSections() {
      const entries = window.ZUDO_R9_SECTION_DATA?.entries ?? [];
      const imageMap = window.ZUDO_R9_SECTION_DATA?.images ?? {};
      for (const entry of entries) {
        const option = document.createElement('option');
        option.value = entry.paramId;
        option.textContent = `${entry.paramId} · ${entry.status}`;
        $('sectionSelect').append(option);
      }
      const update = () => {
        const entry = entries.find((item) => item.paramId === $('sectionSelect').value);
        if (!entry) return;
        const image = imageMap[entry.image];
        $('sectionImage').src = `data:image/png;base64,${image}`;
        $('sectionImage').alt = `${entry.paramId}: ${entry.sectionKind} section from R9 generated BREP`;
        $('sectionNote').textContent = `旧値: ${String(entry.old)} → 新値: ${String(entry.new)} ${entry.unit}. ${entry.reason}`;
      };
      $('sectionSelect').onchange = update;
      if (entries.length) {
        $('sectionSelect').value = entries[0].paramId;
        update();
      }
    }

    $$('[data-state]').forEach((button) => button.addEventListener('click', () => applyState(button.dataset.state)));
    $$('[data-view]').forEach((button) => button.addEventListener('click', () => setView(button.dataset.view)));
    $('lift').addEventListener('input', (event) => updateLift(Number(event.target.value)));
    $('transparency').addEventListener('input', (event) => {
      state.transparency = Number(event.target.value);
      $('transparencyValue').textContent = `${state.transparency}%`;
      applyAppearance();
    });
    $('showKnobs').addEventListener('change', (event) => {
      state.knobs = event.target.checked;
      applyAppearance();
    });
    $('knobNote').textContent = `ノブ領域はパネル厚 ${model.parameters.lid.module_panel_thickness} mm＋ノブ高さ ${model.parameters.lid.knob_envelope_height} mmの仮定です。全モジュールの適合確認ではありません。`;
    $('showThinGuards').addEventListener('change', (event) => {
      state.thinGuards = event.target.checked;
      applyAppearance();
    });
    $('resetAll').addEventListener('click', () => {
      state.knobs = false;
      state.thinGuards = false;
      state.transparency = 0;
      $('showKnobs').checked = false;
      $('showThinGuards').checked = false;
      $('transparency').value = '0';
      $('transparencyValue').textContent = '0%';
      applyAppearance();
      applyState('daily');
      setView('iso');
      $('partInfo').innerHTML = '<strong>部品をクリックしてください</strong>';
      $('selection').hidden = true;
    });

    renderParts();
    renderFileTable();
    renderSections();
    makeBands();
    applyAppearance();
    resize();
    resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(viewer);
    $('loading').hidden = true;
    render();

    window.ZUDO_R9_PREVIEW = {
      revision: model.revision,
      model,
      setState: applyState,
      setLift: updateLift,
      visiblePartCount(partId) {
        return meshes.filter((mesh) => mesh.userData.partId === partId && isVisible(mesh)).length;
      },
      selectPart(partId) {
        const mesh = uniqueParts().find((item) => item.userData.partId === partId);
        if (mesh) selectInfo(mesh);
      },
      dispose() {
        resizeObserver?.disconnect();
        renderer.dispose();
      },
    };
  }
})();
