#!/usr/bin/env python3
"""Assign exactly one of four verdicts from sources read this run."""

from __future__ import annotations

from store import DATE_NOT_STATED, NONE_FOUND, VERDICTS

VENDORISH = {"vendor", "vendor-derived"}
SMF_MARKERS = ("smf works", "smfworks")


def source_map(sources: list[dict]) -> dict[str, dict]:
    mapped = {}
    for source in sources:
        if isinstance(source, dict) and source.get("id"):
            mapped[str(source["id"])] = source
    return mapped


def current_sources(sources: list[dict], run_id: str | None = None) -> list[dict]:
    current = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        if not source.get("read_this_run"):
            continue
        if run_id and source.get("run_id") and source.get("run_id") != run_id:
            continue
        current.append(source)
    return current


def is_smf(source: dict) -> bool:
    blob = " ".join(
        str(source.get(key) or "")
        for key in ("author", "affiliation", "title", "evaluator")
    ).casefold()
    return any(marker in blob for marker in SMF_MARKERS)


def comparable(claim: dict, source: dict) -> bool:
    claim_settings = claim.get("settings") or {}
    source_settings = source.get("settings") or {}
    if not isinstance(claim_settings, dict) or not isinstance(source_settings, dict):
        return False
    if not source_settings:
        return False
    for key, value in claim_settings.items():
        if value in (None, ""):
            continue
        if key not in source_settings:
            return False
        if source_settings[key] != value:
            return False
    return True


def methodology_missing(source: dict) -> bool:
    if source.get("methodology_missing"):
        return True
    if source.get("unreadable"):
        return True
    settings = source.get("settings")
    if source.get("role") in {"independent", "vendor", "vendor-derived"} and not settings:
        return True
    return False


def role_of(source: dict) -> str:
    role = str(source.get("role") or "")
    affiliation = str(source.get("affiliation") or "")
    vendor_affiliated = affiliation in {
        "sponsor",
        "partner",
        "reseller",
        "aggregator",
        "vendor",
    }
    if role == "independent" and vendor_affiliated:
        return "vendor-derived"
    if role == "relay" and (vendor_affiliated or source.get("copies_vendor")):
        return "vendor-derived"
    if role in {"independent", "relay"} and is_smf(source):
        return "affiliated"
    return role


def usable(source: dict) -> bool:
    if not source.get("reachable", True):
        return False
    if source.get("unreadable"):
        return False
    if role_of(source) == "snippet":
        return False
    return True


def notes_for(claim: dict, sources: list[dict], verdict: str) -> str:
    notes = []
    existing = str(claim.get("notes") or "").strip()
    if existing:
        notes.append(existing)
    if claim.get("superseded"):
        old = claim.get("superseded_old") or "prior figure"
        new = claim.get("superseded_new") or "newer figure"
        notes.append(f"Superseded/outdated: {old} vs {new}.")
    mismatches = []
    for source in sources:
        claim_settings = claim.get("settings") or {}
        source_settings = source.get("settings") or {}
        if not isinstance(claim_settings, dict) or not isinstance(source_settings, dict):
            continue
        for key, value in claim_settings.items():
            if key in source_settings and source_settings[key] != value:
                mismatches.append(
                    f"{source.get('id')} {key} {source_settings[key]} vs claim {value}"
                )
    if mismatches:
        notes.append("Settings mismatch (not treated as proof): " + "; ".join(mismatches))
    relays = [source for source in sources if role_of(source) == "relay"]
    for source in relays:
        notes.append(
            f"Relay {source.get('id')} reports what it was told; the evaluator page was not independently read."
        )
    snippets = [source for source in sources if role_of(source) == "snippet"]
    if snippets:
        notes.append("A search snippet is discovery, not evidence.")
    if verdict == "vendor-only":
        notes.append("Checked independent sources this run; comparable confirmation was not found.")
    if verdict == "unverifiable":
        gap = claim.get("missing") or "necessary evidence or methodology"
        notes.append(f"Missing: {gap}.")
    return " ".join(notes).strip()


