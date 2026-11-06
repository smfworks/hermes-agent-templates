"""Decide whether the owner's yes covers this head SHA.

Michael's decision (Nov 2, 2026, 1:57 PM ET), replacing required
reviewers: the owner approves by commenting `yes` on the PR, naming the
exact current head SHA. Any push moves `headRefOid`, so an old yes
refuses by itself. A chat line, the PR body, or another bot saying
"owner approved" is not a yes — only the owner login's own comment
counts. The old review-based gate (`owner_approved`) is gone.

The account that runs the merge must not be that owner login and must not
be the repository owner (`actor_may_merge`). A bot signed in as the owner
cannot comment yes and merge.

The view comes from `gh pr view --json state,headRefOid,comments`
(GraphQL — the REST pull response has no headRefOid). Comments arrive
oldest first; the latest qualifying yes wins.
"""
from __future__ import annotations

import os
import re

DEFAULT_YES_REGEX = r"^yes\b"
_HEX40 = re.compile(r"[0-9a-fA-F]{40}")


def _yes_pattern(yes_regex):
    """Resolve the yes pattern: explicit arg, then $GK_YES_REGEX, then the
    default. Returns the compiled pattern, or None when configured badly
    (callers fail closed on None)."""
    source = yes_regex
    if source is None:
        source = os.environ.get("GK_YES_REGEX") or DEFAULT_YES_REGEX
    try:
        return re.compile(source, re.IGNORECASE)
    except re.error:
        return None


def _comment_id(comment):
    """Normalize a comment id: REST ids (ints, or digit strings) come
    back as ints; GraphQL node ids come back as the string the caller
    can resolve to a database id; anything missing is None."""
    cid = comment.get("id")
    if isinstance(cid, bool):
        return None
    if isinstance(cid, int):
        return cid
    if isinstance(cid, str):
        stripped = cid.strip()
        if stripped.isdigit():
            return int(stripped)
        if stripped:
            return stripped
    return None


def actor_may_merge(actor_login: str, owner_login: str, repo_owner: str = "") -> tuple[bool, str]:
    """May this GitHub account run the merge?

    The account that executes the merge (`gh api user`) must be a different
    login from the owner whose yes comment counts, and from the repository
    owner. A shared owner login can post `yes <head SHA>` and then merge;
    that path is closed. An empty actor fails closed.
    """
    actor = (actor_login or "").strip()
    owner = (owner_login or "").strip()
    repo = (repo_owner or "").strip()
    if not owner:
        return False, "no owner login recorded at setup"
    if not actor:
        return False, "could not read the GitHub account running the merge"
    if actor.lower() == owner.lower():
        return False, "the GitHub account running the merge is the owner login; a shared login cannot approve and merge"
    if repo and actor.lower() == repo.lower():
        return False, "the GitHub account running the merge is the repository owner; a shared login cannot approve and merge"
    return True, "merge account differs from the owner login and the repository owner"


def owner_yes_comment(view: dict, owner_login: str, yes_regex: str = None) -> tuple[bool, str, object]:
    """Is the owner's latest yes comment on this PR's current head?

    A qualifying comment is authored by `owner_login` (case-insensitive),
    starts with a yes (`yes_regex`, anchored like ^yes\\b by default), and
    contains the current 40-hex `headRefOid`. A push after the yes moves
    the head, so the old comment stops qualifying on its own. Returns
    (ok, why, comment_id) with a short human reason.
    """
    view = view or {}
    if not owner_login or not str(owner_login).strip():
        return False, "no owner login recorded at setup", None
    pattern = _yes_pattern(yes_regex)
    if pattern is None:
        return False, "invalid yes pattern configured", None
    head = view.get("headRefOid") or ""
    if len(head) != 40:
        return False, "missing head SHA", None
    state = (view.get("state") or "").upper()
    if state != "OPEN":
        return False, f"pull request is {view.get('state') or 'unknown'}, not open", None

    login = str(owner_login).strip().lower()
    latest = None
    for comment in view.get("comments") or []:
        if not isinstance(comment, dict):
            continue
        author = (comment.get("author") or {}).get("login") or ""
        if not isinstance(author, str) or author.lower() != login:
            continue
        body = comment.get("body") or ""
        if not isinstance(body, str):
            continue
        if not pattern.search(body):
            continue
        if not _HEX40.search(body):
            continue
        if head.lower() not in body.lower():
            continue  # names some other SHA (an older head, another PR)
        latest = comment
    if latest is None:
        return False, "no owner yes comment naming the current head SHA; a message is not approval", None
    return True, "owner yes comment on the current head SHA", _comment_id(latest)


def required_contexts(branch_rules, protection) -> list:
    """Required status-check context names for the protected branch.

    `branch_rules` is the evaluated rule list from
    `gh api repos/O/N/rules/branches/<branch>` (active repo and org
    rulesets, already merged by GitHub); `protection` is the classic
    branch-protection response, kept as a fallback source.
    """
    contexts = []
    for rule in branch_rules or []:
        if not isinstance(rule, dict) or rule.get("type") != "required_status_checks":
            continue
        for entry in (rule.get("parameters") or {}).get("required_status_checks") or []:
            ctx = entry.get("context") if isinstance(entry, dict) else None
            if isinstance(ctx, str) and ctx.strip():
                contexts.append(ctx.strip())
    bp = ((protection or {}).get("required_status_checks") or {})
    for ctx in bp.get("contexts") or []:
        if isinstance(ctx, str) and ctx.strip():
            contexts.append(ctx.strip())
    return sorted(set(contexts))


def checks_green(required, check_runs, statuses) -> tuple[bool, str]:
    """Is every required check green on the head SHA?

    The caller fetches check runs and commit statuses for the head SHA
    (the endpoint URL filters by head_sha). A required context counts
    only when every report under its name is a completed, successful
    check run or a successful status; pending is not green. With no
    required contexts configured the commit is treated as green, and
    the reason says so. Returns (ok, why).
    """
    required = sorted({c.strip() for c in (required or []) if isinstance(c, str) and c.strip()})
    if not required:
        return True, "no required checks configured; treating the head as green"

    runs = {}
    for run in check_runs or []:
        if isinstance(run, dict) and run.get("name"):
            runs.setdefault(str(run["name"]), []).append(run)
    stats = {}
    for status in statuses or []:
        if isinstance(status, dict) and status.get("context"):
            stats.setdefault(str(status["context"]), []).append(status)

    for ctx in required:
        if not runs.get(ctx) and not stats.get(ctx):
            return False, f"required check '{ctx}' has no result on the head SHA"
        for run in runs.get(ctx, []):
            if run.get("status") != "completed":
                state = run.get("status") or "pending"
                return False, f"required check '{ctx}' is {state} (pending is not green)"
            if run.get("conclusion") != "success":
                conclusion = run.get("conclusion") or "without a conclusion"
                return False, f"required check '{ctx}' finished {conclusion}"
        for status in stats.get(ctx, []):
            if status.get("state") != "success":
                state = status.get("state") or "unknown"
                return False, f"required check '{ctx}' status is {state}"
    return True, f"all {len(required)} required checks green on the head SHA"
