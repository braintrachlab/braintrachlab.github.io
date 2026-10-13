// TrachLab — publications list built from DOIs (metadata from Crossref)
(function () {
  const box = document.getElementById("pub-list");
  if (!box) return;

  // Used when Crossref cannot be reached
  const FALLBACK = {
    "10.1038/s41467-026-73731-8": {
      title: "Evolution of the frontal aslant tract and implications for primate vocalization and human speech",
      authors: ["Salvatore Citro", "Matt S. Dawson", "Ahmad Beyh", "Flavio Dell'Acqua", "Carlo Cavaliere", "Tim B. Dyrby", "Kristine Krug", "Maurice Ptito", "Lorenzo Carnevale", "Sergio Della Sala", "William D. Hopkins", "Marsel M. Mesulam", "Marco Catani"],
      journal: "Nature Communications", vol: "17", page: "7236", year: 2026, month: 6,
    },
    "10.1016/j.cortex.2025.01.010": {
      title: "Aleksander Luria and Oliver Sacks: An inspiring correspondence",
      authors: ["Sergio Della Sala", "Kate Edgar", "Elkhonon Goldberg", "Marco Catani"],
      journal: "Cortex", vol: "184", page: "298-310", year: 2025, month: 3,
    },
  };

  // Topic tags inferred from the title (an article can have several)
  const TOPICS = [
    ["history", /histor|correspondence|century|pioneer|legacy|biograph|luria|sacks|cajal|broca|wernicke|meynert|dejerine/i],
    ["comparative", /primate|chimpanzee|macaque|monkey|\bapes?\b|evolution|species|comparative|baboon/i],
    ["clinical", /patient|disease|alzheimer|dementia|aphasia|stroke|lesion|disorder|depress|schizophren|psychiatr|autism|parkinson|epilep|tumou?r|clinical|degenerat|impair/i],
    ["anatomy", /tract|fascicul|white matter|connect|pathway|anatom|tractograph|dissection|fib(er|re)/i],
  ];
  const LABEL = { anatomy: "Anatomy", comparative: "Comparative", clinical: "Health & disease", history: "History" };
  const topicsOf = (t) => {
    const f = TOPICS.filter(([, re]) => re.test(t)).map(([k]) => k);
    return f.length ? f : ["anatomy"];
  };

  const { esc, md, photoUrl, load } = window.TrachContent;
  const TOPIC_KEYS = Object.keys(LABEL);
  const strip = (s) => String(s || "").replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();

  async function meta(doi) {
    try {
      const r = await fetch("https://api.crossref.org/works/" + encodeURIComponent(doi));
      if (!r.ok) throw new Error(r.status);
      const m = (await r.json()).message;
      const dp = (m.issued && m.issued["date-parts"] && m.issued["date-parts"][0]) || [];
      return {
        doi,
        title: strip((m.title || [])[0]),
        authors: (m.author || []).map((a) => [a.given, a.family].filter(Boolean).join(" ") || a.name),
        journal: strip((m["container-title"] || [])[0]),
        vol: m.volume || "", page: m.page || m["article-number"] || "",
        year: dp[0] || 0, month: dp[1] || 0,
      };
    } catch (e) {
      return FALLBACK[doi] ? { doi, ...FALLBACK[doi] } : { doi, title: "", authors: [], journal: "", year: 0, month: 0 };
    }
  }

  // Entries: "doi:" plus optional fields that override or complete Crossref
  const merge = (entry, m) => {
    const o = { ...m };
    if (entry.title) o.title = entry.title;
    if (entry.authors) o.authors = entry.authors.split(/\s*,\s*/);
    if (entry.journal) o.journal = entry.journal;
    if (entry.year) { const [y, mo] = entry.year.split("-").map(Number); o.year = y; o.month = mo || 0; }
    if (entry.topic) o.topics = entry.topic.toLowerCase().split(/[\s,]+/).filter((t) => TOPIC_KEYS.includes(t));
    o.photo = entry.photo || "";
    o.text = entry.text || "";
    o.url = entry.link || (o.doi ? "https://doi.org/" + o.doi : "");
    return o;
  };
  Promise.all([load(box.dataset.src), load("content/team.txt").catch(() => [])]).then(([entries, team]) => {
    const names = team.map((p) => p.name).filter(Boolean);
    window.__trachNames = names;
    return Promise.all(entries.filter((e) => e.doi || e.title).map((e) =>
      (e.doi ? meta(e.doi.replace(/^https?:\/\/(dx\.)?doi\.org\//i, "")) : Promise.resolve({ doi: "", title: "", authors: [], journal: "", year: 0, month: 0 }))
        .then((m) => merge(e, m))));
  }).then((list) => {
    // drop duplicates
    const seen = new Set();
    list = list.filter((p) => { const k = (p.doi || p.title).toLowerCase(); return !seen.has(k) && seen.add(k); });
    list.sort((a, b) => (b.year - a.year) || (b.month - a.month));
    const groups = new Map();
    list.forEach((p) => {
      const y = p.year || "Other";
      if (!groups.has(y)) groups.set(y, []);
      groups.get(y).push(p);
    });
    let html = "";
    groups.forEach((items, y) => {
      html += `<div class="pub-group"><h2 class="pub-year">${y}</h2>`;
      items.forEach((p) => {
        const topics = p.topics && p.topics.length ? p.topics : (p.title ? topicsOf(p.title) : ["anatomy"]);
        let authors = esc(p.authors.join(", "));
        (window.__trachNames || []).forEach((n) => { authors = authors.split(esc(n)).join(`<strong>${esc(n)}</strong>`); });
        const ref = [p.journal && `<em>${esc(p.journal)}</em>`, p.vol, p.page].filter(Boolean).join(", ");
        const url = esc(p.url);
        const title = p.title ? md(p.title) : esc("doi.org/" + p.doi);
        html += `<article class="pub${p.photo ? " has-photo" : ""}" data-topic="${topics.join(" ")}">
          ${p.photo ? `<img class="pub-photo" src="${esc(photoUrl(p.photo))}" alt="" loading="lazy">` : ""}
          <div>
            <h3>${url ? `<a href="${url}" target="_blank" rel="noopener">${title}</a>` : title}</h3>
            ${authors ? `<p class="authors">${authors}</p>` : ""}
            ${(p.title && (ref || p.doi)) ? `<p class="journal">${ref}${ref && p.doi ? " · " : ""}${p.doi ? `<a href="https://doi.org/${esc(p.doi)}" target="_blank" rel="noopener">doi:${esc(p.doi)}</a>` : ""}</p>` : ""}
            ${p.text ? `<p class="pub-text">${md(p.text)}</p>` : ""}
          </div>
          <span class="tag">${p.title ? topics.map((t) => LABEL[t]).join(" · ") : ""}</span>
        </article>`;
      });
      html += "</div>";
    });
    box.innerHTML = html;
  });
})();
