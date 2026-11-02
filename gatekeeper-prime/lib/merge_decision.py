"""Decide whether the owner's GitHub review covers this head SHA.

A chat line, a kanban comment, or another bot saying "owner approved" is not
a review. reviewDecision alone is not enough: it can be some other account.
"""
from __future__ import annotations


def owner_approved(view: dict, owner_login: str) -> tuple[bool, str]:
    if not owner_login or not owner_login.strip():
        return False, "no owner login recorded at setup"
    head = (view or {}).get("headRefOid") or ""
    if len(head) != 40:
        return False, "missing head SHA"
    login = owner_login.strip().lower()
    for rev in (view or {}).get("reviews") or []:
        author = ((rev.get("author") or {}).get("login") or "").lower()
        state = (rev.get("state") or "").upper()
        commit = ((rev.get("commit") or {}).get("oid") or "")
        if author == login and state == "APPROVED" and commit == head:
            return True, "owner review on the current head SHA"
    return False, "no owner GitHub review on the current head SHA; a message is not approval"
