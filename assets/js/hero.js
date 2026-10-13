// TrachLab — animated tractography hero
// 1. White-matter streamlines draw themselves (2D canvas).
// 2. The arterial tree (3D mesh, WebGL) grows from the internal carotid
//    artery to the peripheral branches, following the distance measured
//    along the vessels themselves.
(function () {
  const PALETTES = {
    ink: {
      fibre(a, d) {
        const t = (Math.cos(2 * a) + 1) / 2;
        const r = 35 + t * 95, g = 57 + t * 100, b = 93 + t * 110;
        return `rgba(${r | 0},${g | 0},${b | 0},${0.35 + d * 0.6})`;
      },
      artery: [0.74, 0.06, 0.13],
    },
    dec: {
      fibre(a, d) {
        const ax = Math.abs(Math.cos(a)), ay = Math.abs(Math.sin(a));
        const r = 40 + ay * 30, g = 70 + ax * 110, b = 90 + ay * 120;
        return `rgba(${r | 0},${g | 0},${b | 0},${0.4 + d * 0.55})`;
      },
      artery: [0.80, 0.08, 0.14],
    },
    aurora: {
      fibre(a, d) {
        const t = a / Math.PI;
        const stops = [[38, 140, 150], [52, 84, 170], [118, 72, 168], [38, 140, 150]];
        const s = t * 3, i = Math.min(2, s | 0), f = s - i;
        const c = stops[i].map((v, k) => v + (stops[i + 1][k] - v) * f);
        return `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${0.35 + d * 0.6})`;
      },
      artery: [0.86, 0.17, 0.22],
    },
  };

  const FIBRE_SPREAD = 2.6, FIBRE_GROW = 1.6;   // seconds
  const ART_START = 1.4, ART_GROW = 5.0;

  const ease = (x) => x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2;

  function loadThree() {
    if (window.THREE) return Promise.resolve(window.THREE);
    return new Promise((res, rej) => {
      const s = document.createElement("script");
      s.src = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js";
      s.onload = () => res(window.THREE); s.onerror = rej;
      document.head.appendChild(s);
    });
  }

  async function arteryLayer(el, base, color, W, H) {
    const THREE = await loadThree();
    const [meta, buf] = await Promise.all([
      fetch(base + "arteries.json").then((r) => r.json()),
      fetch(base + "arteries.bin").then((r) => r.arrayBuffer()),
    ]);
    const nv = meta.nv, nt = meta.nt;
    let off = 0;
    const q = new Int16Array(buf, off, nv * 3); off += nv * 6;
    const tq = new Uint16Array(buf, off, nv); off += nv * 2;
    const vq = new Uint8Array(buf, off, nv); off += nv + meta.pad;
    const idx = new Uint32Array(buf, off, nt * 3);

    const pos = new Float32Array(nv * 3);
    for (let i = 0; i < nv * 3; i++) pos[i] = q[i] / meta.scale;
    const tt = new Float32Array(nv), vis = new Float32Array(nv);
    for (let i = 0; i < nv; i++) { tt[i] = tq[i] / 65535; vis[i] = vq[i] / 255; }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    geo.setAttribute("aT", new THREE.BufferAttribute(tt, 1));
    geo.setAttribute("aVis", new THREE.BufferAttribute(vis, 1));
    geo.setIndex(new THREE.BufferAttribute(idx, 1));
    geo.computeVertexNormals();

    const vert = `
      attribute float aT; attribute float aVis;
      varying vec3 vN; varying float vT; varying float vVis;
      void main() {
        vN = normalize(normalMatrix * normal); vT = aT; vVis = aVis;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }`;
    const frag = `
      uniform float uProg; uniform vec3 uColor; uniform float uGhost;
      varying vec3 vN; varying float vT; varying float vVis;
      void main() {
        if (vT > uProg) discard;
        if (uGhost < 0.5 && vVis < 0.5) discard;
        if (uGhost > 0.5 && vVis >= 0.5) discard;
        vec3 n = normalize(vN); if (!gl_FrontFacing) n = -n;
        vec3 L = normalize(vec3(-0.35, 0.55, 1.0));
        float diff = max(dot(n, L), 0.0);
        float spec = pow(max(dot(reflect(-L, n), vec3(0.0, 0.0, 1.0)), 0.0), 28.0);
        vec3 col = uColor * (0.32 + 0.8 * diff) + vec3(1.0) * 0.28 * spec;
        float front = smoothstep(uProg - 0.025, uProg, vT);
        col = mix(col, vec3(1.0, 0.82, 0.82), front * 0.7);
        gl_FragColor = vec4(col, uGhost > 0.5 ? 0.06 : 1.0);
      }`;
    const uniforms = () => ({ uProg: { value: 0 }, uColor: { value: new THREE.Color(...color) }, uGhost: { value: 0 } });
    const solid = new THREE.ShaderMaterial({ vertexShader: vert, fragmentShader: frag, uniforms: uniforms(), side: THREE.DoubleSide });
    const ghost = new THREE.ShaderMaterial({ vertexShader: vert, fragmentShader: frag, uniforms: uniforms(), side: THREE.DoubleSide, transparent: true, depthWrite: false });
    ghost.uniforms.uGhost.value = 1;

    const scene = new THREE.Scene();
    const m2 = new THREE.Mesh(geo, ghost); m2.renderOrder = 0; scene.add(m2);
    const m1 = new THREE.Mesh(geo, solid); m1.renderOrder = 1; scene.add(m1);
    const cam = new THREE.OrthographicCamera(0, W, H, 0, -3000, 3000);

    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.domElement.style.cssText = "position:absolute;inset:0;width:100%;height:100%";
    el.appendChild(renderer.domElement);
    const fit = () => { const r = el.getBoundingClientRect(); renderer.setSize(r.width, r.height, false); };
    fit();
    new ResizeObserver(() => { fit(); renderer.render(scene, cam); }).observe(el);

    return (p) => {
      solid.uniforms.uProg.value = ghost.uniforms.uProg.value = p;
      renderer.render(scene, cam);
    };
  }

  async function mount(el) {
    const base = el.dataset.src || "assets/hero/";
    const palette = PALETTES[el.dataset.palette] || PALETTES.ink;
    const data = await fetch(base + "fibres.json").then((r) => r.json());
    const W = data.w, H = data.h;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    el.style.aspectRatio = `${W} / ${H}`;

    const fc = document.createElement("canvas");
    fc.width = W * dpr; fc.height = H * dpr;
    fc.style.cssText = "position:absolute;inset:0;width:100%;height:100%";
    el.appendChild(fc);
    const fx = fc.getContext("2d");
    fx.scale(dpr, dpr);
    fx.lineCap = "round"; fx.lineJoin = "round";
    fx.lineWidth = parseFloat(el.dataset.width || "1");

    let drawArt = null;
    try { drawArt = await arteryLayer(el, base, palette.artery, W, H); } catch (e) { console.warn("Arteries unavailable", e); }

    const lines = data.lines.map((L) => ({ p: L.p, n: L.p.length / 2, drawn: 0, t: L.t, color: palette.fibre(L.a, L.d) }));
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    function drawFibres(t) {
      let pending = false;
      for (const L of lines) {
        if (L.drawn >= L.n - 1) continue;
        pending = true;
        const k = Math.max(0, Math.min(1, (t - L.t * FIBRE_SPREAD) / FIBRE_GROW));
        const target = Math.floor(k * (L.n - 1));
        if (target <= L.drawn) continue;
        fx.strokeStyle = L.color;
        fx.beginPath();
        fx.moveTo(L.p[L.drawn * 2], L.p[L.drawn * 2 + 1]);
        for (let j = L.drawn + 1; j <= target; j++) fx.lineTo(L.p[j * 2], L.p[j * 2 + 1]);
        fx.stroke();
        L.drawn = target;
      }
      return pending;
    }

    let t0 = null;
    function frame(now) {
      if (t0 === null) t0 = now;
      const t = reduce ? 99 : (now - t0) / 1000;
      const f = drawFibres(t);
      const p = Math.max(0, Math.min(1, (t - ART_START) / ART_GROW));
      if (drawArt) drawArt(ease(p) * 1.03);
      if (f || p < 1) requestAnimationFrame(frame);
    }
    const io = new IntersectionObserver((es) => {
      if (es.some((e) => e.isIntersecting)) { io.disconnect(); requestAnimationFrame(frame); }
    });
    io.observe(el);
  }

  window.TrachHero = { mount, palettes: Object.keys(PALETTES) };
  document.querySelectorAll("[data-tracto]").forEach((el) => mount(el).catch(console.error));
})();
