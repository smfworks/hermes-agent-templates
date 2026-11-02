# When to use

Measuring SEO, GEO, and AEO (the page-quality dimensions) for an owned site —
full audit, re-scan after a fix PR, or a spot check. Crawls the homepage plus
up to N−1 key pages (About/Team/Blog/FAQ links from home + 2 content pages from
the sitemap), respecting the crawl etiquette in `site-signal-guardrails`.

# Run it

```bash
~/SiteSignal/.venv/bin/python3 \
  skills/site-signal/site-signal-seo-geo-aeo/scripts/seo_geo_aeo_scan.py \
  https://<domain> --json $RUN/seo.json --pages 5
```

(stdout: page count, then `SEO / GEO / AEO / overall` scores with grades, then
every issue; `--json` writes the report `rank.py` merges.)

# Read the output

- Each category starts at 100; each distinct failed check (counted once
  site-wide) subtracts critical 25, serious 12, moderate 6, minor 2.
  Overall = 0.4·SEO + 0.3·GEO + 0.3·AEO. Grades A≥90, B≥80, C≥70, D≥55, else F.
- Full check lists and sources: `references/rubric.md` (verbatim from the
  scanner README). `issues[]` carry `category`, `impact`, `id`, `message`,
  `fix`, `page`.

# Article-family types

All of these satisfy the `article-schema` check on content pages (the Oct 31
scanner fix added Book and LearningResource): **Article, BlogPosting,
NewsArticle, TechArticle, Book, LearningResource**. Content pages are URLs
under `/blog|posts|articles|news|insights|learn|books|guides|docs/…`. An
article node also needs `author` (Person with name + url) or it fails
`article-author`, and `dateModified` or it fails `date-modified`.

# Typical fixes (per the Oct 31 fix plans, A.4 style)

- Emit **BlogPosting/Book JSON-LD** on content pages: headline, description,
  image, author `Person{name, url}`, `datePublished`, `dateModified`,
  publisher `Organization "SMF Works"`, `mainEntityOfPage`. Books get `Book`
  (or Book + BlogPosting dual) JSON-LD; learn/guide pages get
  LearningResource/BlogPosting. Add **BreadcrumbList** (Home > Section > page).
- **FAQPage JSON-LD only mirroring visible Q&A** with 40–60-word answers under
  each question heading. Never emit FAQ schema without the visible content.
- **sameAs** on the Organization entity (GitHub, LinkedIn, X) — only URLs the
  owner confirmed or that already appear on the site.
- **Related posts** (3–4 from the same series/tags) + a link back to the index
  to fix `internal-links`.
- **og:image** with a real default image via metadata (e.g. Next.js
  `metadata.openGraph.images`) on pages missing it.
- **Titles 30–60 chars**, **meta descriptions ≤160 chars** (unique per page),
  **single H1**, and a 1–2-sentence **lead summary** that restates what the
  page already says.
- `visible-byline`: show the author name (linked to a bio) and an
  "Updated <time>" date.

# The never-invent rule

Never add statistics, quotes, citations, authors, publish dates, or `sameAs`
profiles to satisfy `facts-stats` or `outbound-citations`. Missing facts are
**content suggestions for the owner**, listed as such in the report and fix
brief. Every fix brief and PR body restates this constraint; the review step
greps the diff for new numerals and new external URLs and lists them.

# Limits (state when reporting)

Samples ~5 pages by default (hard cap 25) — page-level, not site-wide truth.
`facts-stats` and `lead-summary` are heuristics and can false-positive; when
the HTML shows the content exists, call it "scanner heuristic". Scores are Site
Signal rubric scores — no ranking or traffic promises.

# Never

- Fetch a non-owned site beyond a single polite page on explicit request.
- Invent facts (see above) or fabricate a fix without evidence (rule id, URL,
  page).
- Change scanner weights or check lists without a version bump.
