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

  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
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

  window.TrachContent.lines(box.dataset.src).then((dois) => Promise.all(dois.map(meta))).then((list) => {
    // drop duplicates
    const seen = new Set();
    list = list.filter((p) => !seen.has(p.doi.toLowerCase()) && seen.add(p.doi.toLowerCase()));
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
        const topics = p.title ? topicsOf(p.title) : ["anatomy"];
        const authors = esc(p.authors.join(", "))
          .replace(/(Marco Catani|Giovanna Bubbico|Salvatore Citro)/g, "<strong>$1</strong>");
        const ref = [p.journal && `<em>${esc(p.journal)}</em>`, p.vol, p.page].filter(Boolean).join(", ");
        html += `<article class="pub" data-topic="${topics.join(" ")}">
          <div>
            <h3><a href="https://doi.org/${esc(p.doi)}" target="_blank" rel="noopener">${esc(p.title || "doi.org/" + p.doi)}</a></h3>
            ${authors ? `<p class="authors">${authors}</p>` : ""}
            ${p.title ? `<p class="journal">${ref ? ref + " · " : ""}<a href="https://doi.org/${esc(p.doi)}" target="_blank" rel="noopener">doi:${esc(p.doi)}</a></p>` : ""}
          </div>
          <span class="tag">${p.title ? topics.map((t) => LABEL[t]).join(" · ") : ""}</span>
        </article>`;
      });
      html += "</div>";
    });
    box.innerHTML = html;
  });
})();
