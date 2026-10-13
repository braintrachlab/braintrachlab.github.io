#!/usr/bin/env python3
"""TrachLab site generator.

Writes the HTML pages from the templates below. Every visible text comes from
content/texts.txt (created/updated by this script: existing values are kept,
new keys are added with their default text). The same file is also read in the
browser, so edits made on GitHub show up without re-running this script.

Usage:  python3 tools/build_site.py      (from the repository root)
"""
import os, re, html
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXTS = os.path.join(ROOT, "content", "texts.txt")

# ---------------------------------------------------------------- texts store
def read_texts():
    vals = {}
    if os.path.exists(TEXTS):
        for line in open(TEXTS, encoding="utf-8"):
            if line.lstrip().startswith("#") or ":" not in line:
                continue
            k, v = line.split(":", 1)
            k = k.strip()
            if re.fullmatch(r"[a-z0-9_.]+", k):
                k = re.sub(r"\.image$", ".photo", k)   # old name of the image keys
                vals[k] = v.strip()
    return vals

SAVED = read_texts()
REG = OrderedDict()          # key -> default, in page order
SECTIONS = []                # (first key, heading) for comments in texts.txt

def section(title):
    SECTIONS.append((len(REG), title))

def val(key, default):
    if key not in REG:
        REG[key] = default
    return SAVED.get(key, default)

def md(s):
    """Tiny markup: *italic*, **bold**, [label](url), ' | ' = line break."""
    s = html.escape(s, quote=True)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+|mailto:[^)\s]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
    return s.replace(" | ", "<br>")

def T(tag, key, default, cls="", extra=""):
    """An element whose content is the editable text `key`. Empty text hides it."""
    v = val(key, default)
    c = f' class="{cls}"' if cls else ""
    hidden = " hidden" if not v.strip() else ""
    return f'<{tag}{c} data-text="{key}"{extra}{hidden}>{md(v)}</{tag}>'

def IMG(key, label, cls="figure", style="", parallax=True):
    """Image slot: file name in assets/img/ taken from texts.txt."""
    v = val(key, "")
    st = f' style="{style}"' if style else ""
    if v:
        inner = f'<img src="assets/img/{html.escape(v)}" alt="">'
    else:
        inner = f'<span class="img-empty">{label}</span>'
    if parallax:
        inner = f'<div data-speed="0.08" class="parallax-inner">{inner}</div>'
        cls += " parallax"
    return f'<div class="{cls}" data-image="{key}" data-label="{label}"{st}>{inner}</div>'

# ---------------------------------------------------------------- layout
NAV = [("index.html", "nav.home", "Home"), ("about.html", "nav.about", "About us"),
       ("research.html", "nav.research", "Research"), ("publications.html", "nav.publications", "Publications"),
       ("news.html", "nav.news", "News & Events"), ("contacts.html", "nav.contacts", "Contacts")]

# ---------------------------------------------------------------- cache busting
# Every asset reference gets ?v=<hash of the file>, so a browser can never combine an
# old cached file with a new one (e.g. an old figure layout with a new picture).
import hashlib, glob
def _ver(rel):
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        return None
    return hashlib.md5(open(path, "rb").read()).hexdigest()[:8]

def _stamp(text, attr_re):
    def rep(m):
        rel = m.group(2)
        v = _ver(rel)
        return m.group(1) + rel + (f"?v={v}" if v else "") + m.group(4)
    return re.sub(attr_re, rep, text)

ASSET_RE = r'((?:href|src|data-brain)=")(assets/[^"?]+)(\?v=[0-9a-f]+)?(")'

def stamp_svgs():
    # pictures inside the animated figures first, then the figures themselves are hashed
    for svg in glob.glob(os.path.join(ROOT, "assets", "img", "*.svg")):
        t = open(svg, encoding="utf-8").read()
        t2 = _stamp(t, ASSET_RE)
        if t2 != t:
            open(svg, "w", encoding="utf-8").write(t2)
