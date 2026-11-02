# When to use

Measuring accessibility (the axe dimension) for an owned site — full audit,
re-scan after a fix PR, or a single-page spot check. axe-core 4.14 in real
headless Chromium (puppeteer-core), desktop 1280×900, `networkidle2` + 2 s
settle, violations only.

# Run it

```bash
node skills/site-signal/site-signal-axe-scan/scripts/axe_scan.js \
  --json $RUN/axe.json \
  https://<domain>/ /about /books
```

- URLs/paths: the homepage, the site's configured `axe_paths` from
  `sites.yaml`, and up to 8 same-origin links found on the homepage (the
  scanner prints them as `LINKS`). Keep the total ≤25 pages per run.
- `--json $RUN/axe.json` writes the machine report that `rank.py` merges; the
  human summary still prints to stdout either way.
- Chromium: set `CHROME_PATH` to a Chromium binary (Playwright's bundled
  Chromium is autodetected, e.g.
  `~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome`, or the distro
  `/usr/bin/chromium`). Never hardcode `/usr/bin/google-chrome`.
- Mobile pass (optional, off by default): a second run with a 390×844 viewport
  is not built into the script; if asked, note it as an extra manual run and
  keep its counts separate from the desktop baseline.
- Needs the `site-signal-axe-scan/scripts/node_modules` (axe-core +
  puppeteer-core, pinned in `package.json` / `package-lock.json`).

# Read the output

Stdout per URL:

```
### https://<domain>/ -> https://<domain>/          (final URL after redirects)
{"critical":0,"serious":16,"moderate":1,"minor":0}  (violation NODE counts by impact)
- serious color-contrast (16): Elements must have sufficient color contrast
   #main > p.intro | <p class="intro text-faint">… | Fix any of the following:
     Element has insufficient contrast ratio of 4.46:1 (foreground #8a7a68 …)
LINKS /about /books /lab …                          (up to 8 same-origin links)
```

The JSON array has one object per URL: `url`, `counts{critical,serious,
moderate,minor}`, and `violations[]` — each with `id`, `impact`, `help`,
`description`, `nodeCount`, and up to 3 `nodes` with `target` (selector), `html`
snippet (first 120 chars), and `failureSummary`. Node counts, not violation
counts, are the impact numbers — one rule failing on 169 nodes is one line with
reach 169. There is no composite a11y score; report counts by impact
(`site-signal-report` handles the ranking).

# Turn the top violations into fixes

- **color-contrast** (the usual serious offender): compute the failing pair's
  current ratio from the snippet (e.g. `.text-faint` 4.46:1 on `#13131a` needs
  ≥4.5:1). Fix the color **token** in one place (raise lightness until the
  ratio clears 4.5:1 normal text, 3:1 large text/UI), never ad-hoc hex per
  component. Re-run axe on one fixed page before shipping the PR.
- **select-name / button-name / link-name / image-alt**: wire the accessible
  name — `<label htmlFor>` tied to the control, or `aria-label` when no visible
  label exists; add `alt` to images (empty `alt=""` only for decorative).
- **heading-order / page-has-heading-one**: keep h1→h2→h3 without skips and
  exactly one h1 per page.
- **region / landmark-no-duplicate-banner / -contentinfo**: wrap primary
  content in `<main>`; exactly one `<header>`-as-banner and one
  `<footer>`-as-contentinfo per page.
- **link-in-text-block**: links inside paragraphs need a non-color cue —
  underline them (and keep the color change).
- **duplicate-id-aria / aria-* **: deduplicate ids; make referenced ids exist.

Group fixes by mechanism (one token, one component, one utility class) — one
PR per repo per pass, with the ranked evidence in the fix brief.

# Manual-pass caveat (always say it)

axe catches only the automatable subset of WCAG. Keyboard traps, focus order,
screen-reader announcement quality, and cognitive-load issues need a manual
keyboard + screen-reader pass — say so in every report and PR body, and never
claim or imply conformance from a clean axe run.

# Never

- Scan non-owned sites beyond a single polite page on explicit request.
- Invent an accessibility score, or mix axe counts into the 0–100 dimensions.
- Report a rule's fix without citing the rule id, URL, and a selector/snippet.
- Loosen or skip a rule to make a report look better — a suspected axe false
  positive is verified and proposed as a scanner version bump (5.4 step 9).
