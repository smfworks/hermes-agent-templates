#!/usr/bin/env python3
"""Fail closed when verdicts, citations, run IDs, or dates are invalid."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from store import DATE_NOT_STATED, SOURCE_ROLES, VERDICTS, is_safe_http_url
from verdict import assign_verdict, current_sources, source_map

ALLOWED_URL_SCHEMES = ("http://", "https://")


class ValidationError(ValueError):
    pass


def fail_closed(claim: dict, reason: str) -> dict:
    updated = dict(claim)
    updated["verdict"] = "unverifiable"
    updated["missing"] = reason
    updated["notes"] = f"Missing: {reason}."
    if not updated.get("independent_text"):
        updated["independent_text"] = "None found"
    if not updated.get("primary_text"):
        updated["primary_text"] = "None found"
    return updated


def published_or_missing(source: dict) -> str:
    value = source.get("published")
    if value in (None, "", DATE_NOT_STATED):
        return DATE_NOT_STATED
    return str(value)


def validate_source(source: dict, run_id: str) -> list[str]:
    errors = []
    if not source.get("id"):
        errors.append("source missing id")
    role = source.get("role")
    if role not in SOURCE_ROLES:
        errors.append(f"source {source.get('id')} role {role!r} is not allowed")
    url = source.get("url") or ""
    if url and not is_safe_http_url(url):
        errors.append(f"source {source.get('id')} url is not a safe http(s) link")
    if source.get("read_this_run") and source.get("run_id") not in (None, run_id):
        errors.append(f"source {source.get('id')} run_id does not match this run")
    if source.get("retrieved_at") and source.get("published"):
        if str(source["retrieved_at"]) == str(source["published"]) and source.get(
            "retrieved_is_not_published"
        ):
            errors.append(f"source {source.get('id')} uses retrieval as publication")
    return errors


def validate_payload(payload: dict) -> dict:
    """Return a copy with valid rows, or fail closed per claim."""
    run_id = str(payload.get("run_id") or "")
    if not run_id:
        raise ValidationError("run_id is required")
    sources = [item for item in payload.get("sources") or [] if isinstance(item, dict)]
    source_errors = []
    for source in sources:
        source_errors.extend(validate_source(source, run_id))
        source["published_label"] = published_or_missing(source)
    if source_errors:
        # Invalid evidence relationships fail closed rather than inventing a card.
        payload = dict(payload)
        payload["source_errors"] = source_errors
    mapped = source_map(current_sources(sources, run_id=run_id))
    claims = []
    for raw in payload.get("claims") or []:
        if not isinstance(raw, dict):
            continue
        claim = assign_verdict(raw, sources, run_id=run_id)
        verdict = claim.get("verdict")
        if verdict not in VERDICTS:
            claim = fail_closed(claim, "verdict was not one of the four allowed values")
        primary_id = claim.get("primary_source_id")
        if primary_id and primary_id not in mapped and claim["verdict"] != "unverifiable":
            claim = fail_closed(claim, f"primary source {primary_id} was not read this run")
        for sid in claim.get("independent_source_ids") or []:
            if sid not in mapped and claim["verdict"] in {"supported", "contradicted"}:
                claim = fail_closed(claim, f"independent source {sid} was not read this run")
        if claim["verdict"] == "supported" and (
            not claim.get("independent_source_ids")
            and "None found" in str(claim.get("independent_text"))
        ):
            claim = fail_closed(claim, "supported requires independent evidence read this run")
        claims.append(claim)
    out = dict(payload)
    out["claims"] = claims
    out["sources"] = sources
    out["run_id"] = run_id
    return out


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a claims payload")
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    try:
        validated = validate_payload(payload)
    except ValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    Path(args.out).write_text(
        json.dumps(validated, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"claims": len(validated["claims"]), "run_id": validated["run_id"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