stamp_svgs()

def page(filename, title_key, title_default, desc_key, desc_default, body, extra=""):
    pagekey = title_key.split(".")[0]
    title = html.escape(val(title_key, title_default))
    desc = html.escape(val(desc_key, desc_default))
    nav = "\n".join(f'          <li><a href="{h}" data-text="{k}">{md(val(k, d))}</a></li>' for h, k, d in NAV)
    foot = "\n".join(f'          <li><a href="{h}">{md(val(k, d))}</a></li>' for h, k, d in NAV)
    out = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <meta name="description" content="{desc}">
  <link rel="icon" href="assets/img/favicon.svg" type="image/svg+xml">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400;1,500&family=Inter:wght@300;400;500&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="assets/css/style.css">
  <script>document.documentElement.classList.add("texts-loading");setTimeout(function(){{document.documentElement.classList.remove("texts-loading")}},1500);</script>
</head>
<body data-page="{pagekey}">
  <header class="site-header">
    <div class="container nav">
      <a class="brand" href="index.html" data-text="site.logo">{md(val("site.logo", "Trach*Lab*"))}</a>
      <button class="nav-toggle" aria-label="Open menu" aria-expanded="false">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 7h18M3 12h18M3 17h18"/></svg>
      </button>
      <nav>
        <ul class="nav-links">
{nav}
        </ul>
      </nav>
    </div>
  </header>

  <main>
{body}
  </main>

  <footer class="site-footer">
    <div class="container footer-grid">
      <div>
        <a class="brand" href="index.html" data-text="site.logo">{md(val("site.logo", "Trach*Lab*"))}</a>
        {T("p", "footer.tagline", "White matter neuroanatomy & history of neuroscience")}
        <p>&copy; <span id="year"></span> <span data-text="site.name">{md(val("site.name", "TrachLab"))}</span></p>
      </div>
      <nav>
        <ul class="footer-links">
{foot}
        </ul>
      </nav>
    </div>
  </footer>

  <script src="assets/js/main.js"></script>
  <script src="assets/js/content.js"></script>
{extra}</body>
</html>
'''
    out = _stamp(out, ASSET_RE)
    with open(os.path.join(ROOT, filename), "w", encoding="utf-8") as f:
        f.write(out)

def card(n, key, title, text, d=""):
    return f'''          <div class="card reveal{d}">
            <span class="num">{n}</span>
            {T("h3", key + ".title", title)}
            {T("p", key + ".text", text)}
          </div>'''

# ================================================================= HOME
section("GENERAL — logo, menu and footer (shown on every page). In the logo, the part between *stars* is shown in blue italics")
val("site.logo", "Trach*Lab*")
val("site.name", "TrachLab")
for _, k, d in NAV:
    val(k, d)
val("footer.tagline", "White matter neuroanatomy & history of neuroscience")

section("HOME PAGE")
HERO = ('<div class="hero-art hero-plate" data-brain="assets/img/dejerine-lines.svg" role="img" '
        'aria-label="Coronal section of the human brain from Dejerine\'s atlas, with the white matter fibres redrawn as streamlines"></div>')
home = f'''
    <section class="hero">
      <div class="container">
        <div class="hero-content">
          {T("span", "home.eyebrow", "Neuroanatomy lab", "eyebrow reveal")}
          {T("h1", "home.title", "Mapping the *connections* of the human brain", "reveal d1")}
          {T("p", "home.lead", "We study the white matter pathways that link brain regions: their anatomy in the human brain and, through comparative studies, in non-human primates; their functions; and how they change in health and disease.", "lead reveal d2")}
          <div class="reveal d3">
            <a class="btn" href="research.html" data-text="home.button1">{md(val("home.button1", "Our research"))}</a>
            <a class="btn ghost" href="about.html" data-text="home.button2">{md(val("home.button2", "About us"))}</a>
          </div>
        </div>
      </div>
      {HERO}
      <span class="scroll-cue">Scroll</span>
    </section>

    <section class="soft">
      <div class="container grid-2" style="align-items:center">
        <div>
          {T("span", "home.who.eyebrow", "Who we are", "eyebrow reveal")}
          {T("h2", "home.who.title", "Anatomy as the foundation of brain function", "reveal d1")}
          <hr class="divider reveal d1">
          {T("p", "home.who.p1", "TrachLab is a research group devoted to the description of the white matter connections of the human brain. By combining detailed anatomical study with the analysis of their functional role, we aim to understand how the networks support brain functions, in healthy individuals and in people with neurological conditions.", "reveal d2")}
          {T("p", "home.who.p2", "Alongside this work, the lab cultivates a strong interest in the history of neuroscience, tracing how our knowledge of the brain's connections has taken shape over the centuries.", "reveal d2")}
          <a class="link-arrow reveal d3" href="about.html" data-text="home.who.link">{md(val("home.who.link", "Learn more about the lab"))}</a>
        </div>
        {IMG("home.who.photo", "Lab image", "figure reveal d2")}
      </div>
    </section>

    <section>
      <div class="container">
        <div class="section-head">
          {T("span", "home.areas.eyebrow", "Research areas", "eyebrow reveal")}
          {T("h2", "home.areas.title", "What we study", "reveal d1")}
        </div>
        <div class="grid-4">
{card("i.", "home.area1", "White matter anatomy", "Detailed description of the course, organisation and terminations of the brain's association, projection and commissural pathways.")}
{card("ii.", "home.area2", "Comparative neuroanatomy", "Comparing white matter pathways in humans and non-human primates to understand how brain connections evolved and what is distinctive about the human brain.", " d1")}
{card("iii.", "home.area3", "Connections & disease", "How the disruption of white matter pathways relates to clinical symptoms in patients with neurological and psychiatric conditions.", " d2")}
{card("iv.", "home.area4", "History of neuroscience", "The figures, ideas and discoveries that shaped our understanding of brain anatomy and connectivity, from early anatomists to the present.", " d3")}
        </div>
        <p class="reveal" style="margin-top:48px"><a class="link-arrow" href="research.html" data-text="home.areas.link">{md(val("home.areas.link", "Explore our research"))}</a></p>
      </div>
    </section>

    <section class="soft">
      <div class="container">
        {T("p", "home.quote", "Every function of the brain depends on the pathways that carry information from one region to another.", "quote reveal")}
      </div>
    </section>

    <section>
      <div class="container">
        <div class="section-head">
          {T("span", "home.news.eyebrow", "Latest", "eyebrow reveal")}
          {T("h2", "home.news.title", "News & Events", "reveal d1")}
        </div>
        <div class="grid-3" id="news-latest"></div>
        <p class="reveal" style="margin-top:48px"><a class="link-arrow" href="news.html" data-text="home.news.link">{md(val("home.news.link", "All news & events"))}</a></p>
      </div>
    </section>

    <section class="soft">
      <div class="container narrow" style="text-align:center">
        {T("h2", "home.join.title", "Interested in working with us?", "reveal")}
        {T("p", "home.join.text", "We welcome collaborations and enquiries from students and researchers.", "reveal d1")}
        <a class="btn reveal d2" href="contacts.html" data-text="home.join.button">{md(val("home.join.button", "Get in touch"))}</a>
      </div>
    </section>
