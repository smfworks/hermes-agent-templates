# AI-readiness rubric

Copied from the Grok Bot scanner README (SPEC.md Appendix A.2). Weights and
check lists are the scoring source of truth — do not change them without a
version bump.

Checks how well one URL can be found, read and cited by AI crawlers and agents.
It does not test human (WCAG) accessibility; use the `site-signal-axe-scan`
skill for that.

Run: `python3 scripts/ai_ready_scan.py https://example.com [--json out.json]`
(use the Site Signal venv interpreter, `~/SiteSignal/.venv/bin/python3`, which
has requests and bs4). It does not use a browser: it fetches the raw HTML the
way AI crawlers do, without running JavaScript.

## Rubric (score = 100 - critical 25 / serious 10 / moderate 5 / minor 2; A>=90 B>=75 C>=60 D>=40 F)
- critical: page fails to load for a non-browser agent or hits a bot challenge; robots.txt returns 5xx (RFC 9309 treats that as full disallow); AI search or user agents blocked at / (OAI-SearchBot, ChatGPT-User, Claude-SearchBot, Claude-User, PerplexityBot, Googlebot, Bingbot); fewer than 80 words in the server HTML (content is JS-only); meta robots noindex
- serious: HTML takes over 5s; X-Robots-Tag noindex/noai; no XML sitemap; no JSON-LD or JSON-LD that won't parse; missing title or meta description
- moderate: no robots.txt; no /llms.txt; no canonical link; missing Open Graph tags; not exactly one h1; no <main>; images with no alt; links with no real href; thin server HTML (80–249 words)
- minor: no named AI-bot groups in robots.txt; sitemap has no lastmod; llms.txt format problems or no llms-full.txt; no html lang; no twitter:card; JSON-LD has no Organization/Person/WebSite entity; heading levels skip; no modified date; no RSS/Atom feed

Training bots (GPTBot, ClaudeBot, Google-Extended, CCBot, Applebot-Extended,
Meta-ExternalAgent) are reported but not penalized, because blocking them is a
business choice.

## Sources
- OpenAI crawlers: https://developers.openai.com/api/docs/bots (search and training bots are controlled separately)
- RFC 9309 / AI crawler guide: https://attensira.com/guides/ai-crawler-guide
- Ahrefs, AI technical SEO: https://ahrefs.com/academy/aeo-course/lesson-3-4 (SSR; llms.txt is little-read)
- Semrush, preparing for AI agents: https://www.semrush.com/blog/how-to-prepare-your-site-for-ai-agents/
- llms.txt spec: https://llmstxt.org
- Decision matrix: https://www.digitalapplied.com/blog/ai-crawler-access-control-2026-robots-llms-txt-decision-matrix

Limits: checks one page per run; does not see WAF rules that apply only to
specific bot user agents.
