# Examples

Q7 shows `ruleset.json`, fills in the real check names from a recent pull request, and creates nothing without an explicit yes.

`required_approving_review_count` is 0 on purpose. The owner's yes is a pull request comment that names the live head SHA, not a GitHub review. `bypass_actors` is empty.

Private repos need a paid plan for rulesets.

`PULL_REQUEST_TEMPLATE.md` copies to `.github/PULL_REQUEST_TEMPLATE.md` in the guarded repo.