'''
page("index.html", "home.page_title", "TrachLab — White Matter Neuroanatomy",
     "home.page_description", "TrachLab studies the white matter connections of the human brain, their functions in health and disease, and the history of neuroscience.", home)

# ================================================================= ABOUT
section("ABOUT US PAGE (team members are in content/team.txt, collaborations in content/collaborations.txt)")
about = f'''
    <header class="page-header">
      <div class="container">
        {T("span", "about.eyebrow", "People", "eyebrow reveal")}
        {T("h1", "about.title", "Our team", "reveal d1")}
        {T("p", "about.intro", "", "reveal d2")}
      </div>
    </header>

    <section id="team">
      <div class="container">
        <div class="people" id="team-list"></div>
      </div>
    </section>

    <dialog class="member-panel" id="member-panel">
      <button class="close" aria-label="Close">&times;</button>
      <div class="member-body"></div>
    </dialog>

    <section class="soft">
      <div class="container">
        <div class="section-head">
          {T("span", "about.network.eyebrow", "Network", "eyebrow reveal")}
          {T("h2", "about.network.title", "Collaborations", "reveal d1")}
        </div>
        <ul class="collabs" id="collab-list"></ul>
      </div>
    </section>
'''
page("about.html", "about.page_title", "About us — TrachLab", "about.page_description", "Team and collaborations of TrachLab.", about)

# ================================================================= RESEARCH
section("RESEARCH PAGE (an empty value hides the paragraph; images: file name in assets/img/)")
def rblock(n, key, title, p1, p2, image_label, soft, image_left, figure=None):
    text = f'''        <div>
          <span class="eyebrow reveal">{n}</span>
          {T("h2", key + ".title", title, "reveal d1")}
          <hr class="divider reveal d1">
          {T("p", key + ".p1", p1, "reveal d2")}
          {T("p", key + ".p2", p2, "reveal d2")}
        </div>'''
    fig = figure or "        " + IMG(key + ".photo", image_label, "figure reveal" + ("" if image_left else " d1"))
    inner = (fig + "\n" + text) if image_left else (text + "\n" + fig)
    return f'''    <section{' class="soft"' if soft else ''}>
      <div class="container grid-2" style="align-items:center">
{inner}
      </div>
    </section>
