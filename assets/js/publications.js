// TrachLab — publications list built from DOIs (metadata from Crossref)
(function () {
  const box = document.getElementById("pub-list");
  if (!box) return;

  // Stored metadata: used when Crossref cannot be reached (it limits the number of requests per visitor)
  const FALLBACK = {
    "10.1002/alz.70126": {
      title: "Microstructural assessment of the locus coeruleus–entorhinal cortex pathway and association with ATN markers in cognitive impairment",
      authors: ["Marco Aiello", "Moira Marizzoni", "Pasquale Borrelli", "Carlo Cavaliere", "Federica Ribaldi", "Valentina Garibotto", "Max Scheffler", "Ileana Jelescu", "Jorge Jovicich", "Marco Catani", "Marco Salvatore", "Giovanni Battista Frisoni", "Michela Pievani"],
      journal: "Alzheimer's & Dementia", vol: "21", page: "e70126", year: 2025, month: 4,
    },
    "10.1016/j.cortex.2024.10.004": {
      title: "Inside soviet neuropsychology: Luciano Mecacci's personal reflections on Alexander Luria",
      authors: ["Marco Catani", "Luciano Mecacci"], journal: "Cortex", vol: "183", page: "105-115", year: 2025, month: 2,
    },
    "10.1016/j.cortex.2024.10.006": {
      title: "Following in Luria's footsteps: The first training booklet for the neuropsychological assessment of patients with brain lesions",
      authors: ["Marco Catani", "Luciano Mecacci"], journal: "Cortex", vol: "183", page: "146-166", year: 2025, month: 2,
    },
    "10.1016/j.biopsych.2025.06.008": {
      title: "Successful Evidence-Based Parenting Programs Are Associated With Brain Changes and Improved Reward Processing in Boys With Conduct Problems",
      authors: ["Arjun Sethi", "Suzanne O'Brien", "James Blair", "Essi M. Viding", "Daniel Shani", "Oliver Joe Robinson", "Mitul Ashok Mehta", "Christine Ecker", "Marija M. Petrinovic", "Marco Catani", "Nigel Blackwood", "Moira Doolan", "Declan Murphy", "Stephen Scott", "Michael Craig"],
      journal: "Biological Psychiatry", vol: "99", page: "407-417", year: 2025, month: 6,
    },
    "10.1016/j.cortex.2025.02.002": {
      title: "Luria's legacy in the era of cognitive neuroscience",
      authors: ["Marco Catani", "Elkhonon Goldberg"], journal: "Cortex", vol: "184", page: "311-313", year: 2025, month: 3,
    },
    "10.1523/JNEUROSCI.1646-24.2025": {
      title: "Evidence for an Evolutionary Continuity in Social Dominance: Insights from Nonhuman Primate Tractography",
      authors: ["Julie Royo", "Thomas Orset", "Marco Catani", "Pierre Pouget", "Michel Thiebaut de Schotten"],
      journal: "The Journal of Neuroscience", vol: "45", page: "e1646242025", year: 2025, month: 7,
    },
    "10.1016/j.biopsych.2024.07.024": {
      title: "Brain-Charting Autism and Attention-Deficit/Hyperactivity Disorder Reveals Distinct and Overlapping Neurobiology",
      authors: ["Saashi A. Bedford", "Meng-Chuan Lai", "Michael V. Lombardo", "Bhismadev Chakrabarti", "Amber Ruigrok", "John Suckling", "Evdokia Anagnostou", "Jason P. Lerch", "Margot Taylor", "Rob Nicolson", "Stelios Georgiades", "Jennifer Crosbie", "Russell Schachar", "Elizabeth Kelley", "Jessica Jones", "Paul D. Arnold", "Eric Courchesne", "Karen Pierce", "Lisa T. Eyler", "Kathleen Campbell", "Cynthia Carter Barnes", "Jakob Seidlitz", "Aaron F. Alexander-Bloch", "Edward T. Bullmore", "Simon Baron-Cohen", "Richard A.I. Bethlehem", "Marco Catani"],
      journal: "Biological Psychiatry", vol: "97", page: "517-530", year: 2025, month: 3,
    },
    "10.1016/j.cortex.2025.09.004": {
      title: "Bekhterev's case: Amnesia due to bi-hippocampal damage 50 years before HM",
      authors: ["Sergio Della Sala", "Marco Catani", "Luciano Mecacci"],
      journal: "Cortex", vol: "192", page: "165-176", year: 2025, month: 11,
    },
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

  const CACHE = "trach-pub-v1:";
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));
  async function getJSON(doi) {
    // 1) Crossref API (retry when it asks to slow down)  2) doi.org content negotiation (CSL-JSON)
    for (let k = 0; k < 2; k++) {
      try {
        const r = await fetch("https://api.crossref.org/works/" + encodeURIComponent(doi));
        if (r.ok) return (await r.json()).message;
        if (r.status !== 429 && r.status < 500) break;
      } catch (e) { /* network */ }
      await wait(700);
    }
    const r = await fetch("https://doi.org/" + doi, { headers: { Accept: "application/vnd.citationstyles.csl+json" } });
    if (!r.ok) throw new Error(r.status);
    return r.json();
  }
  async function meta(doi) {
    try { const c = JSON.parse(localStorage.getItem(CACHE + doi) || "null"); if (c && c.title) return c; } catch (e) {}
    if (FALLBACK[doi]) return { doi, ...FALLBACK[doi] };          // stored: no request needed
    try {
      const m = await getJSON(doi);
      const dp = ((m.issued || m["published-print"] || m["published-online"] || {})["date-parts"] || [[]])[0] || [];
      const out = {
        doi,
        title: strip((m.title || [])[0]),
        authors: (m.author || []).map((a) => [a.given, a.family].filter(Boolean).join(" ") || a.name),
        journal: strip((m["container-title"] || [])[0]),
        vol: m.volume || "", page: m.page || m["article-number"] || "",
        year: dp[0] || 0, month: dp[1] || 0,
      };
      if (!out.title) throw new Error("empty");
      try { localStorage.setItem(CACHE + doi, JSON.stringify(out)); } catch (e) {}
      return out;
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
    const todo = entries.filter((e) => e.doi || e.title), res = new Array(todo.length);
    let next = 0;
    const worker = async () => {                       // 3 requests at a time, so Crossref does not refuse them
      while (next < todo.length) {
        const i = next++, e = todo[i];
        const m = e.doi ? await meta(e.doi.trim().replace(/^https?:\/\/(dx\.)?doi\.org\//i, "")) : { doi: "", title: "", authors: [], journal: "", year: 0, month: 0 };
        res[i] = merge(e, m);
      }
    };
    return Promise.all([worker(), worker(), worker()]).then(() => res);
  }).then((list) => {
    // drop duplicates
    const seen = new Set();
    list = list.filter((p) => { const k = (p.doi || p.title).toLowerCase(); return !seen.has(k) && seen.add(k); });
    list.sort((a, b) => (b.year - a.year) || (b.month - a.month));
    const groups = new Map();
    list.forEach((p) => {
      const y = p.year || "Other publications";
      if (!groups.has(y)) groups.set(y, []);
      groups.get(y).push(p);
    });
    let html = "";
    groups.forEach((items, y) => {
      html += `<div class="pub-group"><h2 class="pub-year">${y}</h2>`;
      items.forEach((p) => {
        const topics = p.topics && p.topics.length ? p.topics : (p.title ? topicsOf(p.title) : ["anatomy"]);
        let al = p.authors;
        if (al.length > 12) {                          // long consortium lists: first authors, lab members, last author
          const lab = window.__trachNames || [];
          const keep = al.filter((a, i) => i < 8 || i === al.length - 1 || lab.includes(a));
          al = keep.slice(0, 8).concat(["…"], keep.slice(8));
        }
        let authors = esc(al.join(", ")).replace(/, …,/, " …");
        (window.__trachNames || []).forEach((n) => { authors = authors.split(esc(n)).join(`<strong>${esc(n)}</strong>`); });
        const ref = [p.journal && `<em>${esc(p.journal)}</em>`, p.vol, p.page].filter(Boolean).join(", ");
        const url = esc(p.url);
        const title = p.title ? md(p.title) : `<span class="pub-pending">Article details could not be loaded — open it at doi.org/${esc(p.doi)}</span>`;
        html += `<article class="pub${p.photo ? " has-photo" : ""}" data-topic="${topics.join(" ")}">
          ${p.photo ? `<img class="pub-photo" src="${esc(photoUrl(p.photo))}" alt="" loading="lazy">` : ""}
          <div>
            ${p.title ? `<span class="tag">${topics.map((t) => LABEL[t]).join(" · ")}</span>` : ""}
            <h3>${url ? `<a href="${url}" target="_blank" rel="noopener">${title}</a>` : title}</h3>
            ${authors ? `<p class="authors">${authors}</p>` : ""}
            ${(p.title && (ref || p.doi)) ? `<p class="journal">${ref}${ref && p.doi ? " · " : ""}${p.doi ? `<a href="https://doi.org/${esc(p.doi)}" target="_blank" rel="noopener">doi:${esc(p.doi)}</a>` : ""}</p>` : ""}
            ${p.text ? `<p class="pub-text">${md(p.text)}</p>` : ""}
          </div>
        </article>`;
      });
      html += "</div>";
    });
    box.innerHTML = html;
  });
})();
