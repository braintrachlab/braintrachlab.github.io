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
    fetch("assets/atlas/drawings/drawings.json").then((r) => (r.ok ? r.json() : null)).catch(() => null),
  ]).then(([THREE, meta, buf, cards, mri]) => {
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
      attribute vec3 tangent; attribute float side; attribute float t; attribute float shade; attribute float u;
      uniform float uWidth; uniform float uInk; uniform float uWave; uniform float uInkW;
      varying vec3 vT; varying vec3 vB; varying float vSide; varying float vt; varying float vShade; varying float vInk; varying float vY;
      void main() {
        vY = position.y;
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        vec3 T = normalize(mat3(modelViewMatrix) * tangent);
        vec3 V = normalize(-mv.xyz);
        vec3 B = cross(T, V);
        float bl = length(B);
        B = bl > 1e-4 ? B / bl : vec3(1.0, 0.0, 0.0);
        // "Dejerine" pen stroke: thin and tapered at both ends; tractography: full tube
        float ink = uInk * smoothstep(uWave - 0.08, uWave, t);
        float taper = 0.3 + 0.7 * pow(max(sin(3.14159 * u), 0.0), 0.6);
        mv.xyz += B * side * mix(uWidth, uInkW * taper, ink);
        vT = T; vB = B; vSide = side; vt = t; vShade = shade; vInk = ink;
        gl_Position = projectionMatrix * mv;
      }`;
    const frag = `
      uniform vec3 cDark; uniform vec3 cLight; uniform float uProg; uniform float uAlpha; uniform float uFade;
      uniform float uSweep; uniform float uSweepOn;
      varying vec3 vT; varying vec3 vB; varying float vSide; varying float vt; varying float vShade; varying float vInk; varying float vY;
      void main() {
        if (vt > uProg) discard;
        // section sweep (front to back): fibres exist only in front of the moving section plane
        if (uSweepOn > 0.5 && vY < uSweep) discard;
        float born = uSweepOn > 0.5 ? smoothstep(0.0, 3.5, vY - uSweep) : 1.0;     // soft edge where the fibres emerge
        float nearPlane = uSweepOn * (1.0 - smoothstep(0.0, 9.0, vY - uSweep));
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
        vec3 inkCol = mix(vec3(0.12, 0.125, 0.095), vec3(0.34, 0.34, 0.27), vShade);  // ink of the old plates
        inkCol *= 1.0 - 0.45 * nearPlane;                                          // fresh ink where the fibres emerge
        col = mix(col, inkCol, vInk);
        col = mix(col, vec3(0.86, 0.87, 0.88), uFade * 0.92);      // non-selected tracts: pale grey ghost
        float front = smoothstep(uProg - 0.03, uProg, vt);
        gl_FragColor = vec4(col, born * uAlpha * (1.0 - 0.6 * front) * mix(1.0, min(1.0, 0.62 + 0.38 * nearPlane), vInk));
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
      const side = new Float32Array(nseg * 4), tt = new Float32Array(nseg * 4), sh = new Float32Array(nseg * 4), uu = new Float32Array(nseg * 4);
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
          const quad = [[a, ta, -1, g0, u0], [a, ta, 1, g0, u0], [b, tb, -1, g1, u1], [b, tb, 1, g1, u1]];
          for (const [p, d, sd, g, uv] of quad) {
            pos.set(p, v * 3); tan.set(d, v * 3); side[v] = sd; tt[v] = g; sh[v] = s; uu[v] = uv; v++;
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
      g.setAttribute("u", new THREE.BufferAttribute(uu, 1));
      g.setIndex(new THREE.BufferAttribute(idx, 1));
      const pal = PAL[t.id] || [[90, 96, 110], [180, 186, 196]];
      const m = new THREE.ShaderMaterial({
        vertexShader: vert, fragmentShader: frag, transparent: true, depthWrite: true, side: THREE.DoubleSide,
        uniforms: { cDark: { value: new THREE.Color(...rgb(pal[0])) }, cLight: { value: new THREE.Color(...rgb(pal[1])) },
                    uProg: { value: 0 }, uAlpha: { value: 1.0 }, uFade: { value: 0 }, uWidth: { value: WIDTH },
                    uInk: { value: 1 }, uWave: { value: -0.2 }, uInkW: { value: 0.13 }, uSweep: { value: 999 }, uSweepOn: { value: 0 } },
      });
      mats[t.id] = m;
      pickPts[t.id] = pick;
      const mesh = new THREE.Mesh(g, m); mesh.renderOrder = 1; mesh.frustumCulled = false; meshes[t.id] = mesh;
      group.add(mesh);
    }


    // ---------- Dejerine's section planes (fig. 278): lines I-XII, from front to back ----------
    // positions measured on the plate, as fractions of the hemisphere length from the frontal pole
    const SECT = [0.195, 0.23, 0.36, 0.385, 0.40, 0.447, 0.478, 0.50, 0.54, 0.625, 0.76, 0.845];
    const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"];
    const ext = { y0: Infinity, y1: -Infinity, z0: Infinity, z1: -Infinity };
    for (let i = 0; i < q.length; i += 3) {
      const y = q[i + 1] * sc, z = q[i + 2] * sc;
      if (y < ext.y0) ext.y0 = y; if (y > ext.y1) ext.y1 = y; if (z < ext.z0) ext.z0 = z; if (z > ext.z1) ext.z1 = z;
    }
    const front = ext.y1 + 8, back = ext.y0 - 8;                  // the cortex lies a little beyond the fibres
    const secY = SECT.map((f) => front - f * (front - back));
    const lineTop = ext.z1 + 6, lineBot = ext.z0 - 3;
    const lp = [], lu = [], lid = [];
    secY.forEach((y, i) => {
      const n = 60;
      for (let k = 0; k < n; k++) {
        for (const kk of [k, k + 1]) { lp.push(0, y, lineTop - (lineTop - lineBot) * kk / n); lu.push(kk / n); lid.push(i); }
      }
    });
    const lg = new THREE.BufferGeometry();
    lg.setAttribute("position", new THREE.Float32BufferAttribute(lp, 3));
    lg.setAttribute("u", new THREE.Float32BufferAttribute(lu, 1));
    lg.setAttribute("lid", new THREE.Float32BufferAttribute(lid, 1));
    const lineMat = new THREE.ShaderMaterial({
      transparent: true, depthTest: false, depthWrite: false,
      uniforms: { uDraw: { value: 0 }, uLineA: { value: 0 }, uActive: { value: -1 } },
      vertexShader: `attribute float u; attribute float lid; varying float vu; varying float vid;
        void main() { vu = u; vid = lid; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: `uniform float uDraw; uniform float uLineA; uniform float uActive; varying float vu; varying float vid;
        void main() {
          float shown = clamp((uDraw - vid * 0.11) / 0.45, 0.0, 1.0);
          if (vu > shown) discard;
          if (vid > 8.5 && fract(vu * 34.0) > 0.62) discard;                 // the posterior lines are dashed, as on the plate
          float act = 1.0 - smoothstep(0.0, 0.6, abs(vid - uActive));
          gl_FragColor = vec4(mix(vec3(0.36, 0.30, 0.24), vec3(0.12, 0.09, 0.07), act), uLineA * (0.55 + 0.45 * act));
        }`,
    });
    const secLines = new THREE.LineSegments(lg, lineMat); secLines.renderOrder = 5; secLines.frustumCulled = false;
    group.add(secLines);
    const numerals = document.createElement("div"); numerals.className = "atlas-numerals";
    numerals.innerHTML = ROMAN.map((r) => `<span>${r}</span>`).join("");
    box.appendChild(numerals);
    const numEls = [...numerals.children];
    const inset = document.createElement("figure"); inset.className = "atlas-coupe";
    inset.innerHTML = '<div class="sec-imgs"></div><figcaption></figcaption>';
    box.appendChild(inset);
    const secImgs = SECT.map((_, i) => {
      const im = new Image(); im.alt = ""; im.src = `assets/atlas/sections/coupe-${String(i + 1).padStart(2, "0")}.webp`;
      inset.firstChild.appendChild(im); return im;
    });
    let shownSec = -1;
    function showSection(i) {
      if (i === shownSec) return; shownSec = i;
      secImgs.forEach((im, k) => im.classList.toggle("on", k === i));
      inset.querySelector("figcaption").innerHTML = i >= 0 ? `Dejerine, coupe <em>${ROMAN[i]}</em>` : "";
      lineMat.uniforms.uActive.value = i;
    }


    // ---------- MRI sections drawn like Dejerine's plates (intro "mri") ----------
    // Coronal slices of the T1 (front to back), drawn offline in the style of the Weigert-stained
    // plates of Dejerine (tools/sections/dejerine_render.py -> assets/atlas/drawings). The plane moves
    // through the brain and cross-fades between consecutive drawings.
    let mriPlane = null, mriMat = null, mriY0 = 0, mriTex = [], mriLoaded = Promise.resolve();
    if (mri) {
      const loader = new THREE.TextureLoader();
      mriLoaded = Promise.all(mri.files.map((f, i) => new Promise((res) => {
        mriTex[i] = loader.load("assets/atlas/drawings/" + f, res, undefined, res);
        mriTex[i].minFilter = THREE.LinearFilter; mriTex[i].generateMipmaps = false;
      })));
      const px = mri.px_mm, cx = mri.brain.center_px[0], rTop = mri.brain.top_row, zTop = ext.z1 + 5;
      mriY0 = (mri.n - 1) / 2 * mri.slice_mm;                    // first drawing (frontal pole) lies here
      const xa = (cx - mri.w) * px, xb = cx * px, za = zTop - (mri.h - rTop) * px, zb = zTop + rTop * px;
      const pg = new THREE.BufferGeometry();
      pg.setAttribute("position", new THREE.Float32BufferAttribute([xa, 0, za, xb, 0, za, xb, 0, zb, xa, 0, zb], 3));
      pg.setAttribute("uv", new THREE.Float32BufferAttribute([1, 0, 0, 0, 0, 1, 1, 1], 2));
      pg.setIndex([0, 1, 2, 0, 2, 3]);
      mriMat = new THREE.ShaderMaterial({
        transparent: true, depthWrite: false, side: THREE.DoubleSide,
        uniforms: { uA: { value: null }, uB: { value: null }, uMix: { value: 0 }, uOpacity: { value: 0 } },
        vertexShader: `varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
        fragmentShader: `uniform sampler2D uA; uniform sampler2D uB; uniform float uMix; uniform float uOpacity; varying vec2 vUv;
          void main() {
            float ink = mix(texture2D(uA, vUv).r, texture2D(uB, vUv).r, uMix);
            if (ink < 0.01) discard;
            gl_FragColor = vec4(vec3(0.12, 0.125, 0.095), ink * uOpacity);       // ink of the plates
          }`,
      });
      mriPlane = new THREE.Mesh(pg, mriMat); mriPlane.renderOrder = 4; mriPlane.frustumCulled = false; mriPlane.visible = false;
      group.add(mriPlane);
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
    // Intro: the fibres are first drawn as pen strokes on paper, like the plates of Dejerine,
    // then they turn into tractography streamlines. Style: "atlas.opening" in content/texts.txt
    //   a = the drawing dissolves into the streamlines     b = a wave re-traces every fibre
    //   c = the brain starts to turn while the 3D emerges
    //   d = Dejerine's section planes (fig. 278): the fibres emerge from the sections, front to back
    //   none = no drawing
    const speed = 0.75;
    let intro = "mri";
    fetch("content/texts.txt", { cache: "no-cache" }).then((r) => r.text()).then((t) => {
      const m = t.match(/^\s*atlas\.opening\s*:\s*([a-z]+)/m); if (m) intro = m[1];
    }).catch(() => {}).then(() => Promise.race([mriLoaded, new Promise((r) => setTimeout(r, 9000))])).finally(() => {
      const q = new URLSearchParams(location.search).get("intro"); if (q) intro = q;
      if (intro === "mri" && !mriPlane) intro = "a";
      if (intro === "mri") { pivot.rotation.set(0, Math.PI / 2, 0); dist = R * 3.3; mriPlane.visible = true; }
      if (intro === "d") { pivot.rotation.y = Math.PI; for (const t of tracts) mats[t.id].uniforms.uSweepOn.value = 1; }
      if (!["a", "b", "c", "d", "mri"].includes(intro)) { intro = "none"; setInk(0, 2); box.style.setProperty("--paper", 0); }
      introReady = true;
    });
    let introReady = false;
    function setInk(ink, wave) { for (const t of tracts) { mats[t.id].uniforms.uInk.value = ink; mats[t.id].uniforms.uWave.value = wave; } }
    const ease = (x) => (x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x));
    let t0 = null, started = false, prev = null, skip = false;
    const io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) { started = true; io.disconnect(); } }, { threshold: 0.2 });
    io.observe(box);
    el.addEventListener("pointerdown", () => { skip = true; });      // any interaction ends the intro
    const ORDER = { cc: 0, atr: 0.5, fat: 0.9, ifof: 1.1, uf: 1.3 };
    const DRAWN = (1.3 + 2.6 * 1.05) * speed + 0.5;                 // seconds until the drawing is complete
    let introDone = false, inkNow = 1;
    box.style.setProperty("--paper", 1);


    // ----- intro "mri": 1) the drawn coronal sections scroll from front to back, face on, like turning
    // the plates; 2) the streamlines grow in ink while the brain turns to the lateral view; 3) colour.
    const M_IN = 0.6, M_SWEEP = 7.5, M_OUT = M_IN + M_SWEEP * 0.86, M_GROW = M_OUT + 0.1, MRI_END = M_GROW + 6.2;
    const v0 = { x: 0.0, y: Math.PI / 2 };                              // seen from behind, face on
    const tmpV = new THREE.Vector3();
    function mriIntro(sec) {
      const p = Math.min(1, Math.max(0, (sec - M_IN) / M_SWEEP));
      const slice = p * (mri.n - 1);
      const y = mriY0 - slice * mri.slice_mm;
      mriPlane.position.y = y;
      const k0 = Math.min(mri.n - 1, Math.floor(slice));
      mriMat.uniforms.uA.value = mriTex[k0]; mriMat.uniforms.uB.value = mriTex[Math.min(mri.n - 1, k0 + 1)];
      mriMat.uniforms.uMix.value = slice - k0;
      mriMat.uniforms.uOpacity.value = Math.min(1, sec / M_IN) * (1 - ease((sec - M_OUT) / 0.8));
      // turn from the coronal view to the lateral view while the fibres grow
      const r = ease((sec - M_GROW - 0.4) / 4.2);
      pivot.rotation.x = v0.x * (1 - r); pivot.rotation.y = v0.y * (1 - r);
      // keep the section in the middle of the view (the camera follows the cut), then return to the brain centre
      const follow = 1 - ease((sec - M_OUT) / 2.5);
      tmpV.set(0, y * follow, (ext.z1 + ext.z0) / 2 * 0).applyEuler(group.rotation);
      group.position.set(-tmpV.x, -tmpV.y, -tmpV.z);
      dist = R * (3.3 + 0.3 * r);
      const x = sec - (M_GROW + 3.4);
      const ink = 1 - ease(x / 2.4); setInk(ink, -0.2);
      return ink;
    }
    // ----- intro "d": Dejerine's section planes
    const SWEEP0 = 1.6, SWEEP = 5.8, DISS = SWEEP0 + SWEEP + 0.5;
    function sectionsIntro(sec, dt) {
      lineMat.uniforms.uDraw.value = sec;
      const p = Math.min(1, Math.max(0, (sec - SWEEP0) / SWEEP));
      const sw = front + 2 - p * (front - back + 4);
      for (const t of tracts) mats[t.id].uniforms.uSweep.value = sw;
      let act = -1; secY.forEach((y, i) => { if (sw <= y) act = i; });
      showSection(p > 0 && p < 1 ? act : (p >= 1 ? SECT.length - 1 : -1));
      const x = sec - DISS;
      const fade = 1 - ease(x / 1.1);
      lineMat.uniforms.uLineA.value = Math.min(1, sec * 3) * fade;
      numerals.style.opacity = fade; inset.style.opacity = sec > SWEEP0 - 0.3 ? fade : 0;
      placeNumerals();
      const r = ease((sec - DISS - 0.5) / 3.0);
      pivot.rotation.y = Math.PI * (1 + r);
      if (!skip) dist = R * (4.3 - 0.7 * r);
      if (x > 0) for (const t of tracts) mats[t.id].uniforms.uSweepOn.value = 0;
      const ink = 1 - ease(x / 2.4); setInk(ink, -0.2);
      return ink;
    }
    function endSections() {
      if (mriPlane) { mriPlane.visible = false; group.position.set(0, 0, 0); }
      if (intro !== "d" && intro !== "mri") return;
      for (const t of tracts) mats[t.id].uniforms.uSweepOn.value = 0;
      lineMat.uniforms.uLineA.value = 0; numerals.style.opacity = 0; inset.style.opacity = 0;
    }
    const pv = new THREE.Vector3();
    function placeNumerals() {
      group.updateMatrixWorld();
      const r = box.getBoundingClientRect();
      numEls.forEach((elN, i) => {
        pv.set(0, secY[i], lineTop).applyMatrix4(group.matrixWorld).project(cam);
        elN.style.transform = `translate(${((pv.x + 1) / 2 * r.width).toFixed(1)}px, ${((1 - pv.y) / 2 * r.height).toFixed(1)}px) translate(-50%, ${i % 2 && i < 9 ? -10 : -125}%)`;      // staggered like on the plate
        const shown = Math.min(1, Math.max(0, (lineMat.uniforms.uDraw.value - i * 0.11) / 0.3));
        elN.style.opacity = shown;
      });
    }
    function frame(now) {
      requestAnimationFrame(frame);
      if (!started || !introReady) { renderer.render(scene, cam); return; }
      if (t0 === null) t0 = now;
      const dt = Math.min(0.25, prev === null ? 0.016 : (now - prev) / 1000); prev = now;
      const k = 1 - Math.exp(-dt * 7);                 // time-based easing (same on slow and fast devices)
      const sec = (now - t0) / 1000, s = sec / speed;
      for (const t of tracts) {
        const m = mats[t.id].uniforms;
        const sg = intro === "mri" ? (sec - M_GROW) / speed * 1.3 : s;
        m.uProg.value = skip || intro === "d" ? 1.05 : Math.min(1.05, Math.max(0, (sg - (ORDER[t.id] || 0)) / 2.6));
        m.uAlpha.value += (target[t.id] - m.uAlpha.value) * k;
        const fadeTo = selected && t.id !== selected ? 1 : 0;
        m.uFade.value += (fadeTo - m.uFade.value) * 0.12;
      }
      // ----- intro: drawing -> streamlines
      if (!introDone) {
        const x = sec - DRAWN;                         // time since the drawing was completed
        if (skip) { inkNow = Math.max(0, inkNow - dt * 2.5); setInk(inkNow, -0.2); endSections(); }
        else if (intro === "a") { inkNow = 1 - ease(x / 2.2); setInk(inkNow, -0.2); }
        else if (intro === "b") { const w = -0.2 + 1.45 * ease(x / 2.6); inkNow = w > 1.2 ? 0 : 1 - Math.max(0, w) / 1.2; setInk(1, w); }
        else if (intro === "d") inkNow = sectionsIntro(sec, dt);
        else if (intro === "mri") inkNow = mriIntro(sec);
        else if (intro === "c") { inkNow = 1 - ease((x - 0.3) / 3.4); setInk(inkNow, -0.2); if (x > 0) pivot.rotation.y += 0.32 * dt * ease(x / 1.5); }
        else inkNow = 0;
        box.style.setProperty("--paper", Math.min(1, inkNow * 1.4).toFixed(3));
        if (inkNow <= 0 && intro === "d" && !skip && sec < 11.6) inkNow = 0.0001;
        if (inkNow <= 0 && intro === "mri" && !skip && sec < MRI_END) inkNow = 0.0001;   // wait for the turn to the lateral view
        if (inkNow <= 0) { introDone = true; endSections(); setInk(0, 2); lastInteract = skip ? lastInteract : now - 4000; }
      }
      if (introDone && auto && now - lastInteract > 4000) pivot.rotation.y += 0.15 * dt;
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
