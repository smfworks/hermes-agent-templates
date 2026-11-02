# When to use

Measuring AI readiness (the AI-crawler dimension) for an owned site — full
audit, re-scan after a fix PR, or a spot check. One URL per run (the homepage
by default); fetches raw server HTML the way AI crawlers do, with no JavaScript
and no browser.

# Run it

```bash
~/SiteSignal/.venv/bin/python3 \
  skills/site-signal/site-signal-ai-readiness/scripts/ai_ready_scan.py \
  https://<domain> --json $RUN/ai.json
```

(stdout: score line, then every issue `[IMPACT] id: message / fix`, then
`PASSES:`; `--json` writes the report `rank.py` merges.)

# Read the output

- `score 0–100` and `grade`: 100 minus deductions — critical 25, serious 10,
  moderate 5, minor 2; A≥90, B≥75, C≥60, D≥40, else F. Full check list with the
  sources: `references/rubric.md` (verbatim from the scanner README).
- `issues[]`: `impact`, `id`, `message`, `fix` — the fix text is the recipe.
- `passes[]`: checks that passed, cited in the report's evidence section.

# Interpretation: training vs search bots

- **Search/user agents** (OAI-SearchBot, ChatGPT-User, Claude-SearchBot,
  Claude-User, PerplexityBot, Perplexity-User, Googlebot, Bingbot) blocked at
  `/` is **critical** — the site cannot be cited or fetched by answer engines.
- **Training bots** (GPTBot, ClaudeBot, Google-Extended, CCBot,
  Applebot-Extended, Meta-ExternalAgent) are **reported, never penalized**.
  Blocking them is a business choice, not a defect. Present the
  `robots-training-policy` pass line as "Training bots blocked: …" and let the
  owner decide; do not "fix" a deliberate block.
- A `bot-challenge` finding on an owned site is a critical finding, not
  something to bypass. `robots.txt` returning 5xx counts as full disallow
  (RFC 9309) and is critical.

# Typical fixes (in impact order)

- Serve 200 `robots.txt` with named AI-bot groups and a `Sitemap:` line — make
  the search-vs-training policy explicit instead of relying on `*`.
- Publish `/sitemap.xml` with `<lastmod>` dates and reference it in robots.txt.
- Add JSON-LD: `Organization` (name, url, logo, `sameAs`), `WebSite`, and
  `WebPage`/content types on detail pages; validate at validator.schema.org.
- Add `/llms.txt` per llmstxt.org: H1 site name, blockquote summary, `##`
  sections of key links (optionally `/llms-full.txt`).
- Add `<link rel="canonical">` on every page.
- Add Open Graph tags (`og:title`, `og:description`, `og:image`, `og:type`,
  `og:url`) and `twitter:card`.
- Wrap primary content in `<main>`; keep exactly one `<h1>`.
- Ensure real content is in the server HTML (SSR/prerender) — agents mostly do
  not execute JS; aim for ≥250 words server-side, TTFB under ~2 s.

# Limits (state when reporting)

One URL per run; cannot see WAF rules that apply only to specific bot user
agents; the 5 s response-time threshold measures one fetch. Scores are Site
Signal rubric scores — no citation or traffic promises, ever.

# Never

- Add or remove bot blocks on the owner's behalf without an explicit ask.
- Invent robots rules, dates, or schema values (publisher is "SMF Works";
  `sameAs` only from owner-confirmed or on-site URLs).
- Bypass a bot challenge, login, or CAPTCHA.