'''

ARC = lambda: f'''        <figure class="reveal" style="margin:0">
          <div class="arc-figure" data-brain="assets/img/arcuate.svg" role="img" aria-label="The three segments of the arcuate fasciculus redrawn as streamlines"></div>
          <div class="fat-legend arc-legend">
            <span class="fat-item"><span class="fat-key arc-key-long"></span>{T("span", "research.anatomy.legend1", "Long segment")}</span>
            <span class="fat-item"><span class="fat-key arc-key-anterior"></span>{T("span", "research.anatomy.legend2", "Anterior segment")}</span>
            <span class="fat-item"><span class="fat-key arc-key-posterior"></span>{T("span", "research.anatomy.legend3", "Posterior segment")}</span>
          </div>
          {T("figcaption", "research.anatomy.caption", "The three segments of the arcuate fasciculus, redrawn as streamlines.", "plate-caption arc-caption")}
        </figure>'''

DEJ = lambda: f'''        <figure class="reveal d1" style="margin:0">
          <div class="plate-figure" data-brain="assets/img/dejerine-lines.svg" role="img" aria-label="Coronal section of the human brain from Dejerine's atlas, with the white matter fibres redrawn as streamlines"></div>
          {T("figcaption", "research.history.caption", "Coronal section from J. Dejerine, *Anatomie des centres nerveux* (1895–1901), drawing by H. Gillet, with the fibres of the white matter redrawn as streamlines.", "plate-caption")}
        </figure>'''

def comparative():
    key = "research.comparative"
    species = [("macaque", "Macaque"), ("chimpanzee", "Chimpanzee"), ("human", "Human")]
    cells = "\n".join(f'''          <figure class="fat-cell">
            <div data-brain="assets/img/fat-{sp}.svg" role="img" aria-label="Frontal aslant tract of the {label.lower()} brain"></div>
            {T("figcaption", f"{key}.species{i + 1}", label, "fat-species")}
          </figure>''' for i, (sp, label) in enumerate(species))
    return f'''    <section class="soft">
      <div class="container">
        <div class="grid-2" style="align-items:end">
          <div>
            <span class="eyebrow reveal">02</span>
            {T("h2", key + ".title", "Comparative neuroanatomy", "reveal d1")}
            <hr class="divider reveal d1">
          </div>
          <div>
            {T("p", key + ".p1", "By comparing the white matter of the human brain with that of non-human primates, we study how connections have changed during evolution and how these changes relate to abilities such as language and vocal communication.", "reveal d2")}
            {T("p", key + ".p2", "", "reveal d2")}
          </div>
        </div>
        <div class="fat-row reveal">
{cells}
        </div>
        <div class="fat-legend reveal">
          <span class="fat-item"><span class="fat-key fat-key-orange"></span>{T("span", key + ".legend1", "Prefrontal FAT")}</span>
          <span class="fat-item"><span class="fat-key fat-key-green"></span>{T("span", key + ".legend2", "Precentral FAT")}</span>
        </div>
        {T("p", key + ".caption", "The frontal aslant tract (FAT) in the macaque, chimpanzee and human brain, redrawn as streamlines from [Citro et al., *Nature Communications* (2026)](https://doi.org/10.1038/s41467-026-73731-8).", "plate-caption fat-caption reveal")}
      </div>
    </section>
