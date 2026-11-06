---
name: site-signal-getting-started
description: Start a Site Signal conversation, pick a site you own, and run the first ranked scan.
version: 1.0.0
author: SMF Works
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [site-signal, getting-started]
    related_skills: [site-signal-guardrails, site-signal-onboard-site, site-signal-report]
---

# When to use

Start of a conversation, a new site, or "what can you do?". Gets a site from
hello to a first ranked report. Unregistered domains (ownership, repo mapping,
stack detection) go to `site-signal-onboard-site` first; the scan mechanics
live in the three scan skills and `site-signal-report`.

# First-run line

Greet with this line (SPEC.md 3.1):

> Paste a production URL you own and I'll return SEO, GEO, AEO, AI-readiness,
> and accessibility scores ranked by impact, then open fix PRs when you want
> them shipped.

If `~/SiteSignal/sites.yaml` already lists sites, follow it with those sites as
numbered options (Hermes `clarify`), plus "paste a different URL".

# Steps

1. **Greet and pick a site.** One line, then the options above. No questionnaire.
2. **Normalize the URL.** Force https, follow redirects, and record the final
   URL plus the apex and www aliases (both may serve the same site; note which
   one is canonical — e.g. `www.example.com` and the apex may serve the
   same site).
3. **Baseline scan.** Run the full audit (SPEC.md 5.2):
   `site-signal-seo-geo-aeo`, `site-signal-ai-readiness`, and
   `site-signal-axe-scan` (independent — run them in parallel where possible),
   then `site-signal-report` to rank and render. Files land under
   `~/SiteSignal/reports/<domain>/<YYYY-MM-DDTHHMM>/`.
4. **Save and summarize.** Confirm the site is in `~/SiteSignal/sites.yaml`
   (route an unlisted domain through `site-signal-onboard-site` first — until
   verified it is scan-only, no PRs). Send the chat summary: score line, top
   3–6 fixes ranked by impact with evidence, one caveat line, and the question
   "Ship these as PRs?" — under 15 lines.
5. **Offer the weekly re-scan.** After the first report, ask: "Want a weekly
   re-scan of your sites?" The cron job ships PAUSED
   (`site-signal-weekly-rescan`, Mondays 08:00 America/New_York). Enable it
   only on an explicit yes, and say that it reports only on changes and never
   opens or merges PRs.

# Drop questions once real work arrives

The choice card is for the first message only. The moment the owner hands over
something real — a URL, a domain, "scan example.com" — stop asking questions
and scan. (Observed Site Signal behavior: a one-line hello, then it dropped the
questions and ran the scan.)

# Never

- Scan a site the owner does not control beyond a single polite,
  robots-respecting page, and only when explicitly asked.
- Verify ownership, map repos, or edit `sites.yaml` inside this skill — that is
  `site-signal-onboard-site`. An unlisted domain is scan-only.
- Enable the weekly job without a yes, or ever let it open or merge PRs.
- Invent a trend: with no prior entry in `history.jsonl`, say "first scan".
