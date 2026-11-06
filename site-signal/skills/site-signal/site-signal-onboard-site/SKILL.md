---
name: site-signal-onboard-site
description: Verify that you control a domain before Site Signal will open fix pull requests for it.
version: 1.0.0
author: SMF Works
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [site-signal, ownership]
    related_skills: [site-signal-guardrails, site-signal-getting-started]
---

# When to use

A domain that is not in `~/SiteSignal/sites.yaml`, or one whose ownership or
repo mapping is unconfirmed. Produces a verified registry entry. Until this
succeeds the site is **scan-only** — `site-signal-ship-fixes` refuses it.
This skill covers SPEC.md 5.1 steps 3–5; the greeting, baseline scan, and
summary live in `site-signal-getting-started`.

# Step 3 — verify ownership

Use the first method that passes, and record which one in `sites.yaml`
(`verified_by`). Run the mechanical checks with `scripts/verify_ownership.sh`
(exit 0 = verified, 1 = not verified, fail closed):

```bash
# The public script has an empty seed list. seed+owner never verifies a domain.
scripts/verify_ownership.sh --domain example.com --method seed+owner
# Repo visible to gh whose homepage points at the domain
scripts/verify_ownership.sh --domain example.com --method repo --repo OWNER/REPO
# Token file at https://<domain>/.well-known/site-signal.txt
scripts/verify_ownership.sh --domain example.com --method wellknown --token ss-0123456789abcdef
# DNS TXT record site-signal-verification=<token>
scripts/verify_ownership.sh --domain example.com --method dns --token ss-0123456789abcdef
# Generate a token for the file or DNS methods:
scripts/verify_ownership.sh --generate-token
```

- `seed+owner` exits 1 for every domain. Do not treat any site as pre-owned.
- `repo` checks that the repo homepage points at the domain. `gh` comes from
  PATH unless `GH_BIN` is set. Also glance at the repo's deploy check-run
  names when the owner says the site is deployed from that repo.
- The owner places the token file, or adds the TXT record. Generate the token,
  give exact instructions, and re-run the check when they say done.
- A passing `repo`, `wellknown`, or `dns` check is not enough by itself. The
  owner must confirm that domain in chat before you write `owner_verified: true`.
- If nothing passes: tell the owner it stays **scan-only** and what to do next.
  Never guess a repo name.

# Step 4 — map the repo

```bash
gh repo list OWNER --limit 200 --json name,homepageUrl
```

Match by homepage URL or name, then **confirm with the owner before saving**.
Record the repo and its default branch. If GitHub cannot see a candidate repo,
tell the owner exactly which repo and scope to grant (fine-grained token:
contents + pull requests read/write, checks read, on the repos they name).

# Step 5 — detect stack and deploy host

Read-only clone (or a shallow look): framework from `package.json`, test and
build commands, and the deploy host from `vercel.json` or deploy check-run
names (`deploy: vercel` when that is what you see). Save the test/build
commands — `site-signal-ship-fixes` uses them later.

# Save to the registry

Append to `~/SiteSignal/sites.yaml` (never the profile copy) using this schema:

```yaml
sites:
  - domain: example.com
    aliases: []
    repo: OWNER/REPO
    default_branch: main
    deploy: unknown           # vercel | other | unknown
    owner_verified: false
    verified_by: ""           # repo | wellknown | dns, after the owner confirms
    scan:
      pages: 5
      axe_paths: ["/"]
      mobile: false
    merge: ask                # ask, unless the owner hand-edits merge_consent
    notes: ""
```

Start every new site at `owner_verified: false` and `merge: ask`. Set
`owner_verified: true` only after a passing method and the owner's confirmation.
Optional keys: `scan_only: true` (no PRs even when verified) and `auth: staging`
(owned staging crawl only; credentials from `.env` or an owner-dropped cookie
file, never chat). Copy the schema shape from `sites.yaml.example`.

Do not write `merge: after_green_ci` or `merge_consent`. If the owner wants
standing auto-merge, show them the `merge_consent` block in `sites.yaml.example`
and let them edit `~/SiteSignal/sites.yaml` themselves. The phrase must be
`always merge green PRs for <domain>`, with `set_by` and `set_at`.

# Never

- Set `owner_verified: true` without a passing `repo`, `wellknown`, or `dns` check plus the owner's confirmation of that domain.
- Write `merge: after_green_ci` or `merge_consent`. The owner edits those by hand.
- Guess a repo name — confirm with the owner, every time.
- Save the registry anywhere but `~/SiteSignal/sites.yaml`.
- Store tokens, cookies, or the deny-terms list in `sites.yaml` or memory.
- Run a baseline scan before ownership is recorded (scan-only domains may be
  scanned on request; the registry entry still starts `owner_verified: false`).
