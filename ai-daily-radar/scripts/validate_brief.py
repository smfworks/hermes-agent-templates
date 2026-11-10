#!/usr/bin/env python3
"""Fail closed: at most 7 items, one tag, a primary link, no banned categories."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from store import HEADLINE_WORDS, MAX_ITEMS, TAGS, is_safe_http_url, word_count


def validate_item(item: dict) -> list[str]:
    errors = []
    if item.get("dropped"):
        return ["dropped"]
    tag = item.get("tag")
    if tag not in TAGS:
        errors.append("tag missing or invalid")
    if item.get("election") or item.get("campaign") or item.get("investment"):
        errors.append("banned category")
    primary = item.get("primary") or {}
    url = str(primary.get("url") or "")
    if not url:
        errors.append("no primary link")
    elif not is_safe_http_url(url):
        errors.append("primary link is not http(s)")
    if tag == "Vendor-claimed" and item.get("vendor_number") is not None:
        blob = " ".join(
            str(item.get(key) or "")
            for key in ("what_changed", "tag_note", "vendor_says_line")
        )
        if "Vendor says" not in blob and not item.get("vendor_says"):
            errors.append("vendor-claimed number missing Vendor says")
    headline = str(item.get("headline") or "")
    if word_count(headline) > HEADLINE_WORDS:
        errors.append("headline longer than 12 words")
    return errors


def validate_brief(payload: dict) -> dict:
    items = [item for item in payload.get("items") or [] if isinstance(item, dict)]
    kept = []
    dropped = []
    for item in items:
        errors = validate_item(item)
        if errors:
            dropped.append({"id": item.get("id"), "errors": errors})
            continue
        kept.append(item)
    if len(kept) > MAX_ITEMS:
        extra = kept[MAX_ITEMS:]
        kept = kept[:MAX_ITEMS]
        for item in extra:
            dropped.append({"id": item.get("id"), "errors": ["over cap"]})
    out = dict(payload)
    out["items"] = kept
    out["dropped"] = list(payload.get("dropped") or []) + dropped
    return out


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a Radar brief")
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    out = validate_brief(payload)
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"items": len(out["items"]), "dropped": len(out["dropped"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
