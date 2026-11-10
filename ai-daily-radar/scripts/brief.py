#!/usr/bin/env python3
"""Run one Radar brief from a fixture pack. Ledger appends only after delivery."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ledger import append_after_delivery, dedup
from render_brief import (
    build_html,
    build_markdown,
    build_wrap_html,
    build_wrap_markdown,
    wrap_headline,
)
from store import (
    FIXTURE_BANNER,
    FOOTER,
    MAX_ITEMS,
    atomic_write,
    check_date,
    iso_week,
    load_json,
    parse_time,
    read_jsonl,
    write_json,
)
from tagging import tag_many
from validate_brief import validate_brief


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write an AI Daily Radar brief")
    parser.add_argument("--data", required=True)
    parser.add_argument("--fixtures", required=True)
    parser.add_argument("--now", required=True)
    parser.add_argument("--tz", default="America/New_York")
    parser.add_argument("--no-deliver", action="store_true")
    parser.add_argument("--rumor", action="store_true")
    parser.add_argument("--style", default="")
    parser.add_argument("--live", action="store_true")
    return parser.parse_args(argv)


def rank(items: list[dict], profile: dict, weights: dict) -> list[dict]:
    stack = str(profile.get("stack") or "").casefold()
    use = str(profile.get("use") or "").casefold()

    def score(item: dict) -> tuple:
        value = 0
        for token in item.get("stack_match") or []:
            if token.casefold() in stack or token.casefold() in use:
                value += 10
        for topic in item.get("topics") or []:
            info = weights.get(topic) or {}
            value += int(info.get("rank") or 0)
            if info.get("only_if_major") and not (
                item.get("material") or item.get("security") or item.get("major")
            ):
                value -= 100
        return (-value, str(item.get("id") or ""))

    return sorted(items, key=score)


def log_run(data: Path, row: dict) -> None:
    path = data / "runs.jsonl"
    from store import read_jsonl, write_jsonl

    rows = read_jsonl(path)
    rows.append(row)
    write_jsonl(path, rows)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data = Path(args.data)
    if args.live:
        print(
            "Live briefs use the Hermes web search and page-extract tools in chat. "
            "This script is the fixtures path. No search key is required for fixture smoke.",
            file=sys.stderr,
        )
        return 4
    payload = json.loads(Path(args.fixtures).read_text(encoding="utf-8"))
    profile = load_json(data / "profile.json", default={})
    if not isinstance(profile, dict):
        profile = {}
    weights = load_json(data / "topic-weights.json", default={})
    if not isinstance(weights, dict):
        weights = {}
    rumor = args.rumor or bool(profile.get("rumor_opt_in"))
    tagged = tag_many(payload.get("candidates") or payload.get("items") or [], rumor_opt_in=rumor)
    dropped = [item for item in tagged if item.get("dropped")]
    alive = [item for item in tagged if not item.get("dropped")]
    ledger_path = data / "ledger.jsonl"
    ledger_rows = read_jsonl(ledger_path)
    alive = dedup(alive, ledger_rows, args.now)
    alive = rank(alive, profile, weights)[:MAX_ITEMS]
    style = (args.style or profile.get("style") or "standard").casefold()
    if len(alive) <= 2:
        style = "quick"
    brief = validate_brief(
        {
            "items": alive,
            "dropped": [{"id": item.get("id"), "reason": item.get("drop_reason")} for item in dropped],
            "try_this": payload.get("try_this"),
            "banner": FIXTURE_BANNER,
            "week_lines": payload.get("week_lines"),
            "ignore": payload.get("ignore"),
            "archive": payload.get("archive"),
            "wrap_headline": payload.get("wrap_headline"),
        }
    )
    date_line = f"{check_date(args.now)} ({args.tz})"
    log_run(
        data,
        {
            "at": args.now,
            "items": len(brief["items"]),
            "dropped": len(brief["dropped"]),
            "silent": len(brief["items"]) == 0,
            "delivered": False,
        },
    )
    if not brief["items"]:
        return 0
    md = build_markdown(brief, style, date_line)
    html_doc = build_html(brief, style, date_line)
    day = check_date(args.now)
    md_path = data / "briefs" / f"{day}.md"
    html_path = data / "briefs" / f"{day}.html"
    if args.no_deliver:
        print("delivery deferred")
        return 0
    atomic_write(md_path, md)
    atomic_write(html_path, html_doc)
    friday = parse_time(args.now).weekday() == 4
    wrap_path = None
    if friday and (payload.get("week_lines") or payload.get("wrap")):
        week = iso_week(args.now)
        wrap_md = build_wrap_markdown(brief, week)
        wrap_html = build_wrap_html(brief, week)
        wrap_path = data / "wraps" / f"{week}.md"
        atomic_write(wrap_path, wrap_md)
        atomic_write(data / "wraps" / f"{week}.html", wrap_html)
    append_after_delivery(ledger_path, ledger_rows, brief["items"], args.now)
    sys.stdout.write(md)
    if wrap_path:
        sys.stdout.write("\n" + wrap_headline(brief) + "\n" + wrap_path.as_posix() + "\n")
    if FOOTER not in md:
        sys.stdout.write(FOOTER + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
