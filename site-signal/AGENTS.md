# AGENTS.md — rules for building this repo (dev only)

This directory is the `site-signal` Hermes profile. `SPEC.md` is the public
contract. The skill files are the operating rules.

## Working rules

1. Read `SPEC.md` before changing scanner weights, the ownership gate, or the
   merge gate. Do not change scoring weights or check lists without a version
   bump.
2. ARM64 and x86_64 Linux friendly: pure Python and Node, no platform-specific
   binaries. Chromium comes from `CHROME_PATH`. Never hardcode a browser path.
   `gh` is the GitHub CLI on `PATH`. `GH_BIN` is an optional override.
3. No secrets in any committed file. Only `.env.EXAMPLE` exists, with variable
   names only.
4. Git and GitHub safety: never push to a default branch, never force-push, and
   never merge without an approval that names the repo and PR, or a
   `merge_consent` block the owner wrote by hand. Draft PRs stay the default.
   The agent does not write `merge: after_green_ci` or `merge_consent`.
5. Brand is SMF Works. Never name or hint at an operator's employer anywhere:
   code, comments, schema, PR text, reports, or chat drafts. Before finishing,
   if a private deny-terms file is configured, scan with it and fix every hit.
   Never print that file or quote its terms.
6. The public example registry uses `example.com` and `owner_verified: false`.
   Do not add a seed list of real domains to `verify_ownership.sh`.
7. Site Signal data lives in `~/SiteSignal/` (created at runtime) and is never
   committed here.
8. Leave the tree clean: no `__pycache__`, no `.pyc`, no hostnames, local
   usernames, or home-directory paths.
