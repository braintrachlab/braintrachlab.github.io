// BrainTraCh Lab — interactive 3D atlas of white matter tracts
// Streamlines are drawn as hairlines with "illuminated line" shading (tube look),
// they grow in when the figure appears, the brain can be rotated/zoomed, and a click
// on a tract highlights it and opens its card (content/tracts.txt).
(function () {
  const box = document.getElementById("atlas-view");
  if (!box) return;
  const C = window.TrachContent;

  // colour of each tract: [dark, light] (rgb 0-1), same palette as the other figures
  const PAL = {
    cc:   [[128, 40, 38], [214, 112, 100]],   // commissural — brick red
    atr:  [[26, 44, 78], [128, 156, 198]],    // projection — ink blue
    fat:  [[40, 92, 58], [132, 182, 122]],    // association — sage
    ifof: [[30, 98, 72], [124, 190, 150]],    // association — sea green
    uf:   [[82, 98, 36], [176, 190, 106]],    // association — olive green
  };
  const rgb = (c) => c.map((v) => v / 255);

  function loadThree() {
    if (window.THREE) return Promise.resolve(window.THREE);
    return new Promise((res, rej) => {
      const s = document.createElement("script");
      s.src = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js";
      s.onload = () => res(window.THREE); s.onerror = rej; document.head.appendChild(s);
    });
  }

  Promise.all([
    loadThree(),
    fetch(box.dataset.meta).then((r) => r.json()),
    fetch(box.dataset.bin).then((r) => r.arrayBuffer()),
    C.load("content/tracts.txt"),
  ]).then(([THREE, meta, buf, cards]) => {
    const nl = meta.tracts.reduce((a, t) => a + t.lines, 0);
    const counts = new Uint16Array(buf, 0, nl);
    const q = new Int16Array(buf, nl * 2 + (nl * 2) % 2);
    const sc = meta.scale;
    const tracts = meta.tracts.map((t, i) => ({ ...t, index: i }));
    const byId = Object.fromEntries(tracts.map((t) => [t.id, t]));
    const cardOf = Object.fromEntries(cards.filter((c) => c.id).map((c) => [c.id, c]));

    // ---------- geometry: each streamline is a thin shaded tube ----------
    // Every segment is a camera-facing ribbon; the fragment shader shades it as a cylinder
    // (rounded light, specular highlight, darker rims), so each fibre reads as a 3D tube.
    const group = new THREE.Group();
    const mats = {};
    const pickPts = {};            // a sample of points per tract, for clicking
    let off = 0, li = 0;
    const WIDTH = 0.42;            // tube radius in mm
    const vert = `
      attribute vec3 tangent; attribute float side; attribute float t; attribute float shade;
      uniform float uWidth;
      varying vec3 vT; varying vec3 vB; varying float vSide; varying float vt; varying float vShade;
      void main() {
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        vec3 T = normalize(mat3(modelViewMatrix) * tangent);
        vec3 V = normalize(-mv.xyz);
        vec3 B = cross(T, V);
        float bl = length(B);
        B = bl > 1e-4 ? B / bl : vec3(1.0, 0.0, 0.0);
        mv.xyz += B * side * uWidth;
        vT = T; vB = B; vSide = side; vt = t; vShade = shade;
        gl_Position = projectionMatrix * mv;
      }`;
    const frag = `
      uniform vec3 cDark; uniform vec3 cLight; uniform float uProg; uniform float uAlpha; uniform float uFade;
      varying vec3 vT; varying vec3 vB; varying float vSide; varying float vt; varying float vShade;
      void main() {
        if (vt > uProg) discard;
        float a = clamp(vSide, -1.0, 1.0);
        float nz = sqrt(max(0.0, 1.0 - a * a));
        vec3 F = normalize(cross(vB, vT));            // across the tube, facing the viewer
        if (F.z < 0.0) F = -F;
        vec3 N = normalize(vB * a + F * nz);
        vec3 L = normalize(vec3(-0.45, 0.55, 0.75));
        float diff = max(dot(N, L), 0.0);
        float spec = pow(max(dot(reflect(-L, N), vec3(0.0, 0.0, 1.0)), 0.0), 26.0);
        float k = clamp(0.12 + 0.88 * diff, 0.0, 1.0) * (0.85 + 0.15 * vShade);
        vec3 col = mix(cDark, cLight, k) + vec3(0.32) * spec;
        col *= 0.62 + 0.38 * nz;                        // darker rims: the tube outline
        col = mix(col, vec3(0.86, 0.87, 0.88), uFade * 0.92);      // non-selected tracts: pale grey ghost
        float front = smoothstep(uProg - 0.03, uProg, vt);
        gl_FragColor = vec4(col, uAlpha * (1.0 - 0.6 * front));
      }`;
    // growth direction of each tract (x = left→right, y = back→front, z = bottom→top)
    const GROW = {
      cc: [1, 0, 0.2],          // from the left to the right hemisphere
      atr: [0.2, 1, 0.1],       // from the thalamus to the frontal lobe
      fat: [-0.7, -0.3, 0.65],  // from the inferior frontal gyrus up to SMA / pre-SMA
      ifof: [0, 1, 0.2],        // from the occipital to the frontal lobe
      uf: [-0.5, 0.7, 0.5],     // from the temporal pole to the orbitofrontal cortex
    };
    const meshes = {};
    for (const t of tracts) {
      let nseg = 0;
      for (let n = 0; n < t.lines; n++) nseg += counts[li + n] - 1;
      const pos = new Float32Array(nseg * 4 * 3), tan = new Float32Array(nseg * 4 * 3);
      const side = new Float32Array(nseg * 4), tt = new Float32Array(nseg * 4), sh = new Float32Array(nseg * 4);
      const idx = new Uint32Array(nseg * 6);
      const pick = [];
      let v = 0, e = 0;
      for (let n = 0; n < t.lines; n++, li++) {
        const c = counts[li];
        const P = (k) => [q[(off + k) * 3] * sc, q[(off + k) * 3 + 1] * sc, q[(off + k) * 3 + 2] * sc];
        const s = Math.random();
        // grow from one extremity to the other, every streamline of a tract in the same direction
        const h = GROW[t.id] || [0, 1, 0], p0 = P(0), p1 = P(c - 1);
        const flip = (p1[0] - p0[0]) * h[0] + (p1[1] - p0[1]) * h[1] + (p1[2] - p0[2]) * h[2] < 0;
        const U = (k) => (flip ? 1 - k / (c - 1) : k / (c - 1));
        for (let k = 0; k < c - 1; k++) {
          const a = P(k), b = P(k + 1);
          const ka = Math.max(0, k - 1), kb = Math.min(c - 1, k + 2);
          const pa = P(ka), pb = P(kb);                       // smooth tangents at the joints
          const ta = [b[0] - pa[0], b[1] - pa[1], b[2] - pa[2]], tb = [pb[0] - a[0], pb[1] - a[1], pb[2] - a[2]];
          const u0 = U(k), u1 = U(k + 1);
          const g0 = u0 * 0.85 + s * 0.15, g1 = u1 * 0.85 + s * 0.15;
          const quad = [[a, ta, -1, g0], [a, ta, 1, g0], [b, tb, -1, g1], [b, tb, 1, g1]];
          for (const [p, d, sd, g] of quad) {
            pos.set(p, v * 3); tan.set(d, v * 3); side[v] = sd; tt[v] = g; sh[v] = s; v++;
          }
          const o = v - 4;
          idx.set([o, o + 1, o + 2, o + 1, o + 3, o + 2], e); e += 6;
          if (k % 6 === 0 && n % 2 === 0) pick.push(a);
        }
        off += c;
      }
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
      g.setAttribute("tangent", new THREE.BufferAttribute(tan, 3));
      g.setAttribute("side", new THREE.BufferAttribute(side, 1));
      g.setAttribute("t", new THREE.BufferAttribute(tt, 1));
      g.setAttribute("shade", new THREE.BufferAttribute(sh, 1));
      g.setIndex(new THREE.BufferAttribute(idx, 1));
      const pal = PAL[t.id] || [[90, 96, 110], [180, 186, 196]];
      const m = new THREE.ShaderMaterial({
        vertexShader: vert, fragmentShader: frag, transparent: true, depthWrite: true, side: THREE.DoubleSide,
        uniforms: { cDark: { value: new THREE.Color(...rgb(pal[0])) }, cLight: { value: new THREE.Color(...rgb(pal[1])) },
                    uProg: { value: 0 }, uAlpha: { value: 1.0 }, uFade: { value: 0 }, uWidth: { value: WIDTH } },
      });
      mats[t.id] = m;
      pickPts[t.id] = pick;
      const mesh = new THREE.Mesh(g, m); mesh.renderOrder = 1; mesh.frustumCulled = false; meshes[t.id] = mesh;
      group.add(mesh);
    }

    // ---------- scene ----------
    const scene = new THREE.Scene();
    // start from a lateral view of the right hemisphere (RAS coordinates: x right, y anterior, z up)
    group.rotation.set(-Math.PI / 2, 0, -Math.PI / 2);
    const pivot = new THREE.Group(); pivot.add(group); scene.add(pivot);
    const R = meta.radius;
    const cam = new THREE.PerspectiveCamera(28, 1, 1, R * 20);
    let dist = R * 3.6;
    cam.position.set(0, 0, dist);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    box.appendChild(renderer.domElement);
    const fit = () => {
      const r = box.getBoundingClientRect();
      renderer.setSize(r.width, r.height, false); cam.aspect = r.width / r.height; cam.updateProjectionMatrix();
    };
    fit(); new ResizeObserver(fit).observe(box);

    // ---------- interaction: rotate, zoom, auto-turn ----------
    const el = renderer.domElement;
    let drag = null, moved = 0, auto = true, lastInteract = 0;
    const pointers = new Map(); let pinch0 = 0;
    el.addEventListener("pointerdown", (e) => {
      el.setPointerCapture(e.pointerId); pointers.set(e.pointerId, [e.clientX, e.clientY]);
      drag = [e.clientX, e.clientY]; moved = 0; auto = false; lastInteract = performance.now();
      if (pointers.size === 2) { const [a, b] = [...pointers.values()]; pinch0 = Math.hypot(a[0] - b[0], a[1] - b[1]); }
    });
    el.addEventListener("pointermove", (e) => {
      if (!pointers.has(e.pointerId)) return;
      pointers.set(e.pointerId, [e.clientX, e.clientY]);
      if (pointers.size === 2) {
        const [a, b] = [...pointers.values()]; const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
        if (pinch0) { dist = Math.min(R * 7, Math.max(R * 1.6, dist * pinch0 / d)); pinch0 = d; }
        moved += 10; return;
      }
      if (!drag) return;
      const dx = e.clientX - drag[0], dy = e.clientY - drag[1]; drag = [e.clientX, e.clientY]; moved += Math.abs(dx) + Math.abs(dy);
      pivot.rotation.y += dx * 0.008;
      pivot.rotation.x = Math.max(-1.4, Math.min(1.4, pivot.rotation.x + dy * 0.008));
      lastInteract = performance.now();
    });
    const up = (e) => {
      pointers.delete(e.pointerId);
      if (pointers.size < 2) pinch0 = 0;
      if (drag && moved < 6) pick(e.clientX, e.clientY);
      if (pointers.size === 0) drag = null;
    };
    el.addEventListener("pointerup", up); el.addEventListener("pointercancel", up);
    el.addEventListener("wheel", (e) => {
      e.preventDefault(); dist = Math.min(R * 7, Math.max(R * 1.6, dist * (1 + Math.sign(e.deltaY) * 0.08))); lastInteract = performance.now();
    }, { passive: false });

    // ---------- picking: nearest tract on screen ----------
    const v = new THREE.Vector3();
    function pick(cx, cy) {
      const r = el.getBoundingClientRect();
      const x = cx - r.left, y = cy - r.top;
      let best = null, bd = 14;
      group.updateMatrixWorld();
      for (const t of tracts) {
        if (selected && t.id !== selected && mats[t.id].uniforms.uAlpha.value < 0.2) {
          // faded tracts stay clickable, but with a smaller radius
        }
        for (const p of pickPts[t.id]) {
          v.set(p[0], p[1], p[2]).applyMatrix4(group.matrixWorld).project(cam);
          const sx = (v.x + 1) / 2 * r.width, sy = (1 - v.y) / 2 * r.height;
          const d = Math.hypot(sx - x, sy - y);
          if (d < bd) { bd = d; best = t.id; }
        }
      }
      select(best);
    }

    // ---------- selection, card ----------
    let selected = null;
    const panel = document.getElementById("tract-panel");
    const body = panel.querySelector(".tract-body");
    const list = document.getElementById("tract-list");
    const target = {};
    tracts.forEach((t) => (target[t.id] = 1.0));
    function select(id) {
      selected = id && id !== selected ? id : (id === selected ? null : null);
      tracts.forEach((t) => (target[t.id] = !selected || t.id === selected ? 1.0 : 0.12));
      // the faded tracts are drawn first, without writing depth, and the selected one last, on top of them
      tracts.forEach((t) => {
        mats[t.id].depthWrite = !selected || t.id === selected;
        meshes[t.id].renderOrder = selected && t.id === selected ? 2 : 1;
      });
      if (selected) {                     // keep the whole view visible below the sticky header
        const r = box.getBoundingClientRect(); const hdr = 90;
        if (r.top < hdr) window.scrollBy({ top: r.top - hdr, behavior: "smooth" });
      }
      list.querySelectorAll("button").forEach((b) => b.classList.toggle("active", b.dataset.id === selected));
      if (!selected) { panel.classList.remove("open"); return; }
      const c = cardOf[selected] || { name: selected };
      const sec = (k, title) => c[k] ? `<h4>${title}</h4><p>${C.md(c[k])}</p>` : "";
      const pal = PAL[selected] || [[90, 96, 110]];
      body.innerHTML = `
        <span class="tract-swatch" style="background:rgb(${pal[0].join(",")})"></span>
        <span class="eyebrow">${C.esc(c.system || "")}</span>
        <h3>${C.md(c.name || selected)}</h3>
        ${c.text ? `<p class="tract-lead">${C.md(c.text)}</p>` : ""}
        ${sec("history", "History")}${sec("anatomy", "Anatomy")}${sec("function", "Function")}${sec("clinical", "Clinical relevance")}
        ${c.links ? `<h4>Further reading</h4><p class="tract-links">${C.md(c.links)}</p>` : ""}`;
      panel.classList.add("open"); panel.scrollTop = 0;
    }
    panel.querySelector(".close").addEventListener("click", () => select(null));
    list.innerHTML = tracts.map((t) => {
      const c = cardOf[t.id] || {}; const pal = PAL[t.id] || [[90, 96, 110]];
      return `<button data-id="${t.id}"><span class="dot" style="background:rgb(${pal[0].join(",")})"></span>${C.esc(c.short || c.name || t.id)}</button>`;
    }).join("");
    list.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => select(b.dataset.id === selected ? null : b.dataset.id)));
    box.querySelector(".atlas-reset").addEventListener("click", () => { select(null); pivot.rotation.set(0, 0, 0); dist = R * 3.6; auto = true; });

    // ---------- animation ----------
    const speed = 0.75;
    let t0 = null, started = false, prev = null;
    const io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) { started = true; io.disconnect(); } }, { threshold: 0.2 });
    io.observe(box);
    const ORDER = { cc: 0, atr: 0.5, fat: 0.9, ifof: 1.1, uf: 1.3 };
    function frame(now) {
      requestAnimationFrame(frame);
      if (!started) return;
      if (t0 === null) t0 = now;
      const dt = Math.min(0.25, prev === null ? 0.016 : (now - prev) / 1000); prev = now;
      const k = 1 - Math.exp(-dt * 7);                 // time-based easing (same on slow and fast devices)
      const s = (now - t0) / 1000 / speed;
      for (const t of tracts) {
        const m = mats[t.id].uniforms;
        m.uProg.value = Math.min(1.05, Math.max(0, (s - (ORDER[t.id] || 0)) / 2.6));
        m.uAlpha.value += (target[t.id] - m.uAlpha.value) * k;
        const fadeTo = selected && t.id !== selected ? 1 : 0;
        m.uFade.value += (fadeTo - m.uFade.value) * 0.12;
      }
      if (auto && now - lastInteract > 4000) pivot.rotation.y += 0.15 * dt;
      // when the card is open, slide the brain into the free part of the view
      const shiftTo = selected && box.clientWidth > 700 ? -R * 0.55 * (dist / (R * 3.6)) : 0;
      pivot.position.x += (shiftTo - pivot.position.x) * k;
      if (!auto && now - lastInteract > 12000 && !selected) auto = true;
      cam.position.set(0, 0, dist); cam.lookAt(0, 0, 0);
      renderer.render(scene, cam);
    }
    requestAnimationFrame(frame);
  }).catch((e) => { console.error(e); box.insertAdjacentHTML("beforeend", '<p class="muted" style="padding:20px">The 3D atlas could not be loaded in this browser.</p>'); });
})();
