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
    fetch("assets/atlas/planes/sections.json").then((r) => (r.ok ? r.json() : null)).catch(() => null),
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
      varying vec3 vT; varying vec3 vB; varying float vSide; varying float vt; varying float vShade; varying float vInk; varying vec3 vP;
      void main() {
        vP = position;
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
      uniform float uSweep; uniform float uSweepOn; uniform vec3 uN; uniform float uSide; uniform float uKl; uniform vec3 uKlTint;
      varying vec3 vT; varying vec3 vB; varying float vSide; varying float vt; varying float vShade; varying float vInk; varying vec3 vP;
      void main() {
        if (vt > uProg) discard;
        // section sweep (front to back): fibres exist only in front of the moving section plane
        float dP = dot(vP, uN) - uSweep;
        float intro = step(0.5, uSweepOn) * (1.0 - step(1.5, uSweepOn));
        if (intro > 0.5 && dP < 0.0) discard;
        if (uSweepOn > 1.5 && dP * uSide > 0.0) discard;                             // slider: only behind the section
        float born = intro > 0.5 ? smoothstep(0.0, 3.5, dP) : 1.0;                  // soft edge where the fibres emerge
        float nearPlane = intro * (1.0 - smoothstep(0.0, 9.0, dP));
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
        // Klingler dissection: ivory, wet-looking fibres, deep grooves between the bundles
        float specK = pow(max(dot(reflect(-L, N), vec3(0.0, 0.0, 1.0)), 0.0), 46.0);
        vec3 colK = mix(vec3(0.46, 0.38, 0.30) * uKlTint, vec3(0.95, 0.92, 0.84) * uKlTint, pow(k, 0.75));
        colK = colK * (0.52 + 0.48 * pow(nz, 0.5)) + vec3(0.62, 0.60, 0.55) * specK;
        colK *= 0.94 + 0.06 * vShade;                                  // each fibre slightly different
        col = mix(col, colK, uKl);
        vec3 inkCol = mix(vec3(0.22), vec3(0.42), vShade);  // ink of the old plates
        inkCol *= 1.0 - 0.45 * nearPlane;                                          // fresh ink where the fibres emerge
        col = mix(col, inkCol, vInk);
        col = mix(col, vec3(0.86, 0.87, 0.88), uFade * 0.92);      // non-selected tracts: pale grey ghost
        float behind = step(1.5, uSweepOn);                          // with a section: the tracts behind it as a pale ghost
        col = mix(col, vec3(0.90, 0.90, 0.89), behind * 0.72);
        float front = smoothstep(uProg - 0.03, uProg, vt);
        gl_FragColor = vec4(col, born * uAlpha * (1.0 - 0.6 * front) * mix(1.0, min(1.0, 0.62 + 0.38 * nearPlane), vInk) * (1.0 - 0.55 * behind));
      }`;
    // growth direction of each tract (x = left→right, y = back→front, z = bottom→top)
    const GROW = {
      cc: [1, 0, 0.2],          // from the left to the right hemisphere
      atr: [0.2, 1, 0.1],       // from the thalamus to the frontal lobe
      fat: [-0.7, -0.3, 0.65],  // from the inferior frontal gyrus up to SMA / pre-SMA
      ifof: [0, 1, 0.2],        // from the occipital to the frontal lobe
      uf: [-0.5, 0.7, 0.5],     // from the temporal pole to the orbitofrontal cortex
    };
    const meshes = {}, segs = {};
    for (const t of tracts) {
      let nseg = 0;
      for (let n = 0; n < t.lines; n++) nseg += counts[li + n] - 1;
      const pos = new Float32Array(nseg * 4 * 3), tan = new Float32Array(nseg * 4 * 3);
      const side = new Float32Array(nseg * 4), tt = new Float32Array(nseg * 4), sh = new Float32Array(nseg * 4), uu = new Float32Array(nseg * 4);
      const idx = new Uint32Array(nseg * 6);
      const pick = [];
      const sa = new Float32Array(nseg * 3), sb = new Float32Array(nseg * 3); let si = 0;
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
          sa.set(a, si * 3); sb.set(b, si * 3); si++;
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
                    uProg: { value: 0 }, uAlpha: { value: 1.0 }, uFade: { value: 0 }, uWidth: { value: WIDTH }, uKl: { value: 0 }, uKlTint: { value: new THREE.Color(1, 1, 1) },
                    uInk: { value: 1 }, uWave: { value: -0.2 }, uInkW: { value: 0.13 }, uSweep: { value: 999 }, uSweepOn: { value: 0 }, uN: { value: new THREE.Vector3(0, 1, 0) }, uSide: { value: 1 } },
      });
      mats[t.id] = m;
      pickPts[t.id] = pick; segs[t.id] = { a: sa, b: sb, n: si };
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


    // ---------- sections of the same brain (coronal, axial, sagittal) ----------
    // Each plane is a series of images (one per 1.25 mm slice) drawn from the T1 and the whole-brain
    // tractogram in the style of Dejerine's Weigert plates (tools/sections/dejerine_render.py), plus the
    // T1 and FA of the same slices. Positions are in the world space of the brain (RAS mm).
    const PL = {};                                     // plane name -> plane.json + image sets
    let plane = "coronal", mode = "dejerine", kNow = 0, secOn = false, mriPlane = null, mriMat = null;
    const secTex = new THREE.Texture(); secTex.minFilter = THREE.LinearFilter; secTex.generateMipmaps = false;
    let mriShown = null;
    // world (RAS mm) -> atlas frame. Tracts dissected in the same space line up exactly; otherwise the
    // brain is placed on the tracts by its bounding box (approximate).
    const T = new THREE.Vector3();
    if (mri) {
      const bb = mri.brain_box;
      if (meta.space && meta.space === mri.space && meta.center_rasmm) T.set(...meta.center_rasmm).multiplyScalar(-1);
      else T.set(0 - (bb[0][0] + bb[1][0]) / 2, (ext.y0 + ext.y1) / 2 - (bb[0][1] + bb[1][1]) / 2, ext.z1 + 5 - bb[1][2]);
    }
    const planeJson = (p) => PL[p] ? Promise.resolve(PL[p]) :
      fetch(`assets/atlas/planes/${p}/plane.json`).then((r) => r.json()).then((j) => (PL[p] = Object.assign(j, { sets: {} })));
    function loadSet(p, md) {
      const P = PL[p];
      if (P.sets[md]) return P.sets[md].ready;
      const dir = `assets/atlas/planes/${p}/` + (P.modes[md] || "");
      const imgs = [];
      const first = Math.max(0, Math.min(P.n - 1, kNow || 0));
      const order = P.pos.map((_, i) => i).sort((a, b) => Math.abs(a - first) - Math.abs(b - first));   // nearest first
      const ready = Promise.all(order.map((i) => new Promise((res) => {
        const im = new Image(); im.onload = im.onerror = res; im.src = dir + "s" + String(i).padStart(3, "0") + ".webp"; imgs[i] = im;
      })));
      P.sets[md] = { imgs, ready };
      return ready;
    }
    const STAIN = { kb: 2, silver: 3 };                // kb: from the T1 of the slice; silver: its own images (after BigBrain)
    const setName = () => (mode === "dejerine" ? (selected ? "base" : "dejerine") : mode === "kb" ? "t1" : mode);   // a selected tract: only its fibres
    function showSlice(k) {                       // one section on screen: swap the image of the single texture
      const P = PL[plane]; if (!P) return;
      k = Math.max(0, Math.min(P.n - 1, Math.round(k))); kNow = k;
      const set = P.sets[setName()] || P.sets.dejerine; if (!set) return;
      const im = set.imgs[k], key = plane + setName() + k;
      if (key === mriShown || !im) return;
      if (!im.complete || !im.naturalWidth) {            // not downloaded yet: ask for it first, show it when it arrives
        if (!im.__urgent) {
          im.__urgent = true;
          const now = new Image(); now.fetchPriority = "high"; now.src = im.src;
          now.onload = () => { set.imgs[k] = now; if (kNow === k) { mriShown = null; showSlice(k); } };
        }
        return;
      }
      mriShown = key; secTex.image = im; secTex.needsUpdate = true;
    }
    const nrm = (p) => new THREE.Vector3(...[0, 1, 2].map((d) => (d === PL[p].axis ? 1 : 0)));
    function buildPlane(p) {                       // the quad of the images of plane p (normal coordinate = 0)
      const P = PL[p], ax = P.axis;
      const O = new THREE.Vector3(...P.O), U = new THREE.Vector3(...P.U), V = new THREE.Vector3(...P.V);
      O.add(T); O.setComponent(ax, 0);
      const c = [O.clone(), O.clone().add(U), O.clone().add(U).add(V), O.clone().add(V)];
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.Float32BufferAttribute(c.flatMap((v) => [v.x, v.y, v.z]), 3));
      g.setAttribute("uv", new THREE.Float32BufferAttribute([0, 1, 1, 1, 1, 0, 0, 0], 2));
      g.setIndex([0, 1, 2, 0, 2, 3]);
      if (mriPlane.geometry) mriPlane.geometry.dispose();
      mriPlane.geometry = g; mriPlane.position.set(0, 0, 0);
      mriMat.uniforms.uRes.value.set(U.length() / 0.11, V.length() / 0.11);
      for (const t of tracts) mats[t.id].uniforms.uN.value.copy(nrm(p));
    }
    const atlasPos = (p, k) => PL[p].pos[k] + T.getComponent(PL[p].axis);
    const mriLoaded = mri ? planeJson("coronal").then(() => loadSet("coronal", "dejerine")) : Promise.resolve();
    if (mri) {
      mriMat = new THREE.ShaderMaterial({
        transparent: true, depthWrite: false, side: THREE.DoubleSide,
        uniforms: { uA: { value: secTex }, uOpacity: { value: 0 }, uMode: { value: 0 }, uRes: { value: new THREE.Vector2(1400, 1400) } },
        vertexShader: `varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
        fragmentShader: `uniform sampler2D uA; uniform float uOpacity; uniform float uMode; uniform vec2 uRes; varying vec2 vUv;
          float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
          // stained cells: small round dots on a fine grid (density d, size r in cells)
          float cells(vec2 p, float d, float r) {
            vec2 g = floor(p), f = fract(p);
            float h = hash(g); if (h > d) return 0.0;
            vec2 c = vec2(hash(g + 7.1), hash(g + 3.7)) * 0.6 + 0.2;
            return 1.0 - smoothstep(r * 0.6, r, length(f - c));
          }
          void main() {
            vec4 tx = texture2D(uA, vUv);
            if (tx.a < 0.05) discard;                                          // no tissue: the background shows
            vec3 paper = vec3(0.975), inkc = vec3(0.235);                       // grey ink of the home-page plate
            vec3 col = uMode < 0.5 ? mix(paper, inkc, tx.r * 0.92) : vec3(tx.r);  // Dejerine drawing, or T1 / FA / T2
            if (uMode > 1.5 && uMode < 2.5) {                                 // Kluver-Barrera: Luxol fast blue + cresyl violet
              vec2 o = vec2(0.0025);
              float v = (tx.r * 2.0 + texture2D(uA, vUv + vec2(o.x, 0.0)).r + texture2D(uA, vUv - vec2(o.x, 0.0)).r
                         + texture2D(uA, vUv + vec2(0.0, o.y)).r + texture2D(uA, vUv - vec2(0.0, o.y)).r) / 6.0;   // T1, smoothed
              float my = smoothstep(0.47, 0.66, v);                             // myelin: white matter
              float gm = smoothstep(0.10, 0.24, v) * (1.0 - my);               // grey matter
              vec2 p = vUv * uRes;                                              // ~0.1 mm cells
              vec3 wmc = mix(vec3(0.55, 0.68, 0.86), vec3(0.13, 0.29, 0.60), my);
              col = mix(vec3(0.88, 0.75, 0.86), wmc, my);
              col = mix(vec3(0.97, 0.95, 0.97), col, clamp(gm + my, 0.0, 1.0));
              float c = cells(p, 0.30 * gm + 0.04 * my, 0.32) * (0.8 + 0.2 * hash(floor(p) + 1.3));
              col = mix(col, vec3(0.38, 0.17, 0.42), c * 0.85);               // neurons and glia, violet
            } else if (uMode > 2.5) {                                           // silver (cell-body) stain: grey matter dark
              float g = 0.94 + 0.06 * hash(floor(vUv * uRes * 2.0));            // fine grain of the section
              col = mix(vec3(0.10, 0.095, 0.09), vec3(0.95, 0.94, 0.92), tx.r) * g;
            }
            gl_FragColor = vec4(col, uOpacity * smoothstep(0.05, 0.6, tx.a));
          }`,
      });
      mriPlane = new THREE.Mesh(new THREE.BufferGeometry(), mriMat); mriPlane.renderOrder = 4; mriPlane.frustumCulled = false; mriPlane.visible = false;
      group.add(mriPlane);
    }
    function placeSection(k) {                    // move the plane to slice k and cut the tracts there
      const P = PL[plane]; if (!P) return;
      const w = atlasPos(plane, Math.max(0, Math.min(P.n - 1, Math.round(k))));
      mriPlane.position.setComponent(P.axis, w);
      showSlice(k);
      for (const t of tracts) mats[t.id].uniforms.uSweep.value = w;
      drawOverlay();
    }

    // ---------- the selected tract on the section: its streamlines within the slice (lines or dots) ----------
    const ovLines = new THREE.LineSegments(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ color: 0x3c3c3c, transparent: true, depthTest: false }));
    const dotMat = new THREE.ShaderMaterial({                   // small round dots, like the stipple of the plates
      transparent: true, depthTest: false, uniforms: { color: { value: new THREE.Color(0x3c3c3c) }, uSize: { value: 1.6 * Math.min(window.devicePixelRatio || 1, 2) } },   // as wide as the lines
      vertexShader: `uniform float uSize; void main() { gl_PointSize = uSize; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: `uniform vec3 color; void main() { vec2 d = gl_PointCoord - 0.5; float r = length(d); if (r > 0.5) discard; gl_FragColor = vec4(color, smoothstep(0.5, 0.3, r)); }`,
    });
    dotMat.color = dotMat.uniforms.color.value;
    const ovDots = new THREE.Points(new THREE.BufferGeometry(), dotMat);
    ovLines.renderOrder = ovDots.renderOrder = 6; ovLines.frustumCulled = ovDots.frustumCulled = false;
    group.add(ovLines); group.add(ovDots);
    let ovSide = 1;
    function drawOverlay() {
      const on = secOn && selected && PL[plane];
      ovLines.visible = ovDots.visible = !!on;
      if (!on) return;
      const P = PL[plane], ax = P.axis, w = atlasPos(plane, kNow), half = 0.65;
      const S = segs[selected], L = [], D = [];
      for (let i = 0; i < S.n; i++) {
        const a0 = S.a[i * 3 + ax], b0 = S.b[i * 3 + ax];
        if (Math.max(a0, b0) < w - half || Math.min(a0, b0) > w + half) continue;
        const d = b0 - a0;
        let t0 = 0, t1 = 1;
        if (Math.abs(d) > 1e-6) { const u = (w - half - a0) / d, v2 = (w + half - a0) / d; t0 = Math.max(0, Math.min(u, v2)); t1 = Math.min(1, Math.max(u, v2)); }
        const pa = [], pb = [];
        for (let c = 0; c < 3; c++) { const A = S.a[i * 3 + c], B = S.b[i * 3 + c]; pa.push(A + (B - A) * t0); pb.push(A + (B - A) * t1); }
        pa[ax] = pb[ax] = 0;
        const len = Math.hypot(pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]);
        if (len < 0.45) D.push((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2, (pa[2] + pb[2]) / 2);   // crossing the section: a dot
        else L.push(...pa, ...pb);                                                              // running in it: a line
      }
      ovLines.geometry.setAttribute("position", new THREE.Float32BufferAttribute(L, 3));
      ovDots.geometry.setAttribute("position", new THREE.Float32BufferAttribute(D, 3));
      const col = mode === "dejerine" ? 0x3c3c3c : mode === "silver" ? new THREE.Color(...rgb((PAL[selected] || [[0, 0, 0], [230, 120, 110]])[1])).getHex() : STAIN[mode] ? new THREE.Color(...rgb((PAL[selected] || [[60, 60, 60]])[0])).getHex() : new THREE.Color(...rgb((PAL[selected] || [[200, 60, 60], [230, 120, 110]])[1])).getHex();
      ovLines.material.color.set(col); ovDots.material.color.set(col);
      ovLines.position.set(0, 0, 0); ovLines.position.setComponent(ax, w + ovSide * 0.4);
      ovDots.position.copy(ovLines.position);
    }

    // ---------- controls under the view: plane, appearance, position ----------
    const sliderBox = document.getElementById("atlas-slider");
    let slider = null, sliderOn = false, viewTo = null;
    const VIEW = { coronal: { x: 0.15, y: Math.PI / 2 - 0.42 }, axial: { x: 1.15, y: 0.35 }, sagittal: { x: 0.15, y: 0.42 } };
    const FROM = { coronal: "from the frontal pole", axial: "from the lowest point", sagittal: "from the right surface" };
    function setSlider(k) { if (slider && !sliderOn) slider.value = Math.round(k) + 1; }
    let openSection = () => {};
    if (mri && sliderBox) {
      sliderBox.hidden = false;
      slider = sliderBox.querySelector("input");
      const out = sliderBox.querySelector("output");
      const selPlane = document.getElementById("atlas-plane"), selMode = document.getElementById("atlas-mode");
      const ends = sliderBox.querySelectorAll(".end");
      const labels = () => { const P = PL[plane]; ends[0].textContent = P.labels[0]; ends[1].textContent = P.labels[1]; slider.max = P.n + 1; };      // 0 and n+1: beyond the brain, no section
      openSection = (turn) => {
        if (!PL[plane]) return;
        if (turn || !sliderOn) { viewTo = Object.assign({}, VIEW[plane]); auto = false; lastInteract = performance.now(); }
        skip = true; sliderOn = true; secOn = true; group.position.set(0, 0, 0);
        if (!introReady) { intro = "none"; introReady = true; }        // using the controls ends the opening at once
        const kk = +slider.value - 1, outside = kk < 0 || kk > PL[plane].n - 1;
        secOn = !outside;                                // at both ends the plane disappears completely
        mriPlane.visible = !outside; mriMat.uniforms.uOpacity.value = 1;
        for (const t of tracts) mats[t.id].uniforms.uSweepOn.value = outside ? 0 : 2;
        if (!outside) placeSection(kk); else drawOverlay();
        out.textContent = outside ? "" : `${Math.round(kk * (PL[plane].step_mm || 1.25))} mm ${PL[plane].from || FROM[plane]}`;
        sliderBox.classList.add("active");
      };
      slider.addEventListener("input", () => openSection(false));
      if (!(mri.planes || []).includes("axial")) selPlane.querySelector('option[value="axial"]').remove();
      if (!(mri.planes || []).includes("sagittal")) selPlane.querySelector('option[value="sagittal"]').remove();
      selPlane.addEventListener("change", () => {
        const keepFrac = +slider.value / Math.max(1, +slider.max);
        plane = selPlane.value;
        planeJson(plane).then(() => {
          buildPlane(plane); labels(); mriShown = null;
          slider.value = Math.round(keepFrac * (PL[plane].n + 1));
          loadSet(plane, setName()).then(() => { mriShown = null; showSlice(+slider.value - 1); });
          openSection(true);
        });
      });
      selMode.addEventListener("change", () => {
        mode = selMode.value; mriMat.uniforms.uMode.value = mode === "dejerine" ? 0 : STAIN[mode] || 1;
        loadSet(plane, setName()).then(() => { mriShown = null; showSlice(+slider.value - 1); });
        openSection(false); drawOverlay();
      });
      sliderBox.querySelector("button").addEventListener("click", () => {
        sliderOn = false; secOn = false; mriPlane.visible = false; viewTo = { x: 0, y: 0 }; sliderBox.classList.remove("active"); out.textContent = "";
        for (const t of tracts) mats[t.id].uniforms.uSweepOn.value = 0;
        drawOverlay();
      });
      planeJson("coronal").then(() => { buildPlane("coronal"); labels(); });
    }
    // ---------- view of the tracts: tractography colours, or a Klingler fibre dissection ----------
    const KL_TINT = { cc: [1.0, 0.975, 0.94], atr: [0.97, 0.975, 1.0], fat: [0.985, 1.0, 0.965], ifof: [0.97, 0.99, 0.97], uf: [1.0, 0.99, 0.95] };
    const styleSel = document.getElementById("atlas-style");
    let klTarget = 0;
    if (styleSel) styleSel.addEventListener("change", () => {
      klTarget = styleSel.value === "klingler" ? 1 : 0;
      box.classList.toggle("klingler", klTarget === 1);
      for (const t of tracts) mats[t.id].uniforms.uKlTint.value.setRGB(...(KL_TINT[t.id] || [1, 1, 1]));
    });
    function stepStyle(k) {
      for (const t of tracts) {
        const u = mats[t.id].uniforms;
        u.uKl.value += (klTarget - u.uKl.value) * k;
        u.uWidth.value = WIDTH * (1 + 0.95 * u.uKl.value);                 // dissected bundles: thicker, packed fibres
      }
    }
    // after a selection: switch the Dejerine images to the version without fibres, and draw the tract
    function sectionSelectionChanged() {
      if (!secOn) return;
      loadSet(plane, setName()).then(() => { mriShown = null; showSlice(kNow); });
      mriShown = null; showSlice(kNow); drawOverlay();
    }
    const camL = new THREE.Vector3();
    function updateSide() {                        // keep the tracts on the far side of the section
      if (!secOn || !PL[plane]) return;
      group.updateMatrixWorld(); camL.copy(cam.position); group.worldToLocal(camL);
      const s = Math.sign(camL.getComponent(PL[plane].axis) - atlasPos(plane, kNow)) || 1;
      for (const t of tracts) mats[t.id].uniforms.uSide.value = s;
      if (s !== ovSide) { ovSide = s; drawOverlay(); }
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
    // the view shrinks to the free space when the card of a tract is open (beside it, or above it on phones)
    let viewW = 0, viewH = 0;
    const freeSize = () => {
      const r = box.getBoundingClientRect(), pnl = document.getElementById("tract-panel");
      const open = pnl && pnl.classList.contains("open");
      if (!open) return [r.width, r.height];
      return r.width > 700 ? [Math.max(200, r.width - pnl.offsetWidth), r.height] : [r.width, Math.max(160, r.height - pnl.offsetHeight)];
    };
    const setView = (w, h) => {
      viewW = w; viewH = h;
      renderer.setSize(w, h, false); el0.style.width = w + "px"; el0.style.height = h + "px";
      cam.aspect = w / h; cam.updateProjectionMatrix();
    };
    const el0 = renderer.domElement;
    const fit = () => { const [w, h] = freeSize(); setView(w, h); };
    fit(); new ResizeObserver(fit).observe(box);

    // ---------- interaction: rotate, zoom, auto-turn ----------
    const el = renderer.domElement;
    let drag = null, moved = 0, auto = true, lastInteract = 0;
    const pointers = new Map(); let pinch0 = 0;
    el.addEventListener("pointerdown", (e) => {
      el.setPointerCapture(e.pointerId); pointers.set(e.pointerId, [e.clientX, e.clientY]);
      drag = [e.clientX, e.clientY]; moved = 0; auto = false; viewTo = null; lastInteract = performance.now();
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
      sectionSelectionChanged();
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
      if (introReady) return;                                           // the visitor already took over
      const q = new URLSearchParams(location.search).get("intro"); if (q) intro = q;
      if (intro === "mri" && (!mriPlane || !PL.coronal)) intro = "a";
      if (intro === "mri") { buildPlane("coronal"); pivot.rotation.set(0, Math.PI / 2, 0); dist = R * 3.3; mriPlane.visible = true; }
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
      const slice = p * (PL.coronal.n - 1);
      const y = atlasPos("coronal", Math.round(slice));
      mriPlane.position.y = y;
      showSlice(slice); setSlider(slice);
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
      if (sliderOn) { lineMat.uniforms.uLineA.value = 0; numerals.style.opacity = 0; inset.style.opacity = 0; setInk(0, 2); return; }
      if (mriPlane && !sliderOn) { mriPlane.visible = false; } group.position.set(0, 0, 0);
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
      if (viewTo) {          // turn so that the section faces the viewer
        pivot.rotation.x += (viewTo.x - pivot.rotation.x) * k; pivot.rotation.y += (viewTo.y - pivot.rotation.y) * k;
        if (Math.abs(viewTo.y - pivot.rotation.y) < 0.002) viewTo = null;
      }
      // when the card is open, slide the brain into the free part of the view
      { const [tw, th] = freeSize();                     // ease the view to the free space
        if (Math.abs(tw - viewW) > 0.5 || Math.abs(th - viewH) > 0.5) setView(viewW + (tw - viewW) * Math.min(1, k * 1.6) + Math.sign(tw - viewW) * 0.5, viewH + (th - viewH) * Math.min(1, k * 1.6) + Math.sign(th - viewH) * 0.5); }
      if (!auto && now - lastInteract > 12000 && !selected && !sliderOn) auto = true;
      cam.position.set(0, 0, dist); cam.lookAt(0, 0, 0);
      stepStyle(k);
      updateSide();
      renderer.render(scene, cam);
    }
    requestAnimationFrame(frame);
  }).catch((e) => { console.error(e); box.insertAdjacentHTML("beforeend", '<p class="muted" style="padding:20px">The 3D atlas could not be loaded in this browser.</p>'); });
})();