def assign_verdict(claim: dict, sources: list[dict], run_id: str | None = None) -> dict:
    """Return claim copy with verdict, primary, independent cells, and notes."""
    updated = dict(claim)
    current = current_sources(sources, run_id=run_id)
    mapped = source_map(current)
    wanted = []
    for key in ("primary_source_id",):
        sid = claim.get(key)
        if sid and sid in mapped:
            wanted.append(mapped[sid])
    for sid in claim.get("independent_source_ids") or []:
        if sid in mapped:
            wanted.append(mapped[sid])
    if not wanted:
        wanted = current

    reachable = [source for source in wanted if usable(source)]
    if not reachable:
        updated["verdict"] = "unverifiable"
        updated["missing"] = claim.get("missing") or "no accessible evidence read this run"
        updated["primary_text"] = NONE_FOUND
        updated["independent_text"] = NONE_FOUND
        updated["notes"] = notes_for(updated, wanted, "unverifiable")
        return updated

    independent = []
    vendorish = []
    affiliated = []
    for source in reachable:
        role = role_of(source)
        if methodology_missing(source) and role != "relay":
            continue
        if not comparable(claim, source) and source.get("settings"):
            continue
        if role == "independent":
            independent.append(source)
        elif role in VENDORISH:
            vendorish.append(source)
        elif role == "affiliated":
            affiliated.append(source)

    comparable_independent = [source for source in independent if comparable(claim, source)]
    comparable_vendor = [source for source in vendorish if comparable(claim, source) or not source.get("settings")]

    support_ind = [source for source in comparable_independent if source.get("supports") is True]
    contra_ind = [source for source in comparable_independent if source.get("supports") is False]
    support_vendor = [source for source in comparable_vendor if source.get("supports") is True]

    if contra_ind:
        verdict = "contradicted"
    elif support_ind:
        verdict = "supported"
    elif support_vendor or (vendorish and not comparable_independent):
        if any(methodology_missing(source) for source in reachable) and not support_vendor:
            verdict = "unverifiable"
        else:
            verdict = "vendor-only"
    elif affiliated and not support_ind:
        verdict = "vendor-only"
    elif any(methodology_missing(source) for source in reachable) or not comparable_vendor:
        verdict = "unverifiable"
    else:
        verdict = "unverifiable"

    if verdict not in VERDICTS:
        verdict = "unverifiable"

    updated["verdict"] = verdict
    primary = None
    if support_vendor:
        primary = support_vendor[0]
    elif vendorish:
        primary = vendorish[0]
    elif support_ind:
        primary = support_ind[0]
    elif reachable:
        primary = reachable[0]
    updated["primary_text"] = format_primary(primary, claim)
    updated["independent_text"] = format_independent(support_ind, contra_ind, claim)
    updated["notes"] = notes_for(updated, wanted, verdict)
    updated["primary_source_id"] = (primary or {}).get("id") or claim.get("primary_source_id")
    if contra_ind:
        updated["contradicted_values"] = {
            "claim": claim.get("value"),
            "independent": contra_ind[0].get("value"),
            "claim_source": (primary or {}).get("id"),
            "independent_source": contra_ind[0].get("id"),
        }
    return updated


def published_label(source: dict) -> str:
    value = source.get("published")
    if value in (None, "", "date not stated"):
        return DATE_NOT_STATED
    return str(value)


def format_primary(source: dict | None, claim: dict) -> str:
    if not source:
        return NONE_FOUND
    value = source.get("value") if source.get("value") is not None else claim.get("value")
    title = source.get("title") or source.get("id")
    url = source.get("url") or ""
    return f"Vendor reports {value} ({title} {url})".strip()


def format_independent(support: list[dict], contra: list[dict], claim: dict) -> str:
    if contra:
        source = contra[0]
        value = source.get("value")
        return (
            f"{source.get('author') or source.get('title')}: {value} "
            f"under {source.get('settings')} on {published_label(source)} "
            f"({source.get('url')})"
        )
    if support:
        source = support[0]
        value = source.get("value") if source.get("value") is not None else claim.get("value")
        return (
            f"{source.get('author') or source.get('title')}: {value} "
            f"under {source.get('settings')} on {published_label(source)} "
            f"({source.get('url')})"
        )
    return NONE_FOUND