'''

research = f'''
    <header class="page-header">
      <div class="container">
        {T("span", "research.eyebrow", "Research", "eyebrow reveal")}
        {T("h1", "research.title", "Our research", "reveal d1")}
        {T("p", "research.intro", "From the detailed anatomy of single pathways and their evolution across primates, to their role in disease and the history of how they were discovered.", "reveal d2")}
      </div>
    </header>

{rblock("01", "research.anatomy", "White matter anatomy", "We describe the course, organisation and cortical terminations of the white matter tracts of the human brain, building an accurate anatomical map of its association, projection and commissural connections.", "", "Image", False, True, figure=ARC())}
{comparative()}
{rblock("03", "research.clinical", "Connections in health and disease", "By studying the functions of white matter pathways, we investigate how their damage or alteration contributes to the clinical picture of patients with neurological and psychiatric conditions.", "", "Image", False, True)}
{rblock("04", "research.history", "History of neuroscience", "The lab explores the history of brain anatomy and neuroscience: the scientists, methods and ideas that, over the centuries, led to our current understanding of the brain's connections.", "", "", True, False, figure=DEJ())}'''
page("research.html", "research.page_title", "Research — TrachLab", "research.page_description",
     "Research areas of TrachLab: white matter anatomy, comparative neuroanatomy, connections in disease, history of neuroscience.", research)

# ================================================================= PUBLICATIONS
section("PUBLICATIONS PAGE (the list of DOIs is in content/publications.txt)")
pubs = f'''
    <header class="page-header">
      <div class="container">
        {T("h1", "publications.title", "Publications", "reveal")}
        {T("p", "publications.intro", "Selected articles from the lab.", "reveal d1")}
      </div>
    </header>

    <section style="padding-top:60px">
      <div class="container narrow">
        <div class="filters reveal">
          <button class="active" data-filter="all">All</button>
          <button data-filter="anatomy">White matter anatomy</button>
          <button data-filter="comparative">Comparative neuroanatomy</button>
          <button data-filter="clinical">Health &amp; disease</button>
          <button data-filter="history">History of neuroscience</button>
        </div>
        <div id="pub-list" data-src="content/publications.txt">
          <p class="pub-loading">Loading publications…</p>
        </div>
      </div>
    </section>
