# How to edit the website

All the content of the site lives in this folder. Open a file, click the **pencil icon** (Edit), change it, then click **Commit changes**. The site updates by itself in about a minute.

| File | What it controls |
|---|---|
| `texts.txt` | every text on the pages (titles, paragraphs, buttons, menu, contacts) and their pictures |
| `team.txt` | team members |
| `news.txt` | news and events |
| `publications.txt` | publications (by DOI) |
| `collaborations.txt` | partner institutions |

## The same rules in every file

```
key: value          one field per line
                    an empty line separates two entries
# comment           lines starting with # are ignored
```

**Text formatting** (works in any text):

| You write | You get |
|---|---|
| `*word*` | *italic* |
| `**word**` | **bold** |
| `[label](https://...)` | a link |
| ` \| ` (space, bar, space) | a new line |

**Fields with the same meaning everywhere:**

- `photo:` the file name of a picture. Upload the picture to the folder **`assets/img/`** (Add file → Upload files), then write only its name, e.g. `photo: seminar-2026.jpg`. Use names without spaces or accents.
- `link:` a web address; it makes the title (or name) clickable.
- `text:` a paragraph of description.

Leave a field empty, or delete the line, if you do not need it. Each file starts with the list of fields it accepts and ends with a complete example to copy.

## Examples

Add a news item with a picture (`news.txt`):

```
date: 2026-11-20
type: Seminar
title: White matter anatomy seminar
text: Seminar at **IRCCS Neuromed**, Pozzilli.
photo: seminar-2026.jpg
link: https://example.org
```

Add a team member (`team.txt`):

```
name: Jane Doe
role: PhD Student
photo: jane-doe.jpg
text: Jane studies the *frontal aslant tract*.
links: [ORCID](https://orcid.org/0000-0000-0000-0000)
```

Add a publication (`publications.txt`): just `doi: 10.xxxx/xxxxx`. Optional fields (`title`, `authors`, `journal`, `year`, `topic`, `text`, `photo`, `link`) complete or correct what is filled in automatically.

Change a text on a page (`texts.txt`): change only what comes after the colon, e.g.
`home.title: Mapping the *connections* of the human brain`
