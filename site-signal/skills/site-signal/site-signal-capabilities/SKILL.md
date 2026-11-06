---
name: site-signal-capabilities
description: Explain what Site Signal scans and how SEO, GEO, AEO, AI-readiness, and accessibility scores work.
version: 1.0.0
author: SMF Works
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [site-signal, scoring]
    related_skills: [site-signal-guardrails, site-signal-report]
---

# When to use

When the owner asks what Site Signal scans, how scoring works, or what the
scores mean. Also the reference for interpreting any number in a report.

# The five dimensions

1. **SEO** — page-level search quality: titles, meta descriptions, one H1,
   canonical, viewport, Open Graph, image alt, internal links, server-rendered
   content, HTTPS, sitemap, robots, broken key pages, duplicates.
2. **GEO** (generative-engine optimization) — citation and entity signals:
   Organization/Person entity schema with `sameAs`, WebSite schema, About/Team
   page, Article-family JSON-LD with author and dates on content pages, visible
   byline, concrete stats, outbound citations, breadcrumbs.
3. **AEO** (answer-engine optimization) — answer extractability: question-style
   headings, a concise 20–80-word answer directly under each, definition-style
   lead paragraphs, FAQ content + FAQPage schema, list/table structure.
4. **AI readiness** — whether crawlers and agents can fetch and read the site:
   robots.txt rules for AI bots, bot challenges, server-HTML word count, sitemap
   + lastmod, llms.txt, JSON-LD entity, canonical, response time.
5. **Accessibility (axe)** — automatable WCAG checks via axe-core 4.14 in real
   headless Chromium, desktop 1280×900: contrast, names/labels, headings,
   landmarks, and the rest of axe's rule set.

# Scoring rubrics (SPEC.md 5.2 — do not restate from memory)

- **AI readiness**: score = 100 − Σ deductions; critical 25 / serious 10 /
  moderate 5 / minor 2. Grades A≥90, B≥75, C≥60, D≥40, else F. Full check list:
  `site-signal-ai-readiness/references/rubric.md`.
- **SEO / GEO / AEO**: each category starts at 100; each distinct failed check
  (counted once site-wide) subtracts critical 25 / serious 12 / moderate 6 /
  minor 2. Overall = 0.4·SEO + 0.3·GEO + 0.3·AEO. Grades A≥90, B≥80, C≥70,
  D≥55, else F. Full check lists:
  `site-signal-seo-geo-aeo/references/rubric.md`.
- **Accessibility**: no composite score, ever. Report axe node counts by impact
  (critical/serious/moderate/minor) per URL, and rules ranked worst first. If a
  numeric a11y score is ever wanted, version it (`a11y-score/1`) and keep it out
  of parity comparisons — never mix it into these scores.

# Limits (say these before the owner asks)

- Desktop viewport (1280×900), sampled pages only — the SEO/GEO/AEO sampler
  takes 5 pages by default, axe adds same-origin links up to 8; never a
  full-site crawl (≤25 pages per run).
- AI readiness fetches raw server HTML, no JavaScript, one URL per run.
- axe covers only the automatable subset of WCAG — it misses keyboard flow and
  screen-reader experience. Always say a manual pass is still needed.
- AI readiness cannot see WAF rules that apply only to specific bot user
  agents. A bot challenge on an owned site is a finding, not something to
  bypass.
- `facts-stats` and `lead-summary` are heuristics and can false-positive. When
  the HTML shows the content exists, report it as "scanner heuristic".
- Scores are Site Signal rubric scores — never call them Google rankings,
  traffic predictions, or WCAG conformance.

# What Site Signal never does

- Audit sites the owner does not control (one polite, robots-respecting page
  when explicitly asked is the ceiling), penetration or security testing, load
  testing, link-building or outreach, or writing new long-form content.
- Promise rankings, AI citations, traffic, or WCAG conformance.
- Invent statistics, quotes, citations, authors, dates, or `sameAs` profiles —
  missing facts become content suggestions for the owner.
- Push to a default branch, force-push, or merge a PR without the owner's go
  (or a `merge_consent` block the owner wrote by hand that names that site).
- Name anyone but SMF Works as the brand, in schema publishers, PRs, reports,
  or commits.

# Tool map (one screen, for orientation)

- Scanners: `site-signal-axe-scan` (Node + axe-core + Chromium),
  `site-signal-ai-readiness` and `site-signal-seo-geo-aeo` (Python + requests +
  bs4, via `~/SiteSignal/.venv`).
- Rank + report: `site-signal-report` (`rank.py`, `render_report.py`).
- Shipping: `site-signal-ship-fixes` (git worktree → Grok Build headless →
  tests → deny-terms check → draft PR → merge on approval → deploy wait →
  re-scan).
- Registry: `site-signal-onboard-site` + `~/SiteSignal/sites.yaml`.
