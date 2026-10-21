// TrachLab — reads the editable files in /content and fills the pages.
//
// ONE SYNTAX FOR EVERY FILE
//   key: value            one field per line
//   (empty line)          separates two entries
//   # ...                 comment, ignored
//   repeating a key       also starts a new entry (handy for lists of DOIs)
//
// ONE MARKUP FOR EVERY TEXT
//   *italic*   **bold**   [label](https://...)   " | " = new line
//
// COMMON FIELDS
//   photo: file name of a picture in assets/img/   (e.g. photo: seminar-2026.jpg)
//   link:  https://...   (makes the title clickable)
//   text:  a paragraph of description
(function () {
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  // web addresses, e-mails, or pages of this site (e.g. atlas.html)
  const safeUrl = (u) => { u = (u || "").trim(); return /^(https?:|mailto:)/i.test(u) || /^[\w\-./#?=&]+$/.test(u) ? u : ""; };
  const md = (t) => esc(t)
    .replace(/\[([^\]]+)\]\(((?:https?:|mailto:)[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .split(" | ").join("<br>");
  const photoUrl = (name) => {
    name = (name || "").trim();
    if (!name) return "";
    if (/^https?:\/\//i.test(name)) return name;
    return "assets/img/" + name.replace(/^\/+/, "").replace(/^assets\/img\//, "");
  };
  const linked = (html, url) => (safeUrl(url) ? `<a href="${esc(safeUrl(url))}" target="_blank" rel="noopener">${html}</a>` : html);

  function parse(txt) {
    const blocks = [];
    let cur = null;
    txt.split(/\r?\n/).forEach((line) => {
      if (/^\s*#/.test(line)) return;
      if (!line.trim()) { if (cur) blocks.push(cur); cur = null; return; }
      const m = line.match(/^\s*([a-zA-Z0-9_.]+)\s*:\s?(.*)$/);
      if (!m) return;
      const k = m[1].toLowerCase();
      if (cur && k in cur) { blocks.push(cur); cur = null; }
      cur = cur || {};
      cur[k] = m[2].trim();
    });
    if (cur) blocks.push(cur);
    return blocks;
  }
  const load = (file) => fetch(file, { cache: "no-cache" }).then((r) => r.text()).then(parse);
  window.TrachContent = { load, parse, md, esc, safeUrl, photoUrl, linked };

  // ---------- Page texts (content/texts.txt) ----------
  const done = () => document.documentElement.classList.remove("texts-loading");
  const textsTxt = fetch("content/texts.txt", { cache: "no-cache" }).then((r) => r.text());
  textsTxt.then((txt) => {
    const T = {};
    txt.split(/\r?\n/).forEach((line) => {
      if (/^\s*#/.test(line)) return;
      const m = line.match(/^\s*([a-z0-9_.]+)\s*:\s?(.*)$/);
      if (m) T[m[1]] = m[2].trim();
    });
    document.querySelectorAll("[data-text]").forEach((el) => {
      const k = el.dataset.text;
      if (!(k in T)) return;
      el.innerHTML = md(T[k]);
      el.hidden = !T[k];
    });
    document.querySelectorAll("[data-image]").forEach((el) => {
      const k = el.dataset.image;
      if (!(k in T)) return;
      const box = el.querySelector(".parallax-inner") || el;
      box.innerHTML = T[k]
        ? `<img src="${esc(photoUrl(T[k]))}" alt="">`
        : `<span class="img-empty">${esc(el.dataset.label || "")}</span>`;
    });
    document.querySelectorAll(".contact-block").forEach((b) => {
      const ps = [...b.querySelectorAll("p[data-text]")];
      if (ps.length) b.hidden = ps.every((p) => p.hidden);
    });
    const pg = document.body.dataset.page;
    if (pg && T[pg + ".page_title"]) document.title = T[pg + ".page_title"];
  }).catch(() => {}).finally(done);

  // ---------- Team (content/team.txt) ----------
  const team = document.getElementById("team-list");
  if (team) {
    load("content/team.txt").then((people) => {
      people = people.filter((p) => p.name);
      team.innerHTML = people.map((p, i) => {
        const ini = p.name.split(/\s+/).map((w) => w[0]).filter(Boolean).slice(0, 2).join("").toUpperCase();
        const pic = p.photo ? `<img src="${esc(photoUrl(p.photo))}" alt="${esc(p.name)}" loading="lazy">` : `<span class="initials">${esc(ini)}</span>`;
        return `<button class="person reveal visible" data-i="${i}" aria-haspopup="dialog">
            <span class="figure portrait">${pic}</span>
            <span class="name">${esc(p.name)}</span>
            <span class="role">${md(p.role)}</span>
          </button>`;
      }).join("");
      const panel = document.getElementById("member-panel");
      const body = panel.querySelector(".member-body");
      team.querySelectorAll(".person").forEach((btn) => btn.addEventListener("click", () => {
        const p = people[+btn.dataset.i];
        const text = p.text || p.bio || "";
        const links = p.links || "";
        body.innerHTML = `
          ${p.photo ? `<img class="member-photo" src="${esc(photoUrl(p.photo))}" alt="">` : ""}
          <span class="eyebrow">${md(p.role)}</span>
          <h2>${linked(esc(p.name), p.link)}</h2>
          ${text ? `<p>${md(text)}</p>` : `<p class="muted">Biography coming soon.</p>`}
          ${links ? `<p class="member-links">${md(links)}</p>` : ""}`;
        if (panel.showModal) panel.showModal(); else panel.setAttribute("open", "");
      }));
    });
  }

  // ---------- Collaborations (content/collaborations.txt): map + list grouped by city ----------
  const collab = document.getElementById("collab-list");
  if (collab) {
    const svg = document.getElementById("collab-map");
    const mapP = svg ? fetch("assets/data/collab-map.json").then((r) => r.json()).catch(() => null) : Promise.resolve(null);
    Promise.all([load("content/collaborations.txt"), mapP]).then(([list, MAP]) => {
      list = list.filter((c) => c.institution || c.people);
      // group by place (or by coordinates when the place is missing)
      const cities = [];
      list.forEach((c) => {
        const m = (c.coords || "").match(/(-?\d+(?:\.\d+)?)\s*[,;\s]\s*(-?\d+(?:\.\d+)?)/);
        const key = (c.place || "").trim() || (m ? m[0] : "Other");
        let k = cities.find((x) => x.key === key);
        if (!k) { k = { key, place: c.place || "", lat: m ? +m[1] : null, lon: m ? +m[2] : null, left: /^l/i.test(c.label || ""), items: [] }; cities.push(k); }
        if (/^l/i.test(c.label || "")) k.left = true;
        k.items.push(c);
      });
      const region = (c) => (c.lat == null ? 2 : c.lon < -30 ? 1 : 0);
      cities.sort((a, b) => region(a) - region(b) || (b.lat || 0) - (a.lat || 0));
      const cityName = (c) => esc((c.place || "").split(",")[0].trim() || "Other");
      const country = (c) => esc((c.place || "").split(",").slice(1).join(",").trim());
      // one card per collaboration, in alphabetical order of the city (3 per row)
      const cards = [];
      cities.forEach((c, i) => c.items.forEach((x, k) => cards.push({ c, i, x, k })));
      cards.sort((a, b) => cityName(a.c).localeCompare(cityName(b.c)) || a.k - b.k);
      collab.innerHTML = cards.map(({ c, i, x }) => `
        <section class="cm-city" data-i="${i}" tabindex="0">
          <h3>${cityName(c)}<small>${country(c)}</small></h3>
          <div class="cm-col${x.photo ? " has-photo" : ""}">
            ${x.photo ? `<img class="collab-logo" src="${esc(photoUrl(x.photo))}" alt="">` : ""}
            ${x.institution ? `<p class="cm-inst">${linked(md(x.institution), x.link)}</p>` : ""}
            ${x.unit ? `<p class="cm-unit">${md(x.unit)}</p>` : ""}
            ${x.topic ? `<p class="cm-topic"><span class="badge">${md(x.topic)}</span></p>` : ""}
            ${x.people ? `<p class="cm-who">${md(x.people)}</p>` : ""}
            ${x.text ? `<p class="cm-unit">${md(x.text)}</p>` : ""}
          </div>
        </section>`).join("");
      const count = document.getElementById("collab-count");
      if (count) count.textContent = `${list.length} collaborations · ${cities.filter((c) => c.place || c.lat != null).length} cities`;
      if (!svg || !MAP) { if (svg) svg.closest(".cm-map").hidden = true; return; }

      // the map: one continuous Equal Earth projection (equal-area, true width of the Atlantic);
      // coastlines are drawn in advance (assets/data/collab-map.json, Natural Earth 1:10m),
      // the cities are projected here with the same formula
      const NS = "http://www.w3.org/2000/svg", R = Math.PI / 180;
      const el = (tag, attrs, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); (parent || svg).appendChild(e); return e; };
      const P = MAP.proj;
      const A1 = 1.340264, A2 = -0.081106, A3 = 0.000893, A4 = 0.003796, M = Math.sqrt(3) / 2;
      const raw = (l, f) => { const t = Math.asin(M * Math.sin(f)), t2 = t * t, t6 = t2 * t2 * t2;
        return [l * Math.cos(t) / (M * (A1 + 3 * A2 * t2 + t6 * (7 * A3 + 9 * A4 * t2))), t * (A1 + A2 * t2 + t6 * (A3 + A4 * t2))]; };
      const c0 = raw(P.center[0] * R, P.center[1] * R);
      const project = (lat, lon) => { let l = (lon + P.rot) * R; l = Math.atan2(Math.sin(l), Math.cos(l)); const q = raw(l, lat * R);
        return [P.translate[0] + P.scale * (q[0] - c0[0]), P.translate[1] - P.scale * (q[1] - c0[1])]; };
      svg.setAttribute("viewBox", `0 0 ${MAP.W} ${MAP.H}`);
      el("path", { class: "cm-grat", d: MAP.grat });
      MAP.land.forEach((d) => el("path", { class: "cm-land", d }));
      { const box = svg.closest(".cm-map"); if (box.scrollWidth > box.clientWidth + 4) box.scrollLeft = (box.scrollWidth - box.clientWidth) * 0.92; }   // phones: open on Europe

      // cities closer than a few pixels (London and Cambridge; Chieti, Pozzilli and Naples) share one marker
      const pts = cities.map((c, i) => (c.lat == null ? null : { i, xy: project(c.lat, c.lon) })).filter((q) => q && q.xy[0] >= 0 && q.xy[0] <= MAP.W && q.xy[1] >= 0 && q.xy[1] <= MAP.H);
      const groups = [];
      pts.forEach((q) => {
        const g = groups.find((g) => g.members.some((m) => Math.hypot(m.xy[0] - q.xy[0], m.xy[1] - q.xy[1]) < 22));
        if (g) g.members.push(q); else groups.push({ members: [q] });
      });
      const marks = el("g", {});
      const mk = [];          // marker element per city index
      groups.forEach((g, gi) => {
        const ids = g.members.map((m) => m.i).sort((a, b) => (cities[b].lat - cities[a].lat));
        const x = g.members.reduce((s, m) => s + m.xy[0], 0) / g.members.length, y = g.members.reduce((s, m) => s + m.xy[1], 0) / g.members.length;
        const nn = ids.reduce((s, i) => s + cities[i].items.length, 0);
        const names = ids.map((i) => (cities[i].place || "").split(",")[0]);
        const left = ids.some((i) => cities[i].left);
        const node = el("g", { class: "cm-mk", tabindex: 0, role: "button", "data-ids": ids.join(","), transform: `translate(${x.toFixed(1)},${y.toFixed(1)})`,
          "aria-label": `${names.join(", ")}: ${nn} collaboration${nn > 1 ? "s" : ""}` }, marks);
        el("circle", { class: "cm-halo", r: 9 + Math.min(nn, 6) * 2.5 }, node);
        // the exact position of each city, as a small point, when several share a marker
        if (g.members.length > 1) g.members.forEach((m) => el("circle", { class: "cm-pt", r: 2.2, cx: (m.xy[0] - x).toFixed(1), cy: (m.xy[1] - y).toFixed(1) }, node));
        el("circle", { class: "cm-dot", r: nn > 1 ? 8 : 5, ...(g.members.length > 1 ? { opacity: 0.92 } : {}) }, node);
        if (nn > 1) el("text", { class: "cm-n", "text-anchor": "middle", dy: "0.35em" }, node).textContent = nn;
        const tx = el("text", { x: (left ? -1 : 1) * (nn > 1 ? 13 : 10), y: 5 - (names.length - 1) * 8.5, "text-anchor": left ? "end" : "start" }, node);
        names.forEach((nm, k) => { const ts = el("tspan", { x: (left ? -1 : 1) * (nn > 1 ? 13 : 10), dy: k ? 17 : 0 }, tx); ts.textContent = nm; });
        ids.forEach((i) => { mk[i] = node; });
      });
      let selected = null;
      const hover = matchMedia("(hover: hover)").matches;
      const idsOf = (g) => g.dataset.ids.split(",").map(Number);
      const light = (ids) => { marks.querySelectorAll(".cm-mk").forEach((g) => g.classList.toggle("on", idsOf(g).some((i) => (ids || []).includes(i) || (selected || []).includes(i)))); };
      const select = (ids, fromMap) => {
        selected = ids; light(null);
        collab.querySelectorAll(".cm-city").forEach((s) => s.classList.toggle("on", ids.includes(+s.dataset.i)));
        if (fromMap) { const t = collab.querySelector(`.cm-city[data-i="${ids[0]}"]`); if (t) t.scrollIntoView({ block: "nearest", behavior: "smooth" }); }
      };
      marks.addEventListener("click", (e) => { const g = e.target.closest(".cm-mk"); if (g) select(idsOf(g), true); });
      marks.addEventListener("keydown", (e) => { const g = e.target.closest(".cm-mk"); if (g && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); select(idsOf(g), true); } });
      marks.addEventListener("mouseover", (e) => { const g = e.target.closest(".cm-mk"); if (g && hover) light(idsOf(g)); });
      marks.addEventListener("mouseleave", () => light(null));
      collab.addEventListener("click", (e) => { const s = e.target.closest(".cm-city"); if (s && !e.target.closest("a")) select([+s.dataset.i], false); });
      collab.addEventListener("keydown", (e) => { const s = e.target.closest(".cm-city"); if (s && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); select([+s.dataset.i], false); } });
      collab.addEventListener("mouseover", (e) => { const s = e.target.closest(".cm-city"); if (s && hover) light([+s.dataset.i]); });
      collab.addEventListener("mouseleave", () => light(null));
      // the markers appear one by one, east to west, when the map comes into view
      const order = [...marks.querySelectorAll(".cm-mk")].sort((a, b) => b.transform.baseVal[0].matrix.e - a.transform.baseVal[0].matrix.e);
      if (matchMedia("(prefers-reduced-motion: reduce)").matches || !("IntersectionObserver" in window)) { order.forEach((g) => g.classList.add("in")); return; }
      svg.classList.add("cm-anim");
      const io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) { io.disconnect(); order.forEach((g, k) => setTimeout(() => g.classList.add("in"), 200 + k * 120)); } }, { threshold: 0.3 });
      io.observe(svg);
    });
  }

  // ---------- White matter pioneers (content/pioneers.txt): portrait timeline in Research ----------
  const pnBox = document.getElementById("pioneers");
  if (pnBox) {
    const erasP = textsTxt.then((txt) => {
      const m = txt.match(/^\s*research\.history\.eras\s*:\s?(.*)$/m);
      return m && m[1].trim() ? m[1].trim() : pnBox.dataset.eras || "";
    }).catch(() => pnBox.dataset.eras || "");
    Promise.all([load("content/pioneers.txt"), erasP]).then(([list, erasTxt]) => {
      const P = list.filter((p) => p.name && p.born).map((p) => ({ ...p, b: parseInt(p.born, 10), y: parseInt(p.year || p.born, 10) }))
        .sort((a, b) => a.b - b.b);
      if (!P.length) return;
      const ERAS = erasTxt.split(";").map((e) => e.trim().match(/^(.*\S)\s+(\d+)$/)).filter(Boolean).map((m) => [m[1], +m[2]]);
      // compressed time scale: log of the distance from today blended with the order, then a minimum spacing
      const lg = (y) => -Math.log(2030 - y);
      const L0 = lg(P[0].b), L1 = lg(P[P.length - 1].b) || L0 + 1;
      const GAP = 104, W = Math.max(GAP * (P.length - 1) * 1.3, 1000);
      const xs = P.map((p, i) => 0.38 * (lg(p.b) - L0) / (L1 - L0 || 1) + 0.62 * i / Math.max(1, P.length - 1)).map((f) => 56 + f * W);
      for (let i = 1; i < xs.length; i++) xs[i] = Math.max(xs[i], xs[i - 1] + GAP);
      const xOf = (y) => { const k = P.findIndex((p) => p.b >= y); return k < 0 ? xs[xs.length - 1] : xs[k]; };
      const when = (y) => (y < 1000 ? "c. " + y : String(y));
      const face = (p) => (p.portrait ? `<img src="${esc(photoUrl(p.portrait))}" alt="" draggable="false" loading="lazy">` : "");
      const track = pnBox.querySelector(".pn-track"), card = pnBox.querySelector(".pn-card"), ribbon = pnBox.querySelector(".pn-ribbon");
      const END = xs[xs.length - 1] + 110;                       // the axis runs on to today
      track.style.width = END + 20 + "px";
      track.innerHTML = `<span class="pn-axis" style="width:${END}px"></span><span class="pn-today" style="left:${END}px">Today</span><span class="pn-head"><span class="pn-year"></span></span>` +
        ERAS.map(([e, y]) => `<span class="pn-era" style="left:${xOf(y) - 44}px">${esc(e)}</span>`).join("") +
        P.map((p, i) => `<button class="pn-person" id="pn${i}" role="tab" aria-selected="false" data-i="${i}" style="left:${xs[i]}px" aria-label="${esc(p.name)}, ${esc(p.life || "")}">
            <span class="pn-face">${face(p)}</span><span class="pn-name">${esc(p.name)}</span>
            <span class="pn-tick"></span><span class="pn-life">${esc((p.life || "").replace(/\s*–\s*/g, "–"))}</span></button>`).join("");
      let current = Math.max(0, P.findIndex((p) => /^y(es)?$/i.test(p.start || "")));
      const show = (i) => {
        current = i;
        const p = P[i];
        track.querySelectorAll(".pn-person").forEach((b) => b.setAttribute("aria-selected", String(+b.dataset.i === i)));
        const title = `<b>${esc(p.short || p.name.split(/\s+/).pop())}, ${when(p.y)}</b>`;
        card.innerHTML = `
          <div class="pn-portrait">${face(p)}</div>
          <figure class="pn-figure${p.image ? " has-img" : ""}">${p.image
            ? `<a class="pn-img" href="${esc(photoUrl(p.image))}" target="_blank" rel="noopener" title="Open the full figure"><img src="${esc(photoUrl(p.image))}" alt="${esc(p.figure || "")}"></a>
               <figcaption>${md(p.figure || "")}${p.source ? `<span class="pn-source">${md(p.source)}</span>` : ""}</figcaption>`
            : `<div>${title}${md(p.figure || "")}${p.source ? `<span class="pn-source">${md(p.source)}</span>` : ""}<span class="pn-ph">Figure in preparation</span></div>`}</figure>
          <div class="pn-text">
            <span class="eyebrow">Key work · ${when(p.y)}</span>
            <h3>${esc(p.name)}</h3>
            ${p.life ? `<p class="pn-dates">${esc(p.life)}</p>` : ""}
            ${p.text ? `<p>${md(p.text)}</p>` : ""}
            ${p.ref ? `<p class="pn-ref">${md(p.ref)}</p>` : ""}
          </div>`;
      };
      track.addEventListener("mouseover", (e) => { const b = e.target.closest(".pn-person"); if (b && matchMedia("(hover: hover)").matches && +b.dataset.i !== current) show(+b.dataset.i); });
      track.addEventListener("click", (e) => { const b = e.target.closest(".pn-person"); if (b) show(+b.dataset.i); });
      track.addEventListener("keydown", (e) => {
        if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
        e.preventDefault();
        const n = Math.max(0, Math.min(P.length - 1, current + (e.key === "ArrowRight" ? 1 : -1)));
        show(n); document.getElementById("pn" + n).focus({ preventScroll: false });
      });
      const centre = (i, smooth) => ribbon.scrollTo({ left: Math.max(0, xs[i] - ribbon.clientWidth / 2), behavior: smooth ? "smooth" : "auto" });
      const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (reduce || !("IntersectionObserver" in window)) { show(current); centre(current); return; }

      // ---- intro: the axis is drawn from antiquity to today, each pioneer appears as the line reaches them
      const persons = [...track.querySelectorAll(".pn-person")], eras = [...track.querySelectorAll(".pn-era")];
      const eraX = ERAS.map(([, y]) => xOf(y) - 44);
      const axis = track.querySelector(".pn-axis"), head = track.querySelector(".pn-head"), yearEl = track.querySelector(".pn-year");
      const NOW = new Date().getFullYear();
      const stops = xs.map((x, i) => [x, P[i].b]).concat([[END, NOW]]);
      const yearAt = (x) => {                                   // the axis is compressed: read the year back from the stops
        if (x <= stops[0][0]) return stops[0][1];
        for (let k = 1; k < stops.length; k++) if (x <= stops[k][0]) {
          const [x0, y0] = stops[k - 1], [x1, y1] = stops[k];
          return Math.round(y0 + (y1 - y0) * (x - x0) / (x1 - x0));
        }
        return NOW;
      };
      pnBox.classList.add("pn-intro-on");
      card.classList.add("pn-wait");
      let raf = 0, t0 = 0, done = false;
      const D = Math.min(9000, 2600 + P.length * 280);        // about 8 s for twenty people
      const ease = (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
      const frame = (now) => {
        if (!t0) t0 = now;
        const k = Math.min(1, (now - t0) / D), x = 4 + ease(k) * (END - 4);
        axis.style.transform = `scaleX(${x / END})`;
        head.style.left = x + "px";
        const y = yearAt(x);
        yearEl.textContent = y >= NOW ? "Today" : y < 1000 ? y + " AD" : y;
        persons.forEach((b, i) => b.classList.toggle("in", xs[i] <= x + 30));
        eras.forEach((e, i) => e.classList.toggle("in", eraX[i] + 44 <= x + 30));
        ribbon.scrollLeft = Math.max(0, x - ribbon.clientWidth * 0.62);
        if (k < 1) raf = requestAnimationFrame(frame); else finish(true);
      };
      const finish = (natural) => {
        if (done) return; done = true;
        cancelAnimationFrame(raf);
        pnBox.classList.remove("pn-intro-on");
        pnBox.classList.add("pn-intro-done");
        axis.style.transform = "";
        show(current); card.classList.remove("pn-wait");
        setTimeout(() => centre(current, true), natural ? 500 : 0);
      };
      ["pointerdown", "wheel", "touchstart", "keydown"].forEach((ev) => ribbon.addEventListener(ev, () => finish(false), { once: true, passive: true }));
      const io = new IntersectionObserver((es) => {
        if (es.some((e) => e.isIntersecting)) { io.disconnect(); setTimeout(() => { if (!done) raf = requestAnimationFrame(frame); }, 250); }
      }, { threshold: 0.45 });
      io.observe(ribbon);
    });
  }

  // ---------- Nomina Anatomica (content/nomina.txt): Terminologia Neuroanatomica, in TNA order ----------
  const nomList = document.getElementById("nomina-list");
  if (nomList) {
    load("content/nomina.txt").then((items) => {
      items = items.filter((n) => n.latin);
      const search = document.getElementById("nomina-search");
      const filters = document.getElementById("nomina-filters");
      const index = document.getElementById("nomina-letters");
      const groups = [...new Set(items.map((n) => n.group || "Terms"))];
      const slug = (g) => "g-" + g.toLowerCase().replace(/[^a-z0-9]+/g, "-");
      filters.innerHTML = ["All", ...groups].map((x, i) => `<button class="${i ? "" : "active"}" data-g="${esc(x)}">${esc(x)}</button>`).join("");
      let grp = "All";
      const uk = (t) => t.replace(/fibers/g, "fibres").replace(/fiber/g, "fibre").replace(/center/g, "centre").replace(/Semioval/g, "Semi-oval");   // only spelling
      const row = (n) => {
        const lv = Math.max(0, Math.min(3, parseInt(n.level || "0", 10) || 0));
        const en = n.english ? `${md(n.english)}${n.us && uk(n.us) !== n.english ? ` <span class="us">(US ${md(n.us)})</span>` : ""}` : "";
        const meta = [
          n.latin_syn ? `<span><em>Lat. syn.</em> ${md(n.latin_syn)}</span>` : "",
          n.synonyms ? `<span><em>Syn.</em> ${md(n.synonyms)}</span>` : "",
          n.other ? `<span><em>Also</em> ${md(n.other)}</span>` : "",
        ].join("");
        return `<article class="nomen lv${lv}" id="tna-${esc(n.tna || "")}">
            <span class="tna">${esc(n.tna || "")}</span>
            <div>
              <h3 lang="la">${md(n.latin)}</h3>
              ${en ? `<p class="en">${en}</p>` : ""}
              ${meta ? `<p class="nomen-meta">${meta}</p>` : ""}
              ${n.note ? `<p class="nomen-note">${md(n.note)}</p>` : ""}
              ${n.text ? `<p>${md(n.text)}</p>` : ""}
            </div>
          </article>`;
      };
      function draw() {
        const q = (search.value || "").trim().toLowerCase();
        const shown = items.filter((n) => (grp === "All" || (n.group || "Terms") === grp) && (!q || Object.values(n).join(" ").toLowerCase().includes(q)));
        const gs = groups.filter((g) => shown.some((n) => (n.group || "Terms") === g));
        index.innerHTML = gs.map((g) => `<a href="#${slug(g)}">${esc(g)}</a>`).join("");
        nomList.innerHTML = gs.length
          ? gs.map((g) => `<section class="nomina-group" id="${slug(g)}"><h2 class="nomina-letter">${esc(g)}</h2>${shown.filter((n) => (n.group || "Terms") === g).map(row).join("")}</section>`).join("")
          : `<p class="muted">No term found.</p>`;
      }
      search.addEventListener("input", draw);
      filters.querySelectorAll("button").forEach((b) => b.addEventListener("click", () => {
        filters.querySelectorAll("button").forEach((x) => x.classList.toggle("active", x === b));
        grp = b.dataset.g; draw();
      }));
      draw();
    });
  }

  // ---------- Tools (content/tools.txt) ----------
  const toolList = document.getElementById("tool-list");
  if (toolList) {
    load("content/tools.txt").then((items) => {
      const hiddenPages = ((document.querySelector('meta[name="hidden-pages"]') || {}).content || "").split(" ").filter(Boolean);
      items = items.filter((t) => t.name && !hiddenPages.includes((t.link || "").trim()));   // no cards for pages in preparation
      toolList.innerHTML = items.length ? items.map((t) => {
        const inner = `${t.photo ? `<img class="tool-photo" src="${esc(photoUrl(t.photo))}" alt="" loading="lazy">` : ""}
            ${t.type ? `<span class="badge">${esc(t.type)}</span>` : ""}
            <h3>${md(t.name)}</h3>
            ${t.text ? `<p>${md(t.text)}</p>` : ""}
            ${safeUrl(t.link) ? `<span class="tool-more">Open &rarr;</span>` : ""}`;
        const u = safeUrl(t.link);
        return u ? `<a class="tool-card" href="${esc(u)}"${/^https?:/i.test(u) ? ' target="_blank" rel="noopener"' : ""}>${inner}</a>`
                 : `<div class="tool-card">${inner}</div>`;
      }).join("") : `<p class="muted">Tools will be listed here soon.</p>`;
    });
  }

  // ---------- News & events (content/news.txt) ----------
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const fmtDate = (d) => { const [y, m, day] = d.split("-").map(Number); return `${day ? day + " " : ""}${m ? months[m - 1] + " " : ""}${y}`; };
  const newsPage = document.getElementById("news-list");
  const newsHome = document.getElementById("news-latest");
  if (newsPage || newsHome) {
    load("content/news.txt").then((items) => {
      items = items.filter((n) => n.date && n.title).sort((a, b) => b.date.localeCompare(a.date));
      const today = new Date().toISOString().slice(0, 10);
      const pic = (n, cls) => (n.photo ? `<img class="${cls}" src="${esc(photoUrl(n.photo))}" alt="" loading="lazy">` : "");
      if (newsPage) {
        const row = (n) => `<article class="news-item${n.photo ? " has-photo" : ""}">
            <time datetime="${esc(n.date)}">${esc(fmtDate(n.date))}</time>
            <div>
              <span class="badge">${esc(n.type || "News")}</span>
              <h3>${linked(md(n.title), n.link)}</h3>
              ${n.text ? `<p>${md(n.text)}</p>` : ""}
              ${pic(n, "news-photo")}
            </div>
          </article>`;
        const up = items.filter((n) => n.date > today).reverse();
        const past = items.filter((n) => n.date <= today);
        newsPage.innerHTML =
          (up.length ? `<h2 style="margin-top:20px">Upcoming events</h2>${up.map(row).join("")}` : "") +
          `<h2 style="margin-top:${up.length ? 80 : 20}px">News</h2>` +
          (past.length ? past.map(row).join("") : `<p class="muted">News will appear here soon.</p>`);
      }
      if (newsHome) {
        const latest = items.slice(0, 3);
        if (!latest.length) { newsHome.closest("section").style.display = "none"; return; }
        newsHome.innerHTML = latest.map((n) => `<div class="card">
            ${pic(n, "card-photo")}
            <span class="badge">${esc(n.type || "News")}</span>
            <h3>${linked(md(n.title), n.link)}</h3>
            <p><span class="muted">${esc(fmtDate(n.date))}</span>${n.text ? " — " + md(n.text) : ""}</p>
          </div>`).join("");
      }
    });
  }
})();
