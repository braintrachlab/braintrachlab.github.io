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
Edit these text files directly on GitHub (open the file → pencil icon → "Commit changes"):
- `content/team.txt` — team members (photos go in `assets/img/team/`)
- `content/publications.txt` — one DOI per line
- `content/news.txt` — news and events
The site updates by itself about a minute after each commit.
