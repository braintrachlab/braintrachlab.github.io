// TrachLab — animated tractography hero
// Fibres (traced streamlines) draw themselves, then the arterial tree grows
// from the carotid trunk out to the peripheral branches.
(function () {
  const PALETTES = {
    // Ink: blue-grey fibres, crimson vessels
    ink: {
      fibre(a, d) {
        const t = (Math.cos(2 * a) + 1) / 2;               // horizontal ↔ vertical
        const r = 35 + t * 95, g = 57 + t * 100, b = 93 + t * 110;
        return `rgba(${r | 0},${g | 0},${b | 0},${0.35 + d * 0.6})`;
      },
      artery: [168, 18, 38],
    },
    // Direction-encoded colour (tractography convention), softened
    dec: {
      fibre(a, d) {
        const ax = Math.abs(Math.cos(a)), ay = Math.abs(Math.sin(a));
        // green = antero-posterior, blue = supero-inferior
        const r = 40 + ay * 30, g = 70 + ax * 110, b = 90 + ay * 120;
        return `rgba(${r | 0},${g | 0},${b | 0},${0.4 + d * 0.55})`;
      },
      artery: [200, 24, 40],
    },
    // Aurora: teal → indigo → violet by orientation
    aurora: {
      fibre(a, d) {
        const t = a / Math.PI;                              // 0..1, cyclic
        const stops = [[38, 140, 150], [52, 84, 170], [118, 72, 168], [38, 140, 150]];
        const s = t * 3, i = Math.min(2, s | 0), f = s - i;
        const c = stops[i].map((v, k) => v + (stops[i + 1][k] - v) * f);
        return `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${0.35 + d * 0.6})`;
      },
      artery: [214, 52, 64],
    },
  };

  const FIBRE_START = 0.0, FIBRE_SPREAD = 2.6, FIBRE_GROW = 1.6;   // seconds
  const ART_START = 1.2, ART_GROW = 3.4, ART_SOFT = 0.04;

  async function mount(el) {
    const base = el.dataset.src || "assets/hero/";
    const palette = PALETTES[el.dataset.palette] || PALETTES.ink;
    const [data, img] = await Promise.all([
      fetch(base + "fibres.json").then((r) => r.json()),
      new Promise((res, rej) => { const i = new Image(); i.onload = () => res(i); i.onerror = rej; i.src = base + "arteries.png"; }),
    ]);
    const W = data.w, H = data.h;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);

    const fc = document.createElement("canvas");
    const ac = document.createElement("canvas");
    for (const c of [fc, ac]) {
      c.width = W * dpr; c.height = H * dpr;
      c.style.cssText = "position:absolute;inset:0;width:100%;height:100%";
      el.appendChild(c);
    }
    el.style.aspectRatio = `${W} / ${H}`;
    const fx = fc.getContext("2d");
    fx.scale(dpr, dpr);
    fx.lineCap = "round"; fx.lineJoin = "round"; fx.lineWidth = parseFloat(el.dataset.width || "1");

    // Artery layer: precompute pixel lists (shade, growth time)
    const tmp = document.createElement("canvas");
    tmp.width = W; tmp.height = H;
    const tx = tmp.getContext("2d");
    tx.drawImage(img, 0, 0);
    const src = tx.getImageData(0, 0, W, H).data;
    const out = tx.createImageData(W, H);
    const idx = [], time = [], shade = [], alpha = [];
    for (let i = 0; i < W * H; i++) {
      const A = src[i * 4 + 3];
      if (A) { idx.push(i); shade.push(src[i * 4] / 255); time.push(src[i * 4 + 1] / 255); alpha.push(A); }
    }
    const ax = ac.getContext("2d");
    ax.imageSmoothingEnabled = true;
    const [ar, ag, ab] = palette.artery;

    const lines = data.lines.map((L) => ({
      p: L.p, n: L.p.length / 2, drawn: 0, t: L.t, color: palette.fibre(L.a, L.d),
    }));

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let t0 = null, artDone = false;

    function drawFibres(t) {
      let pending = false;
      for (const L of lines) {
        if (L.drawn >= L.n - 1) continue;
        pending = true;
        const k = Math.max(0, Math.min(1, (t - FIBRE_START - L.t * FIBRE_SPREAD) / FIBRE_GROW));
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

    function drawArteries(t) {
      const prog = (t - ART_START) / ART_GROW;
      if (prog <= 0) return true;
      const d = out.data;
      for (let k = 0; k < idx.length; k++) {
        const v = Math.max(0, Math.min(1, (prog - time[k]) / ART_SOFT + 1));
        const i = idx[k] * 4, s = 0.62 + shade[k] * 0.5;
        d[i] = Math.min(255, ar * s); const hl = Math.max(0, shade[k] - 0.8) * 160; d[i + 1] = Math.min(255, ag * s + hl); d[i + 2] = Math.min(255, ab * s + hl);
        d[i + 3] = alpha[k] * v;
      }
      tx.putImageData(out, 0, 0);
      ax.clearRect(0, 0, ac.width, ac.height);
      ax.drawImage(tmp, 0, 0, ac.width, ac.height);
      return prog < 1 + ART_SOFT;
    }

    function frame(now) {
      if (t0 === null) t0 = now;
      const t = reduce ? 99 : (now - t0) / 1000;
      const f = drawFibres(t);
      if (!artDone) artDone = !drawArteries(t);
      if (f || !artDone) requestAnimationFrame(frame);
    }

    // Start when visible
    const io = new IntersectionObserver((es) => {
      if (es.some((e) => e.isIntersecting)) { io.disconnect(); requestAnimationFrame(frame); }
    });
    io.observe(el);
  }

  window.TrachHero = { mount, palettes: Object.keys(PALETTES) };
  document.querySelectorAll("[data-tracto]").forEach((el) => mount(el).catch(console.error));
})();
