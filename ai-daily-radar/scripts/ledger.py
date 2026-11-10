#!/usr/bin/env python3
"""Normalize URLs, same-story keys, material updates, append after delivery."""

from __future__ import annotations

from datetime import timedelta
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from store import parse_time, read_jsonl, write_jsonl

TRACKING = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "ref",
}
LOCALE_SEGMENTS = {"en", "en-us", "en-gb", "fr", "de", "es", "ja", "zh"}


def normalize_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    scheme = (parsed.scheme or "https").lower()
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    segments = [part for part in parsed.path.split("/") if part]
    if segments and segments[0].lower() in LOCALE_SEGMENTS:
        segments = segments[1:]
    path = "/" + "/".join(segments)
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING
    ]
    query_text = urlencode(query)
    return urlunparse((scheme, host, path or "/", "", query_text, ""))


def story_key(item: dict) -> str:
    vendor = str(item.get("vendor") or "").strip().casefold()
    product = str(item.get("product") or "").strip().casefold()
    event = str(item.get("event_type") or "").strip().casefold()
    return f"{vendor}|{product}|{event}"


def same_story(a: dict, b: dict, now: str) -> bool:
    url_a = normalize_url((a.get("primary") or {}).get("url") or a.get("url") or "")
    url_b = normalize_url((b.get("primary") or {}).get("url") or b.get("url") or "")
    if url_a and url_b and url_a == url_b:
        return True
    if story_key(a) == story_key(b) and story_key(a) != "||":
        at_a = a.get("at") or a.get("first_seen") or now
        at_b = b.get("at") or b.get("first_seen") or now
        try:
            delta = abs(parse_time(at_a) - parse_time(at_b))
        except ValueError:
            delta = timedelta(0)
        if delta <= timedelta(days=7):
            return True
    main = normalize_url(str(a.get("points_to_primary") or b.get("points_to_primary") or ""))
    if main and main in {url_a, url_b}:
        return True
    if a.get("secondary_of") and normalize_url(str(a["secondary_of"])) == url_b:
        return True
    if b.get("secondary_of") and normalize_url(str(b["secondary_of"])) == url_a:
        return True
    return False


def is_material(new: dict, old: dict) -> bool:
    if new.get("commentary") or new.get("repost") or new.get("opinion"):
        return False
    old_tag = old.get("tag")
    new_tag = new.get("tag")
    if old_tag == "Announced" and new_tag == "Shipped":
        return True
    if old.get("availability") == "announced" and new.get("availability") in {"ga", "shipped"}:
        return True
    if old_tag and new_tag and old_tag != new_tag:
        return True
    if new.get("price_change") or new.get("limits_change") or new.get("region_change"):
        return True
    if new.get("security") or new.get("rollback") or new.get("deprecation"):
        return True
    return False


def material_prefix(item: dict) -> dict:
    out = dict(item)
    headline = str(out.get("headline") or "")
    if not headline.startswith("Update:"):
        out["headline"] = f"Update: {headline}".strip()
    out["material"] = True
    return out


def prune(rows: list[dict], now: str, days: int = 30) -> list[dict]:
    cutoff = parse_time(now) - timedelta(days=days)
    kept = []
    for row in rows:
        at = row.get("at") or row.get("first_seen") or now
        try:
            when = parse_time(str(at))
        except ValueError:
            kept.append(row)
            continue
        if when >= cutoff:
            kept.append(row)
    return kept


def dedup(items: list[dict], ledger: list[dict], now: str) -> list[dict]:
    kept: list[dict] = []
    for item in items:
        if item.get("dropped"):
            continue
        matched_old = None
        for old in ledger:
            if same_story(item, old, now):
                matched_old = old
                break
        matched_new = None
        for other in kept:
            if same_story(item, other, now):
                matched_new = other
                break
        if matched_new is not None:
            continue
        if matched_old is not None:
            if is_material(item, matched_old):
                kept.append(material_prefix(item))
            else:
                continue
        else:
            kept.append(item)
    return kept


def append_after_delivery(path, rows: list[dict], delivered: list[dict], now: str) -> None:
    if not delivered:
        existing = prune(read_jsonl(path), now)
        write_jsonl(path, existing)
        return
    existing = read_jsonl(path)
    for item in delivered:
        existing.append(
            {
                "id": item.get("id"),
                "headline": item.get("headline"),
                "tag": item.get("tag"),
                "vendor": item.get("vendor"),
                "product": item.get("product"),
                "event_type": item.get("event_type"),
                "url": (item.get("primary") or {}).get("url"),
                "at": now,
                "first_seen": now,
                "delivered": True,
            }
        )
    write_jsonl(path, prune(existing, now))
