#!/usr/bin/env python3
"""Run one claim check from fixtures. Overwrite the card in place."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from claim_validate import validate_payload
from decompose import decompose
from evidence import load_fixture, timeout_payload
from render_card import build_html, build_markdown, chat_summary, sources_csv
from store import (
    append_jsonl,
    atomic_write,
    check_date,
    claim_dir,
    load_state,
    read_json,
    sanitize_slug,
    save_state,
    utc_now_text,
    write_json,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write an AI Claim Checker card")
    parser.add_argument("--data", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--backend", default="fixtures", choices=["fixtures", "live"])
    parser.add_argument("--fixtures", default=None)
    parser.add_argument("--now", default=None)
    parser.add_argument("--tz", default="America/New_York")
    parser.add_argument("--style", default=None, choices=["card", "brief"])
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--timeout", action="store_true")
    return parser.parse_args(argv)


def apply_style(state: dict, explicit: str | None) -> str:
    if explicit:
        return explicit
    return str(state.get("style") or "card")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data = Path(args.data)
    state = load_state(data / "state.json")
    now = args.now or utc_now_text()
    slug = sanitize_slug(args.slug)
    if args.backend == "live":
        print(
            "Live research uses the Hermes web search and page-extract tools in chat. "
            "This script is the fixtures path. No research key is required for fixture smoke.",
            file=sys.stderr,
        )
        return 4
    if args.timeout:
        payload = timeout_payload(
            run_id="timeout-run",
            title="Unreachable evaluator",
            source_id="s-timeout",
            url="https://example.invalid/eval",
        )
    else:
        if not args.fixtures:
            print("A fixtures path is required for the fixtures backend.", file=sys.stderr)
            return 1
        payload = load_fixture(Path(args.fixtures))
    payload.setdefault("title", slug)
    payload["input_label"] = (payload.get("input") or {}).get("value") or payload.get(
        "input_label"
    )
    if (payload.get("input") or {}).get("owner_supplied"):
        payload["owner_supplied"] = True
    split = decompose(payload)
    payload["claims"] = split["claims"]
    payload["not_checkable"] = split["not_checkable"]
    payload["omitted_count"] = split["omitted_count"]
    validated = validate_payload(payload)
    checked_on = check_date(now)
    style = apply_style(state, args.style)
    folder = claim_dir(data, slug)
    md_path = folder / "claim-card.md"
    html_path = folder / "claim-card.html"
    markdown = build_markdown(validated, checked_on, style="card")
    brief = build_markdown(validated, checked_on, style="brief")
    rendered = build_html(validated, checked_on)
    atomic_write(md_path, markdown)
    atomic_write(html_path, rendered)
    write_json(folder / "claims.json", validated.get("claims") or [])
    write_json(folder / "sources.json", validated.get("sources") or [])
    atomic_write(folder / "sources.csv", sources_csv(validated.get("sources") or []))
    if style == "brief":
        atomic_write(folder / "claim-brief.md", brief)
    history_row = {
        "slug": slug,
        "at": now,
        "run_id": validated.get("run_id"),
        "verdicts": [row.get("verdict") for row in validated.get("claims") or []],
        "style": style,
    }
    append_jsonl(data / "history.jsonl", history_row)
    append_jsonl(folder / "history.jsonl", history_row)
    save_state(
        data / "state.json",
        {"last_slug": slug, "tz": args.tz, "style": style},
    )
    if args.save:
        saved_path = data / "saved-claims.json"
        saved = read_json(saved_path, default={"claims": []})
        if not isinstance(saved, dict):
            saved = {"claims": []}
        rows = saved.get("claims")
        if not isinstance(rows, list):
            rows = []
        for row in validated.get("claims") or []:
            rows.append(
                {
                    "slug": slug,
                    "text": row.get("text"),
                    "settings": row.get("settings") or {},
                    "verdict": row.get("verdict"),
                    "sources": [
                        row.get("primary_source_id"),
                        *(row.get("independent_source_ids") or []),
                    ],
                    "checked_on": checked_on,
                    "run_id": validated.get("run_id"),
                    "fixture": args.fixtures,
                }
            )
        saved["claims"] = rows
        write_json(saved_path, saved)
    visible = brief if style == "brief" else markdown
    sys.stdout.write(chat_summary(validated, md_path, html_path, style))
    if style == "brief":
        sys.stdout.write(visible)
    return 0


if __name__ == "__main__":
    sys.exit(main())
