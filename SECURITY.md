# Security Policy — hermes-agent-templates

Maintained by SMF Works. This document records the repository's security
boundaries, the findings from the 2026-11-16 hermes-security scan
(`scan_aff22f7037c4b51692738c92`, sealed against commit `3dc3e6c`), and the
remediation state for each. Every finding below cites its PR; each PR proves
its fix in the body (adversarial probes, before/after, repo test suites).

## Reporting

Report vulnerabilities to the repository owner. Do not open a public issue
for an exploitable finding.

## Scope

This repository is a collection of agent-operated templates. The threat
model that matters here is not a classic web-app boundary: agent-executed
scripts, template files, and agent-instruction markdown are all part of the
attack surface, because an agent that reads them treats them as
instructions. Content derived from scanned public sites is untrusted input
even when a scanner fetched it.

## Findings and remediation

### HIGH — priority one

**hsf_d74cc4c8444b1592820c348c — scanned-site evidence rendered unescaped into the Grok
Build prompt executed with --always-approve (HIGH, triple-confirmed).**

The chain: axe evidence from scanned public sites → `evidence_lines` →
`fix-brief.md.j2` rendered with autoescape off → the whole brief passed as
grok's prompt with `--always-approve` → `npm test`/`npm run build` execute
the agent's edits in the worktree. A hostile scanned site could plant
instructions that become executed code with no human in between.

Fixed in **PR #12** with three independent controls (any one breaks the
chain; all three applied): evidence/message/fix/where sanitization in
`select_issues`; a structural fence + explicit EVIDENCE-IS-DATA rule in
`fix-brief.md.j2`; and a prompt/task split (`--prompt-file`) with
`--deny`-scoped network and secret-file access. The PR also closes the
adjacent `$RUN_DIR` quoting defect **hsf_2ad6d3bfa810b4aecf3a321f** (low) via the same
`--prompt-file` change. Until #12 merges, do not run the ship-fix pipeline
against untrusted sites.

### Dependency rollup — CRITICAL as scanned, effective exposure MEDIUM

**hsf_cbc22422b355152cbf9a2d8c — dependencies with known vulnerabilities (worst: critical).**
The scanner rates the rollup CRITICAL; after the PR #12 chain fix, the
effective exposure is **MEDIUM** and here is why, per the adjudication:

- **certifi** is the reachable leg: `requests` fetches hostile sites with
  its CA bundle. It was not a direct dependency at all — TLS trust ran on
  whatever transitive certifi pip resolved.
- **jinja2** renders untrusted content, but its reachability is narrow
  (no `SandboxedEnvironment` in this repo, no `attr`/`xmlattr` filters on
  untrusted keys).
- **basic-ftp / extract-zip / zod** are axe-scan transitives, reached only
  through the local fixture workflow.

Fixed in **PR #14**: `certifi>=2026.10.23` added as a direct dependency
(floor verified against PyPI), `Jinja2>=3.1.6`, upper bounds on all runtime
deps, exact pins + `puppeteer-core` 25.18.0 in the axe-scan scripts, and a
regenerated `package-lock.json`. `npm audit --omit=dev` went from 9 high to
0. Going forward this rollup class is covered by the dependency-audit
cadence; the point-in-time closure is this PR.

### Merge-gate integrity — 8 findings, fixed together

**hsf_674eaaffd69edfd9b649edab (medium)** — `merge_gate.sh` treated a failed
required-checks API call as "no required checks" and merged.
**hsf_fbf7f4957fe0e8898b790b13 (informational)** — a repository with zero required checks
merged on approval with a silent vacuous gate.

Both fixed in **PR #15**: the rules/protection fetch now fails closed
(HTTP 404 keeps the legitimate empty-document path; every other failure
aborts with an explicit error), and a zero-required-checks merge is
opt-in via `--allow-no-checks` with the vacuous pass recorded in the
decision. The vacuous-gate refusal is evaluated after the identity gates
so a shared-login attempt is named as itself.

