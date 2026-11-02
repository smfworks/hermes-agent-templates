# SEO / GEO / AEO rubric

Copied from the Grok Bot scanner README (SPEC.md Appendix A.3). Weights, check
lists, and the overall formula are the scoring source of truth — do not change
them without a version bump.

`python3 scripts/seo_geo_aeo_scan.py https://site.com [--json out.json] [--pages 5]`
(use the Site Signal venv interpreter, `~/SiteSignal/.venv/bin/python3`; deps:
requests, beautifulsoup4)

Crawls the homepage plus up to N-1 key pages (About/Team/Blog/FAQ links from
home + 2 content pages from sitemap: /blog, /learn, /books, /guides, /docs...).
Fetches robots.txt, sitemap.xml, llms.txt. Emits ranked issues
(critical > serious > moderate > minor) and JSON.

## Scoring
Each category starts at 100; each distinct failed check (counted once site-wide)
subtracts critical 25 / serious 12 / moderate 6 / minor 2.
Overall = 0.4·SEO + 0.3·GEO + 0.3·AEO. Grades A≥90 B≥80 C≥70 D≥55 F.

- **SEO**: title presence/length, meta description presence/length, single H1, canonical, noindex, viewport, html lang, Open Graph + twitter:card, image alt, internal links (≥5), thin server-rendered content (<250 words), HTTPS, sitemap, robots, broken key pages, duplicate titles/descriptions.
- **GEO**: Organization/Person entity schema + sameAs, WebSite schema, About/Team page (E-E-A-T), Article-type schema (Article, BlogPosting, NewsArticle, TechArticle, Book, or LearningResource all satisfy `article-schema`) with author + dateModified on content pages, visible byline/date, concrete stats, outbound citations, BreadcrumbList, llms.txt (minor only — low evidence).
- **AEO**: question-style H2/H3s, concise 20–80-word answer directly under questions, definition-style lead paragraph on content pages, FAQ content + FAQPage schema, list/table structure.

## How it differs
- **axe** (`site-signal-axe-scan`): WCAG accessibility in a real browser.
- **ai-ready** (`site-signal-ai-readiness`): crawler access/discovery — AI bot robots policy, llms.txt, sitemap, JSON-LD presence, response time.
- **This**: page-level search quality (SEO), citation/entity/authorship signals (GEO), and answer extractability (AEO). Overlap (sitemap, canonical, llms.txt) is kept at low weight.

## Evidence notes / sources
- Google: optimizing for AI features *is* SEO; no special schema or llms.txt needed; unique, people-first, well-structured, crawlable content — https://developers.google.com/search/docs/fundamentals/ai-optimization-guide , https://developers.google.com/search/docs/appearance/ai-features
- Self-contained paragraphs, specific facts, descriptive headings, clear entity signals — https://searchengineland.com/what-is-generative-engine-optimization-geo-444418
- Query fan-out / cover adjacent dimensions — https://searchengineland.com/google-ai-overviews-everything-you-need-to-know-449399
- Ahrefs (2026): adding JSON-LD alone did not measurably raise AI citations → schema weighted as hygiene, content structure weighted more — https://ahrefs.com/blog/schema-ai-citations/
- GEO paper (Aggarwal et al., KDD 2024): adding statistics, quotations and citations increased generative-engine visibility — https://arxiv.org/abs/2311.09735
- Google FAQ rich results limited to authoritative gov/health sites (2023) — FAQPage still useful for Bing/answer engines, scored minor.

## Historical baselines
The Oct 31, 2026 Grok Bot run reports (report-wisdomforge.json,
report-clearinghouse.json, report-smfworks.json on the Grok Bot box) are not
copied here; the before → after numbers are recorded in SPEC.md Appendix A.5
and are used for regression reference only.
