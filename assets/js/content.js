// TrachLab — renders the editable text files in /content
(function () {
  const esc = (s) => String(s || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const safeUrl = (u) => /^(https?:|mailto:)/i.test((u || "").trim()) ? u.trim() : "";

  // "key: value" blocks separated by blank lines; lines starting with # are ignored
  window.TrachContent = {
    load(file) {
      return fetch(file, { cache: "no-cache" }).then((r) => r.text()).then((txt) => {
        const blocks = [];
        let cur = null;
        txt.split(/\r?\n/).forEach((line) => {
          if (/^\s*#/.test(line)) return;
          if (!line.trim()) { if (cur) blocks.push(cur); cur = null; return; }
          const m = line.match(/^\s*([a-zA-Z]+)\s*:\s?(.*)$/);
          if (!m) return;
          cur = cur || {};
          cur[m[1].toLowerCase()] = m[2].trim();
        });
        if (cur) blocks.push(cur);
        return blocks;
      });
    },
    lines(file) {
      return fetch(file, { cache: "no-cache" }).then((r) => r.text()).then((txt) =>
        txt.split(/\r?\n/).map((l) => l.trim()).filter((l) => l && !l.startsWith("#")));
    },
  };
  const { load } = window.TrachContent;

  // ---------- Team ----------
  const team = document.getElementById("team-list");
  if (team) {
    load("content/team.txt").then((people) => {
      people = people.filter((p) => p.name);
      team.innerHTML = people.map((p, i) => {
        const ini = p.name.split(/\s+/).map((w) => w[0]).filter(Boolean).slice(0, 2).join("").toUpperCase();
        const pic = p.photo
          ? `<img src="assets/img/team/${esc(p.photo)}" alt="${esc(p.name)}" loading="lazy">`
          : `<span class="initials">${esc(ini)}</span>`;
        return `<button class="person reveal visible" data-i="${i}" aria-haspopup="dialog">
            <span class="figure portrait">${pic}</span>
            <span class="name">${esc(p.name)}</span>
            <span class="role">${esc(p.role)}</span>
          </button>`;
      }).join("");
      const panel = document.getElementById("member-panel");
      const body = panel.querySelector(".member-body");
      team.querySelectorAll(".person").forEach((btn) => btn.addEventListener("click", () => {
        const p = people[+btn.dataset.i];
        const links = (p.links || "").split("|").map((s) => s.split("=")).filter((x) => x.length >= 2)
          .map(([label, ...u]) => { const url = safeUrl(u.join("=")); return url ? `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(label.trim())}</a>` : ""; })
          .filter(Boolean).join(" · ");
        body.innerHTML = `
          ${p.photo ? `<img class="member-photo" src="assets/img/team/${esc(p.photo)}" alt="">` : ""}
          <span class="eyebrow">${esc(p.role)}</span>
          <h2>${esc(p.name)}</h2>
          ${p.bio ? `<p>${esc(p.bio)}</p>` : `<p class="muted">Biography coming soon.</p>`}
          ${links ? `<p class="member-links">${links}</p>` : ""}`;
        if (panel.showModal) panel.showModal(); else panel.setAttribute("open", "");
      }));
    });
  }

  // ---------- News ----------
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const fmtDate = (d) => { const [y, m, day] = d.split("-").map(Number); return `${day ? day + " " : ""}${months[(m || 1) - 1]} ${y}`; };
  const newsPage = document.getElementById("news-list");
  const newsHome = document.getElementById("news-latest");
  if (newsPage || newsHome) {
    load("content/news.txt").then((items) => {
      items = items.filter((n) => n.date && n.title).sort((a, b) => b.date.localeCompare(a.date));
      const today = new Date().toISOString().slice(0, 10);
      const title = (n) => safeUrl(n.link) ? `<a href="${esc(safeUrl(n.link))}" target="_blank" rel="noopener">${esc(n.title)}</a>` : esc(n.title);
      if (newsPage) {
        const row = (n) => `<article class="news-item">
            <time datetime="${esc(n.date)}">${esc(fmtDate(n.date))}</time>
            <div>
              <span class="badge">${esc(n.type || "News")}</span>
              <h3>${title(n)}</h3>
              ${n.text ? `<p>${esc(n.text)}</p>` : ""}
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
            <span class="badge">${esc(n.type || "News")}</span>
            <h3>${title(n)}</h3>
            <p><span class="muted">${esc(fmtDate(n.date))}</span>${n.text ? " — " + esc(n.text) : ""}</p>
          </div>`).join("");
      }
    });
  }
})();
