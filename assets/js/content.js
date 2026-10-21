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
  fetch("content/texts.txt", { cache: "no-cache" }).then((r) => r.text()).then((txt) => {
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

  // ---------- Collaborations (content/collaborations.txt) ----------
  const collab = document.getElementById("collab-list");
  if (collab) {
    load("content/collaborations.txt").then((list) => {
      collab.innerHTML = list.filter((c) => c.institution).map((c) => `<li class="collab${c.photo ? " has-photo" : ""}">
          ${c.photo ? `<img class="collab-logo" src="${esc(photoUrl(c.photo))}" alt="">` : ""}
          <h3>${linked(md(c.institution), c.link)}</h3>
          ${c.unit ? `<p>${md(c.unit)}</p>` : ""}
          ${c.topic ? `<p class="collab-topic"><span class="badge">${md(c.topic)}</span></p>` : ""}
          ${c.people ? `<p class="who">${md(c.people)}</p>` : ""}
          ${c.text ? `<p class="who">${md(c.text)}</p>` : ""}
        </li>`).join("");
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
      items = items.filter((t) => t.name);
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
