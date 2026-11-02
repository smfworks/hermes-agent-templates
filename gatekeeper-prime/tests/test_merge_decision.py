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
print("merge_decision: PASS")
