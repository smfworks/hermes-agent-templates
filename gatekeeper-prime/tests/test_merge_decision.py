#!/usr/bin/env python3
import importlib.util
from pathlib import Path
root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("merge_decision", root / "lib" / "merge_decision.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
SHA = "a" * 40
OLD = "b" * 40

def view(reviews, head=SHA):
    return {"headRefOid": head, "reviewDecision": "APPROVED", "reviews": reviews}

ok, why = mod.owner_approved(view([
    {"author": {"login": "octocat"}, "state": "APPROVED", "commit": {"oid": SHA}}
]), "octocat")
assert ok, why

ok, why = mod.owner_approved(view([
    {"author": {"login": "some-bot"}, "state": "APPROVED", "commit": {"oid": SHA}}
]), "octocat")
assert not ok, why

ok, why = mod.owner_approved(view([
    {"author": {"login": "octocat"}, "state": "APPROVED", "commit": {"oid": OLD}}
]), "octocat")
assert not ok and "current head" in why

ok, why = mod.owner_approved({"headRefOid": SHA, "reviews": [], "reviewDecision": "APPROVED"}, "octocat")
assert not ok

ok, why = mod.owner_approved(view([
    {"author": {"login": "octocat"}, "state": "COMMENTED", "commit": {"oid": SHA}}
]), "octocat")
assert not ok

# Stale approve: the owner's LATEST review on the head wins. An APPROVED
# followed by CHANGES_REQUESTED from the same login must not merge.
ok, why = mod.owner_approved(view([
    {"author": {"login": "octocat"}, "state": "APPROVED", "commit": {"oid": SHA}},
    {"author": {"login": "octocat"}, "state": "CHANGES_REQUESTED", "commit": {"oid": SHA}},
]), "octocat")
assert not ok, "a later changes-requested must override a stale approve"

# Changes, then a fresh approve on the head: mergeable.
ok, why = mod.owner_approved(view([
    {"author": {"login": "octocat"}, "state": "CHANGES_REQUESTED", "commit": {"oid": OLD}},
    {"author": {"login": "octocat"}, "state": "APPROVED", "commit": {"oid": SHA}},
]), "octocat")
assert ok, why

# A merged or closed PR is not mergeable, whatever the reviews say.
ok, why = mod.owner_approved({
    "state": "MERGED", "headRefOid": SHA, "reviewDecision": "APPROVED",
    "reviews": [{"author": {"login": "octocat"}, "state": "APPROVED", "commit": {"oid": SHA}}],
}, "octocat")
assert not ok and "not open" in why
print("merge_decision: PASS")