'''
page("publications.html", "publications.page_title", "Publications — TrachLab", "publications.page_description",
     "Publications of TrachLab.", pubs, '  <script src="assets/js/publications.js"></script>\n')

# ================================================================= NEWS
section("NEWS & EVENTS PAGE (the items are in content/news.txt)")
news = f'''
    <header class="page-header">
      <div class="container">
        {T("h1", "news.title", "News & Events", "reveal")}
        {T("p", "news.intro", "Seminars, conferences, new publications and life in the lab.", "reveal d1")}
      </div>
    </header>

    <section style="padding-top:40px">
      <div class="container narrow" id="news-list"></div>
    </section>
'''
page("news.html", "news.page_title", "News & Events — TrachLab", "news.page_description", "News and events from TrachLab.", news)

# ================================================================= CONTACTS
section("CONTACTS PAGE (in the address, ' | ' starts a new line)")
contacts = f'''
    <header class="page-header">
      <div class="container">
        {T("span", "contacts.eyebrow", "Contacts", "eyebrow reveal")}
        {T("h1", "contacts.title", "Get in touch", "reveal d1")}
        {T("p", "contacts.intro", "For collaborations, student enquiries or information about our research.", "reveal d2")}
      </div>
    </header>

    <section>
      <div class="container grid-2">
        <div>
          <div class="contact-block reveal"{" hidden" if not val("contacts.email", "").strip() else ""}>
            {T("h3", "contacts.email.title", "Email")}
            {T("p", "contacts.email", "")}
          </div>
          <div class="contact-block reveal d1"{" hidden" if not val("contacts.address", "").strip() else ""}>
            {T("h3", "contacts.address.title", "Address")}
            {T("p", "contacts.address", "")}
          </div>
          <div class="contact-block reveal d2">
            {T("h3", "contacts.join.title", "Join the lab")}
            {T("p", "contacts.join.text", "We are always interested in hearing from motivated students and researchers. Send us a short presentation and your CV.")}
          </div>
        </div>
        {IMG("contacts.photo", "Map or building image", "figure reveal d1", "aspect-ratio:1/1", parallax=False)}
      </div>
    </section>
'''
page("contacts.html", "contacts.page_title", "Contacts — TrachLab", "contacts.page_description", "How to contact TrachLab.", contacts)

# ================================================================= 404
nf = '''
    <section style="min-height:60vh;display:flex;align-items:center">
      <div class="container narrow" style="text-align:center">
        <span class="eyebrow">404</span>
        <h1>Page not found</h1>
        <p>The page you are looking for does not exist.</p>
        <a class="btn" href="index.html">Back to home</a>
      </div>
    </section>
'''
page("404.html", "notfound.page_title", "Page not found — TrachLab", "notfound.page_description", "Page not found.", nf)

# ================================================================= write texts.txt
HEADER = """# ======================================================================
#  HOW TO WRITE IN THIS FILE  (the same rules apply to every file in /content)
#
#  - One field per line:            key: value
#  - An empty line separates two entries.
#  - Lines starting with # are comments and are ignored.
#  - Text formatting, usable in any text:
#        *italic*     **bold**     [label](https://...)     " | " = new line
#  - photo:  file name of a picture uploaded to the folder assets/img/
#            (e.g.  photo: seminar-2026.jpg)
#  - link:   a web address; it makes the title clickable
#  - text:   a paragraph of description
#  - Leave a field empty, or delete the line, if you do not need it.
# ======================================================================
#
#  TEXTS OF THE PAGES — one line per text, grouped by page.
#  Change only the part after the colon; never change the key on the left.
#  An empty text hides that element; keys ending in .photo take a picture.
# ======================================================================
"""
keys = list(REG.keys())
starts = {i: t for i, t in SECTIONS}
lines = [HEADER]
for i, k in enumerate(keys):
    if i in starts:
        lines.append(f"\n# ---------------- {starts[i]}\n")
    lines.append(f"{k}: {SAVED.get(k, REG[k])}\n")
os.makedirs(os.path.dirname(TEXTS), exist_ok=True)
with open(TEXTS, "w", encoding="utf-8") as f:
    f.write("".join(lines))
print("pages written,", len(keys), "texts")
