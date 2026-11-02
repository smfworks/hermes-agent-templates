#!/usr/bin/env python3
"""Offline tests for the owner-yes-comment gate (lib/merge_decision.py).

Plain asserts run directly — no unittest classes, so `python3 tests/
test_merge_decision.py` prints one line on success and raises on the
first broken promise.
"""
import importlib.util
import os
from pathlib import Path

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("merge_decision", root / "lib" / "merge_decision.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

SHA = "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b"  # this PR's head
OLD = "0f9e8d7c6b5a4f3e2d1c0b9a8f7e6d5c4b3a2f1e"  # an older head / another PR's head


def view(comments, head=SHA, state="OPEN"):
    return {"state": state, "headRefOid": head, "comments": comments}


def yes(body, cid=101, login="smfworks"):
    return {"author": {"login": login}, "body": body, "id": cid}


# A valid yes: the owner's own comment, yes-shaped, naming the current head.
ok, why, cid = mod.owner_yes_comment(view([yes(f"yes — approved at {SHA}")]), "smfworks")
assert ok, why
assert cid == 101
assert "head" in why or "yes" in why

# Login match is case-insensitive on both sides.
ok, why, _ = mod.owner_yes_comment(view([yes(f"yes — approved at {SHA}", login="SmfWorks")]), "SMFWORKS")
assert ok, why

# A different account's yes does nothing.
ok, why, _ = mod.owner_yes_comment(view([yes(f"yes — approved at {SHA}", login="builder-prime")]), "smfworks")
assert not ok, why

# Stale SHA: the yes names a commit that is no longer the head.
ok, why, _ = mod.owner_yes_comment(view([yes(f"yes — approved at {OLD}")]), "smfworks")
assert not ok and "head" in why

# Irrelevant comments and a bare yes without a SHA change nothing.
ok, why, _ = mod.owner_yes_comment(view([yes("looks good to me"), yes("yes please merge it")]), "smfworks")
assert not ok, why

# Another bot's "owner approved" phrasing is not a yes (and names no SHA).
ok, why, _ = mod.owner_yes_comment(view([yes("owner approved, merge")]), "smfworks")
assert not ok, why

# A yes naming another PR's head does not qualify, and no id comes back.
ok, why, cid = mod.owner_yes_comment(view([yes(f"yes — approved at {OLD}", cid=202)]), "smfworks")
assert not ok and cid is None, why

# reviewDecision is out of the gate entirely: it neither helps nor blocks.
v = {"state": "OPEN", "headRefOid": SHA, "reviewDecision": "APPROVED", "comments": []}
ok, why, _ = mod.owner_yes_comment(v, "smfworks")
assert not ok, why
v["comments"] = [yes(f"yes — approved at {SHA}")]
v["reviewDecision"] = "CHANGES_REQUESTED"
ok, why, cid = mod.owner_yes_comment(v, "smfworks")
assert ok and cid == 101, why

# Closed and merged PRs refuse whatever the comments say.
for state in ("CLOSED", "MERGED"):
    ok, why, _ = mod.owner_yes_comment(view([yes(f"yes — approved at {SHA}")], state=state), "smfworks")
    assert not ok and "not open" in why

# A view without a head SHA refuses.
ok, why, _ = mod.owner_yes_comment({"state": "OPEN", "comments": [yes(f"yes — approved at {SHA}")]}, "smfworks")
assert not ok and "missing head" in why

# The latest qualifying yes wins. An older yes cannot override it, and a
# later non-qualifying yes does not erase an earlier qualifying one.
ok, why, cid = mod.owner_yes_comment(
    view([yes(f"yes — approved at {OLD}", cid=201), yes(f"yes — approved at {SHA}", cid=202)]), "smfworks")
assert ok and cid == 202, why
ok, why, cid = mod.owner_yes_comment(
    view([yes(f"yes — approved at {SHA}", cid=301), yes(f"yes — approved at {OLD}", cid=302)]), "smfworks")
assert ok and cid == 301, why

# The GK_YES_REGEX override is honored when no explicit pattern is passed,
# and an explicit pattern wins over the env.
saved = os.environ.pop("GK_YES_REGEX", None)
try:
    os.environ["GK_YES_REGEX"] = r"^ship it: yes\b"
    ok, why, cid = mod.owner_yes_comment(view([yes(f"ship it: yes — approved at {SHA}", cid=303)]), "smfworks")
    assert ok and cid == 303, why
    ok, why, _ = mod.owner_yes_comment(view([yes(f"no — approved at {SHA}")]), "smfworks")
    assert not ok, why
    ok, why, _ = mod.owner_yes_comment(
        view([yes(f"ship it: yes — approved at {SHA}")]), "smfworks", yes_regex=r"^yes\b")
    assert not ok, "the explicit pattern must win over the env"
finally:
    if saved is None:
        os.environ.pop("GK_YES_REGEX", None)
    else:
        os.environ["GK_YES_REGEX"] = saved

# Comment ids come back as given: REST/digit ids as ints, GraphQL node
# ids as the string the merge gate resolves, missing ids as None.
ok, why, cid = mod.owner_yes_comment(
    view([{"author": {"login": "smfworks"}, "body": f"yes — approved at {SHA}", "id": "IC_kwDODKw3uc7tpgEC"}]),
    "smfworks")
assert ok and cid == "IC_kwDODKw3uc7tpgEC", why
ok, why, cid = mod.owner_yes_comment(
    view([{"author": {"login": "smfworks"}, "body": f"yes — approved at {SHA}", "id": "2987654321"}]),
    "smfworks")
assert ok and cid == 2987654321, why
ok, why, cid = mod.owner_yes_comment(
    view([{"author": {"login": "smfworks"}, "body": f"yes — approved at {SHA}"}]), "smfworks")
assert ok and cid is None, why

# Required contexts come from evaluated branch rules, with classic
# branch protection as a fallback; unrelated rule types are skipped.
req = mod.required_contexts(
    [{"type": "required_status_checks",
      "parameters": {"required_status_checks": [{"context": "test"}, {"context": "slow-scan"}]}},
     {"type": "pull_request", "parameters": {}}],
    {})
assert req == ["slow-scan", "test"], req
req = mod.required_contexts([], {"required_status_checks": {"contexts": ["ci"]}})
assert req == ["ci"], req

# Checks: pending is not green, only success is green, a missing result
# is not green, and no configured rules is green-but-said-so.
green, gwhy = mod.checks_green(["test"], [{"name": "test", "status": "in_progress", "conclusion": None}], [])
assert not green and "pending" in gwhy, gwhy

green, gwhy = mod.checks_green(["test"], [{"name": "test", "status": "completed", "conclusion": "success"}], [])
assert green, gwhy

green, gwhy = mod.checks_green(["test"], [{"name": "test", "status": "completed", "conclusion": "failure"}], [])
assert not green and "failure" in gwhy, gwhy

green, gwhy = mod.checks_green(["scan"], [], [{"context": "scan", "state": "pending"}])
assert not green and "pending" in gwhy, gwhy

green, gwhy = mod.checks_green(["scan"], [], [{"context": "scan", "state": "success"}])
assert green, gwhy

green, gwhy = mod.checks_green(["ghost"], [], [])
assert not green and "no result" in gwhy, gwhy

green, gwhy = mod.checks_green([], [], [])
assert green and "no required checks" in gwhy, gwhy

# One failing report under a required name blocks the merge even when
# another report of the same name is green — the gate is strict.
green, gwhy = mod.checks_green(
    ["ci"],
    [{"name": "ci", "status": "completed", "conclusion": "failure"}],
    [{"context": "ci", "state": "success"}])
assert not green and "failure" in gwhy, gwhy

print("merge_decision: PASS")
