/* Arnold's plates turning into tractography.
   1 the plate; 2 its engraved fibres traced as lines; 3 the lines thicken into tubes; 4 the tubes continue out of the
   plane as real streamlines (those that continue an engraved fibre first, then outwards), while the view turns;
   5 the rest of the brain completes itself.  Data: arnold-{med,ax}.{json,bin}, registered to the plate in plate pixels. */
(function () {
  const sm = (x) => (x <= 0 ? 0 : x >= 1 ? 1 : x * x * (3 - 2 * x));
  const smoother = (x) => (x <= 0 ? 0 : x >= 1 ? 1 : x * x * x * (x * (x * 6 - 15) + 10));
  const ramp = (t, a, b, f = sm) => f((t - a) / (b - a));
  const LVS = `attribute float aT; varying float vT; void main(){ vT = aT; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
  const LFS = `uniform float uDraw; uniform float uAlpha; uniform vec3 uCol; varying float vT;
    void main(){ if (vT > uDraw) discard; gl_FragColor = vec4(uCol, uAlpha); }`;
  const TVS = `attribute vec3 aNext; attribute float aSide; attribute vec3 aC; attribute float aT; attribute float aDel; attribute float aR;
    uniform float uD0; uniform float uD1; uniform float uMorph; uniform vec2 uRes; uniform float uRad; uniform float uMinPx; uniform float uGrow; uniform float uC; uniform float uEdgeC;
    varying vec3 vC; varying float vT; varying float vS; varying float vG; varying float vZ; varying float vK; varying float vR; varying float vD;
    void main(){
      vR = aR; vZ = position.z; vK = 1.0 - smoothstep(-uEdgeC, uEdgeC, position.z - uC); vec3 p = position; p.z *= uMorph; vec3 q = aNext; q.z *= uMorph;
      vec4 mv = modelViewMatrix * vec4(p, 1.0); vD = clamp((-mv.z - uD0) / (uD1 - uD0), 0.0, 1.0);
      vec4 a = projectionMatrix * mv; vec4 b = projectionMatrix * modelViewMatrix * vec4(q, 1.0);
      vec2 sa = a.xy / a.w * uRes * 0.5, sb = b.xy / b.w * uRes * 0.5; vec2 d = sb - sa; float L = length(d);
      vec2 n = L > 1e-4 ? vec2(-d.y, d.x) / L : vec2(0.0, 1.0);
      float px = max(uRad * projectionMatrix[1][1] * uRes.y * 0.5 / a.w, uMinPx);
      a.xy += n * aSide * px / (uRes * 0.5) * a.w;
      vC = aC; vT = aT; vS = aSide; vG = clamp((uGrow - aDel) / 0.5, 0.0, 1.0); gl_Position = a; }`;
  const TFS = `uniform float uAlpha; uniform vec3 uTint; uniform float uTintK; uniform float uA; uniform float uB; uniform float uEdge;
    varying vec3 vC; varying float vT; varying float vS; varying float vG; varying float vZ; varying float vK; varying float vR; varying float vD;
    void main(){ if (vT > vG * 1.02 || vZ < uA || vZ > uB || fract(vR * 7.31) > 0.4 + 1.2 * vK) discard; float n = sqrt(max(0.0, 1.0 - vS * vS));
      // Arnold's engraving: fine sepia strokes, darker at their edges, on the tone of the paper
      // light fibres on the paper; each stroke its own tone, deeper ones darker (the chiaroscuro of the plate)
      // the greys of Arnold's white matter, from the lit bundles to the shaded grooves (sampled from the plate)
      float tone = clamp(0.1 + 0.6 * vR + 0.45 * vD, 0.0, 1.0);
      vec3 g0 = vec3(0.933, 0.914, 0.871), g1 = vec3(0.769, 0.749, 0.71), g2 = vec3(0.498, 0.486, 0.443);
      vec3 eng = (tone < 0.5 ? mix(g0, g1, tone * 2.0) : mix(g1, g2, tone * 2.0 - 1.0)) * (0.8 + 0.2 * n);
      vec3 trc = mix(vC, vec3(0.97), 0.16) * (0.78 + 0.26 * n);
      gl_FragColor = vec4(min(mix(eng, trc, vK), 1.0), uAlpha); }`;
  const INK = [0.43, 0.39, 0.34];   // the graphite-sepia of the lithograph
  function read(buf, set, dim, extra) {
    let o = set.off; const lens = new Uint16Array(buf, o, set.n); o += 2 * set.n;
    const P = new Int16Array(buf, o, dim * set.v); o += 2 * dim * set.v;
    let C = null, D = null;
    if (extra) { C = new Uint8Array(buf, o, 3 * set.v); o += 3 * set.v; D = new Uint8Array(buf, o, set.n); }
    return { lens, P, C, D, dim };
  }
  function lines(THREE, S) {
    let segs = 0; for (const l of S.lens) segs += l - 1;
    const pos = new Float32Array(segs * 6), tt = new Float32Array(segs * 2); let v = 0, s = 0;
    for (const l of S.lens) {
      const arc = [0]; for (let i = 1; i < l; i++) arc.push(arc[i - 1] + Math.hypot(S.P[(v + i) * 2] - S.P[(v + i - 1) * 2], S.P[(v + i) * 2 + 1] - S.P[(v + i - 1) * 2 + 1]));
      for (let i = 0; i < l - 1; i++) for (let e = 0; e < 2; e++) { const q = v + i + e, o = s * 2 + e; pos[o * 3] = S.P[q * 2]; pos[o * 3 + 1] = S.P[q * 2 + 1]; tt[o] = arc[i + e] / (arc[l - 1] || 1); if (e) s++; }
      v += l;
    }
    const g = new THREE.BufferGeometry(); g.setAttribute("position", new THREE.BufferAttribute(pos, 3)); g.setAttribute("aT", new THREE.BufferAttribute(tt, 1));
    return new THREE.LineSegments(g, new THREE.ShaderMaterial({ vertexShader: LVS, fragmentShader: LFS, transparent: true, depthWrite: false,
      uniforms: { uDraw: { value: 0 }, uAlpha: { value: 0 }, uCol: { value: new THREE.Color(...INK) } } }));
  }
  function tubes(THREE, S, rad, mode, zref) {   // mode: where each streamline starts to grow: plane | mid | near | flat
    const dim = S.dim, NV = S.P.length / dim * 2;
    const rr = new Float32Array(NV), pos = new Float32Array(NV * 3), nxt = new Float32Array(NV * 3), col = new Float32Array(NV * 3), tt = new Float32Array(NV), side = new Float32Array(NV), del = new Float32Array(NV);
    let tri = 0; for (const l of S.lens) tri += (l - 1) * 2;
    const idx = new Uint32Array(tri * 3); let ii = 0, v = 0, si = 0;
    const get = (q, j) => (j < dim ? S.P[q * dim + j] : 0);
    for (const l of S.lens) {
      const arc = new Float32Array(l); let k = 0, best = 1e9;
      for (let i = 0; i < l; i++) {
        const q = v + i;
        if (i) arc[i] = arc[i - 1] + Math.hypot(get(q, 0) - get(q - 1, 0), get(q, 1) - get(q - 1, 1), get(q, 2) - get(q - 1, 2));
        const zz = get(q, 2), z = mode === "mid" ? Math.abs(zz - zref) : mode === "near" ? zz : Math.abs(zz); if (z < best) { best = z; k = i; }
      }
      // each streamline is drawn from one cortical end to the other: the end nearest Arnold's plane
      // (for the callosum and the other hemisphere: the end on Arnold's side) is where it starts
      if (mode === "flat") k = 0;
      else if (mode === "plane") k = Math.abs(get(v, 2)) <= Math.abs(get(v + l - 1, 2)) ? 0 : l - 1;
      else k = get(v, 2) <= get(v + l - 1, 2) ? 0 : l - 1;
      const tot = arc[l - 1] || 1;
      const dly = S.D ? S.D[si] / 255 : 0; const rnd = ((si * 2654435761) % 1000) / 1000;
      for (let i = 0; i < l; i++) {
        const q = v + i, r = i < l - 1 ? q + 1 : q - 1, fw = i < l - 1;
        for (let e = 0; e < 2; e++) {
          const o = q * 2 + e;
          for (let j = 0; j < 3; j++) {
            pos[o * 3 + j] = get(q, j); nxt[o * 3 + j] = fw ? get(r, j) : 2 * get(q, j) - get(r, j);
            col[o * 3 + j] = S.C ? S.C[q * 3 + j] / 255 : INK[j];
          }
          rr[o] = mode === "flat" ? 0.15 + 0.25 * rnd : rnd; side[o] = e ? 1 : -1; tt[o] = Math.abs(arc[i] - arc[k]) / tot; del[o] = dly;
        }
        if (fw) { const b = q * 2; idx[ii++] = b; idx[ii++] = b + 1; idx[ii++] = b + 2; idx[ii++] = b + 1; idx[ii++] = b + 3; idx[ii++] = b + 2; }
      }
      v += l; si++;
    }
    const g = new THREE.BufferGeometry();
    for (const [n, a, d] of [["position", pos, 3], ["aNext", nxt, 3], ["aC", col, 3], ["aT", tt, 1], ["aSide", side, 1], ["aDel", del, 1], ["aR", rr, 1]]) g.setAttribute(n, new THREE.BufferAttribute(a, d));
    g.setIndex(new THREE.BufferAttribute(idx, 1));
    const m = new THREE.ShaderMaterial({ vertexShader: TVS, fragmentShader: TFS, transparent: true, depthWrite: true, side: THREE.DoubleSide,
      uniforms: { uMorph: { value: 0 }, uGrow: { value: 0 }, uAlpha: { value: 0 }, uRes: { value: new THREE.Vector2(1, 1) }, uRad: { value: rad }, uMinPx: { value: 0.6 },
        uTint: { value: new THREE.Color(...INK) }, uTintK: { value: 0 }, uA: { value: -1e6 }, uB: { value: 1e6 }, uEdge: { value: 60 }, uC: { value: 1e6 }, uEdgeC: { value: 70 }, uD0: { value: 0 }, uD1: { value: 1 } } });
    const mesh = new THREE.Mesh(g, m); mesh.frustumCulled = false; return mesh;
  }
  const VIEW = { med: { rot: [0.2, -0.8], zoom: 1.3, aspect: 1.15, pan: [0, -0.1] }, ax: { rot: [-0.62, 0.0], zoom: 1.12, aspect: 1.6, pan: [-0.3, 0] } };
  window.TrachArnold = function (box, THREE, base) {
    const name = box.dataset.arnold, V = VIEW[name];
    const fail = (e) => { box.insertAdjacentHTML("beforeend", '<p style="font-size:12px;color:#a24b44">Figure could not load: ' + String((e && e.message) || e) + "</p>"); };
    if (!THREE) return fail("three.js missing");
    (window.__arnoldData ? Promise.resolve([window.__arnoldData[name].meta, Uint8Array.from(atob(window.__arnoldData[name].bin), (c) => c.charCodeAt(0)).buffer])
      : Promise.all([fetch(base + "arnold-" + name + ".json").then((r) => r.json()), fetch(base + "arnold-" + name + ".bin").then((r) => r.arrayBuffer())])).then(([meta, buf]) => {
      const W = meta.W, H = meta.H, FW = W * V.aspect, FH = H * 1.3;
      const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
      renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
      box.appendChild(renderer.domElement);
      const scene = new THREE.Scene(), fov = 16, camera = new THREE.PerspectiveCamera(fov, FW / FH, 10, 40000);
      const dist = (H * 1.14 / 2) / Math.tan((fov / 2) * Math.PI / 180) * 1.02;
      const pivot = new THREE.Group(), content = new THREE.Group(); pivot.add(content); scene.add(pivot);
      const plate = new THREE.Mesh(new THREE.PlaneGeometry(W, H), new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false }));
      content.add(plate);
      const R = meta.scale * 0.36;
      const TR = read(buf, meta.sets.trace, 2, false);
      const trace = lines(THREE, TR), traceT = tubes(THREE, TR, R, "flat");
      // the whole tractogram (Arnold's hemisphere, the commissures, the other hemisphere) revealed by two fronts
      // that leave Arnold's plane: one towards the lateral surface of his hemisphere, one across the midline to the other
      const brain = tubes(THREE, read(buf, meta.sets.all, 3, true), R, "plane");
      brain.material.uniforms.uMorph.value = 1; brain.material.uniforms.uGrow.value = 9;
      traceT.material.uniforms.uMorph.value = 1; traceT.material.depthWrite = false; traceT.renderOrder = 2;
      content.add(trace, traceT, brain);
      let zmin = 0, zmax = 0; { const p = brain.geometry.attributes.position.array; for (let i = 2; i < p.length; i += 6) { if (p[i] < zmin) zmin = p[i]; if (p[i] > zmax) zmax = p[i]; } }
      const zc = (zmin + zmax) / 2;
      const T = [traceT, brain];
      const resize = () => { const w = box.clientWidth, h = w * FH / FW; renderer.setSize(w, h); camera.aspect = FW / FH; camera.updateProjectionMatrix();
        const db = renderer.getDrawingBufferSize(new THREE.Vector2()), pr = renderer.getPixelRatio();
        T.forEach((m) => { m.material.uniforms.uRes.value.copy(db); m.material.uniforms.uMinPx.value = 1.1 * pr; }); };
      resize(); window.addEventListener("resize", resize);
      const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
      let t0 = 0, visible = true, raf = 0;
      const frame = (now) => {
        if (!t0) t0 = now;
        const t = window.__arnoldTime != null ? window.__arnoldTime : reduce ? 40000 : now - t0;
        // 1 the plate, 2 the engraved fibres traced as lines
        plate.material.opacity = ramp(t, 0, 1200) * (1 - 0.15 * ramp(t, 3000, 6500)) * (1 - ramp(t, 8000, 13000));
        trace.material.uniforms.uDraw.value = ramp(t, 900, 3600) * 1.01;
        trace.material.uniforms.uAlpha.value = 0.85 * (1 - ramp(t, 3600, 6200));
        // 3 the lines slowly thicken into tubes
        const thick = ramp(t, 3200, 6400);
        traceT.material.uniforms.uGrow.value = 2; traceT.material.uniforms.uRad.value = R * (0.15 + 0.85 * thick); traceT.material.uniforms.uC.value = -1e6;
        traceT.material.uniforms.uAlpha.value = 0.8 * thick * (1 - ramp(t, 6800, 11000));
        traceT.visible = traceT.material.uniforms.uAlpha.value > 0.005;
        // 4 two fronts leave the plane and reveal the tractography: Arnold's hemisphere first, then across to the other
        const u = brain.material.uniforms;
        // 4 the brain goes on being drawn in Arnold's manner, from his plane outwards and across to the other hemisphere
        u.uA.value = zmin * ramp(t, 5600, 11500, (x) => x) - 2;
        u.uB.value = zmax * ramp(t, 5600, 15500, (x) => 1 - Math.pow(1 - x, 1.4)) + 2;
        u.uAlpha.value = ramp(t, 5600, 6400);
        // 5 then the engraving turns into tractography, from left to right
        u.uC.value = (zmin - 160) + (zmax - zmin + 320) * ramp(t, 14500, 21500, (x) => x);
        const m = 1;
        // one continuous camera move
        const c = ramp(t, 6000, 21500, smoother), e = ramp(t, 11500, 21500, smoother);
        const sway = reduce ? 0 : Math.sin(Math.max(0, t - 21500) / 2800) * 0.14 * ramp(t, 21500, 24500);
        pivot.rotation.x = V.rot[0] * c; pivot.rotation.y = V.rot[1] * c + sway;
        pivot.position.z = zc * c; content.position.z = -zc * c;
        const cx = W * V.pan[0] * e, cy = H * V.pan[1] * e;
        camera.position.set(cx, cy, dist * (1 + (V.zoom - 1) * e)); camera.lookAt(cx, cy, 0);
        { const cd = camera.position.length(), span = Math.max(W, H) * 0.3; T.forEach((mm) => { mm.material.uniforms.uD0.value = cd - span; mm.material.uniforms.uD1.value = cd + span; }); }
        renderer.render(scene, camera);
        raf = visible ? requestAnimationFrame(frame) : 0;
      };
      let went = false;
      const go = () => {
        if (went) return; went = true;
        // on the website the animation starts when the figure scrolls into view, and pauses when it leaves
        if (!("IntersectionObserver" in window)) { raf = requestAnimationFrame(frame); return; }
        visible = false;
        new IntersectionObserver((es) => { visible = es.some((x) => x.isIntersecting); if (visible && !raf) raf = requestAnimationFrame(frame); }, { threshold: 0.35 }).observe(box);
      };
      new THREE.TextureLoader().load(window.__arnoldData ? window.__arnoldData[name].img : "assets/img/arnold-" + name + ".webp",
        (tex) => { plate.material.map = tex; plate.material.needsUpdate = true; go(); }, undefined, go);
      setTimeout(go, 2500);
    }).catch(fail);
  };
})();

// start: load three.js only on pages with the figure
(function () {
  const boxes = document.querySelectorAll("[data-arnold]");
  if (!boxes.length) return;
  const run = () => boxes.forEach((b) => window.TrachArnold(b, window.THREE, "assets/data/"));
  if (window.THREE) return run();
  const s = document.createElement("script");
  s.src = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js";
  s.onload = run; document.head.appendChild(s);
})();
