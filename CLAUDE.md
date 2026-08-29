# CLAUDE.md

Context for Claude Code working in this repository.

## What this is

Personal portfolio site for Jacob Ufkes, served by GitHub Pages at
https://ufkesjp.github.io.

**Audience: recruiters and hiring managers.** Target role is **BI Architect**
(also open to Data Engineer / Data Scientist). Every change should be judged
against one question: does this make a hiring manager more likely to reach out?

Static HTML and CSS. **No build step, no framework, no bundler.** Jekyll is
nominally configured (`_config.yml`, `jekyll-theme-modernist`) but the site is
hand-written HTML that bypasses the theme. Do not introduce a build pipeline,
npm dependencies, or a static site generator without asking.

## Layout

| Path | Contents |
| --- | --- |
| `index.html` | Landing page, section cards |
| `projects/index.html` | Project index |
| `minimize_freight_miles/index.html` | Freight optimization writeup (see warning below) |
| `blog/index.html` | Post index |
| `blog/take_it_personally/` | Published post |
| `games/`, `utilities/` | Prototypes and small tools |
| `css/style.css` | Single shared stylesheet for the whole site |
| `images/` | Card thumbnails |
| `404.html` | Root 404 page |

## Design system — preserve this

Deliberate neubrutalist style. It is distinctive and it is an asset. Do not
replace it with a generic template look, and do not add a CSS framework.

Tokens live in `:root` in `css/style.css`:

```
--bg:        #f4ede0   (warm paper background)
--ink:       #0a0a0a   (near-black, borders and text)
--paper:     #ffffff   (card surfaces)
--accent:    #ffd60a   (yellow, hover and emphasis)
--bord:      3px solid #0a0a0a
--shadow:    6px 6px 0 #0a0a0a
--shadow-sm: 4px 4px 0 #0a0a0a
--shadow-xs: 3px 3px 0 #0a0a0a
```

- Fonts: **Space Grotesk** for body, **JetBrains Mono** for headers, nav, and labels.
- `border-radius: 0 !important` is set globally in the reset. Square corners
  are intentional. Do not add rounded corners.
- Hard offset shadows, no blur. Hover state shrinks the shadow and shifts the
  element to simulate a press.
- Always use the CSS variables. Do not hard-code these hex values inline.

## Conventions

- Cards are `<a class="project-card" href="...">` anchors — **never** `<div>`
  with a JS click handler. They must be keyboard focusable, middle-clickable,
  and crawlable. `.project-card` resets `text-decoration` and `color`, and
  defines a `:focus-visible` outline. Preserve both.
- Every page needs: `<title>`, `meta description`, `link rel=canonical`,
  Open Graph tags, and Twitter card tags.
- Footer on every page:
  `© 2026 Jacob Ufkes` plus LinkedIn and GitHub links.
  LinkedIn: https://www.linkedin.com/in/jacob-ufkes-75592bba/
  GitHub: https://github.com/ufkesjp
  Keep the year consistent sitewide.
- Do **not** add "Built with AI assistance" disclaimers. They were deliberately
  removed; they undercut engineering credibility on a portfolio.
- Do **not** add placeholder or "coming soon" cards. Empty scaffolding reads as
  abandonment. Ship finished items only.
- Image paths in subdirectories must be absolute (`/images/...` or the full
  URL). Relative `images/...` breaks from `games/` and `blog/`.

## Image rules

Thumbnails render in roughly 260×180 cards. Cap them at **800px on the long
edge, JPEG quality ~82, progressive**. Target under 100KB each.

These were previously committed as full-resolution camera originals totalling
65MB, which made the site effectively unusable on mobile. Never commit an
unresized image.

## Warning: minimize_freight_miles/index.html

592KB raw `nbconvert` Jupyter export. Do not attempt line edits or
search-and-replace across the whole file without a plan. It is slated to be
replaced by a hand-written case study page that keeps the charts and drops the
notebook chrome.

## Verify before committing

```bash
python3 -m http.server 8000    # then click through every page
grep -rn "YOUR_\|Pending Upload\|Placeholder\|TODO" --include=*.html .
du -sh images/                  # should stay well under 1MB
```

Check that no page has a bare `<title>index</title>`, that all internal links
resolve, and that card anchors are balanced.
