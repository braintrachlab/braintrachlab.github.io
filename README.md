# TrachLab website

Website of TrachLab, published with GitHub Pages at https://trachlab.github.io

## Structure
- `index.html` — Home
- `about.html` — About us (mission, approach, team, collaborations)
- `research.html` — Research areas
- `publications.html` — Publications (filterable by topic)
- `news.html` — News & Events
- `contacts.html` — Contacts
- `assets/css/style.css` — styles
- `assets/js/main.js` — scroll animations, menu, publication filters
- `assets/img/` — images

Text highlighted in yellow inside square brackets is placeholder content to replace.

## Home animation
- Home hero: animated Dejerine plate (`assets/img/dejerine-lines.svg`), also on the Research page.
- `assets/img/white-matter.svg` — stylised tract diagram (previous home animation, kept in reserve).
- Archived: `hero-lab.html` + `assets/js/hero.js` + `assets/hero/` — tractography with the 3D arterial tree (ICA) growing from the carotid. Not linked.

## Publications
Edit the DOI list in the generator; titles, authors and journals are loaded from Crossref in the visitor's browser.

## History of neuroscience figure
- `assets/img/dejerine-lines.svg` + `assets/img/dejerine-1895.png` — coronal section from Dejerine's *Anatomie des centres nerveux* (drawing by H. Gillet), with the white matter redrawn as animated streamlines. Shown on the Research page.

## Editing content without touching code
Everything is in the `content/` folder, which has its own guide: see `content/README.md`.
Pictures go in `assets/img/` and are referenced by file name with `photo:`.

## For developers
`tools/build_site.py` regenerates the HTML pages from its templates and keeps the values already in `content/texts.txt`.
Run `python3 tools/build_site.py` from the repository root after changing the layout.