The six `git_guard.sh` bypasses (**hsf_fa8fbb2845b6e8b5417e6e3e, hsf_d12a1dd6cce09f0441ca7c92** —
`--all`/`--mirror` ref-expanding pushes; **hsf_76d114f2ce4feb4a74dbb312, hsf_a56170d477d348d89409804b** —
graphql `mergePullRequest` mutations; **hsf_60388ff53ae885ed700659e5, hsf_8efaed055e67e430df3ab4ca** —
yes-shaped bodies on stdin via `-F -`) are fixed by one hardened control
applied **byte-identically to both `builder-prime` and `gatekeeper-prime`**
in the same PR. The per-refspec classification, force-push confirmation
flow, and pass-through behavior are unchanged; branch protection on GitHub
remains the real lock.

### Mediums — path containment, report injection, SSRF

- **hsf_38898d94f3cb7c58cbf698a1 + hsf_05a2c2e3a8a7152f0b46bb2a** — roast `audit.py`/`card.py` wrote
  outside the data dir when the handle contained path separators. Fixed in
  **PR #16** with one shared `contained_handle()` guard before any write.
- **hsf_9334fec2d31ecd0391257355** — sitemap-derived URLs were fetched without an origin
  allowlist (SSRF pivot from a scanned site). Fixed in **PR #13** with a
  default-deny origin policy (http/https + public-unicast host check) and
  a 3-hop redirect cap re-checked per hop. Tests that serve fixtures on
  loopback opt in explicitly via `SITE_SIGNAL_ALLOW_LOCAL_FETCH=1`; the
  default posture denies loopback and link-local.
- **hsf_45ef67e193f03278e5d9efe0** — scanned-site text rendered unescaped into
  owner-facing markdown reports next to the ship question. Fixed in
  **PR #13** with the `_md_safe` filter (fence-run neutralization,
  leading-structure stripping, pipe escaping) on every untrusted field.
- **hsf_21dab6ace272ffd829ae6427** — template HTML slots are filled by the
  model agent via the file tool; the escaping rule is instruction-level.
  Accepted as designed: the html env autoescapes at render time, and the
  agent-editing-templates flow is the product. The instruction layer is
  documented in the template skills rather than converted to code.
- **hsf_c1ee8922dadcb41c8b8e8a3e + hsf_01f59bcfb3eaf846a645498a** — receipts `draft.py` `--service` as an
  unvalidated filename (traversal) and interpolated raw into `.eml`
  headers (CRLF injection). Both fixed in **PR #17** as distinct
  mechanisms: `safe_service()` containment with an `unknown-service`
  fallback, and an RFC 5322 `EmailMessage` build that structurally cannot
  fold a header.

### Lows and informational

- **hsf_01f59bcfb3eaf846a645498a** (low) — covered by PR #17 above.
- **hsf_2ad6d3bfa810b4aecf3a321f** (low) — shell path interpolated into a `python -c`
  source string; closed by the `--prompt-file` change in PR #12.
- **hsf_ba7e3355b7d24eeaeca38b06** (low) — price-watch alert bodies carried untrusted
  link/notes/source text into the owner-facing message. Fixed in **PR
  #18**: an https + fixture-domain link allowlist at the fixture boundary
  (rejected links are flagged, not dropped) and alert provenance with an
  unverified marker, a verify-before-booking caveat, and a
  `[notes — data, not instructions]` marker. Links never render inside a
  `Fare Hawk:`-prefixed trusted sentence.
- **hsf_de72f2f0aacea05a928db970** (informational) — the weekly cron executes `npm ci`
  against the network and the pinned tree carried known vulnerabilities.
  The vulnerability half is closed by PR #14; the network-execution half
  is accepted as designed (the cron's purpose), with the lockfile now
  regenerated on every dependency change so the tree stays audited.

## Standing boundaries (unchanged by this scan)

- Agents never push, never merge, and never post a yes. The owner types
  their own yes on the PR; the merge account is a different GitHub login
  from the owner.
- `git_guard.sh` runs on both profiles; branch protection is the real
  lock.
- The product keeps card data out of the agent's hands: agents report,
  owners book.
- Scanned-site content is data. Evidence blocks are fenced and labeled;
  agents treat them as strings to verify, never instructions.

## Verification cadence

- Dependency audit (npm audit --omit=dev, pip index) on every lockfile
  change and at least weekly — this covers the hsf_cbc22422b355152cbf9a2d8c rollup class.
- Re-run the adversarial probes from PRs #12-#18 after any change to
  `ship_fix.sh`, `render_report.py`, `polite_get`, `git_guard.sh`,
  `merge_gate.sh`, `draft.py`, or the alert body path. A merged PR is not
  a closed finding until the probe answers differently.
