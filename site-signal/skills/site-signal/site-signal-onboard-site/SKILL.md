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
# a. Seed list + owner confirms in chat (agent records the confirmation itself;
#    the script only checks membership in the Oct-31 observed work list)
scripts/verify_ownership.sh --domain smfwisdomforge.com --method seed+owner
# b. Repo visible to gh, homepage/deploy field points at the domain
GH_BIN=~/.local/share/mise/installs/gh/2.103.3/gh_2.103.3_linux_amd64/bin/gh \
  scripts/verify_ownership.sh --domain example.com --method repo --repo smfworks/smfworks-site
# c. Token file at https://<domain>/.well-known/site-signal.txt
scripts/verify_ownership.sh --domain example.com --method wellknown --token ss-0123456789abcdef
# d. DNS TXT record site-signal-verification=<token>
scripts/verify_ownership.sh --domain example.com --method dns --token ss-0123456789abcdef
# Generate a token for methods c/d:
scripts/verify_ownership.sh --generate-token
```

- (a) The seed list is `smfwisdomforge.com` → `smfworks/wisdomforge`,
  `smfclearinghouse.com` (+ `www.`) → `smfworks/aiclearinghouse-site`,
  `smfworks.com` → `smfworks/smfworks-site`. Seed membership alone is not
  enough: the owner must confirm in chat; the agent records `seed+owner`.
- (b) `GH_BIN` override exists because `~/.local/bin/gh` on this host is a
  broken mise wrapper. The script checks the repo homepage; also glance at the
  repo's Vercel check-run names for the domain.
- (c) Owner places the token file; (d) owner adds the TXT record. Generate the
  token, give exact instructions, and re-run the check when they say done.
- If nothing passes: tell the owner it stays **scan-only** and what to do next.
  Never guess (the Grok Bot guessed `smfworks/smfworks.com` and
  `smfworks/smfwisdomforge`; both failed).

# Step 4 — map the repo

```bash
GH_BIN=<working gh> gh repo list smfworks --limit 200 --json name,homepageUrl
```

Match by homepage URL or name, then **confirm with the owner before saving**.
Record the repo and its default branch. If GitHub cannot see a candidate repo,
tell the owner exactly which repo and scope to grant (fine-grained token:
contents + pull requests read/write, checks read, smfworks site repos only).

# Step 5 — detect stack and deploy host

Read-only clone (or a shallow look): framework from `package.json`
(Next.js app/pages router was the norm for SMF Works sites), test and build
commands, and the deploy host from `vercel.json` or Vercel check-run names
(`deploy: vercel`). Save the test/build commands — `site-signal-ship-fixes`
uses them later.

# Save to the registry

Append to `~/SiteSignal/sites.yaml` (never the profile copy) using this schema:

```yaml
sites:
  - domain: smfwisdomforge.com
    aliases: []
    repo: smfworks/wisdomforge
    default_branch: main
    deploy: vercel            # vercel | other | unknown
    owner_verified: true
    verified_by: seed+owner   # seed+owner | repo | wellknown | dns
    scan:
      pages: 5                # SEO/GEO/AEO sampler
      axe_paths: ["/", "/books", "/about"]   # plus auto-discovered links, max 8
      mobile: false
    merge: ask                # ask | after_green_ci
    notes: "Book pages use Book+BlogPosting dual JSON-LD (PR #27)."
```

Optional keys: `scan_only: true` (no PRs even when verified — smfworks.com
until Michael assigns fix ownership) and `auth: staging` (owned staging
crawl only; credentials from `.env` or an owner-dropped cookie file, never
chat). Copy the schema shape from `sites.yaml.example` in the profile.

# Never

- Set `owner_verified: true` without a passing method above.
- Guess a repo name — confirm with the owner, every time.
- Save the registry anywhere but `~/SiteSignal/sites.yaml`.
- Store tokens, cookies, or the deny-terms list in `sites.yaml` or memory.
- Run a baseline scan before ownership is recorded (scan-only domains may be
  scanned on request; the registry entry still starts `owner_verified: false`).
