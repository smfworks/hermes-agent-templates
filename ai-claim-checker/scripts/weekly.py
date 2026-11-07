#!/usr/bin/env python3
"""Re-check saved claims. Print only when a verdict or reachability changes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from claim_validate import validate_payload
from evidence import load_fixture
from store import load_state, read_json, write_json


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Weekly saved-claim re-check")
    parser.add_argument("--data", required=True)
    parser.add_argument("--now", default=None)
    return parser.parse_args(argv)


def fingerprint(rows: list[dict]) -> list[tuple]:
    return [
        (
            str(row.get("text") or row.get("id") or ""),
            str(row.get("verdict") or ""),
            str(row.get("reachable", True)),
        )
        for row in rows
    ]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data = Path(args.data)
    state = load_state(data / "state.json")
    if not state.get("cron_installed"):
        return 0
    saved = read_json(data / "saved-claims.json", default={"claims": []})
    rows = saved.get("claims") if isinstance(saved, dict) else []
    if not rows:
        return 0
    notices = []
    last_outage = state.get("last_outage_notice") or ""
    updated = []
    for row in rows:
        fixture = row.get("fixture")
        previous_verdict = row.get("verdict")
        if not fixture or not Path(fixture).is_file():
            warning = f"Saved claim fixture missing for {row.get('text')}"
            if warning != last_outage:
                notices.append(warning)
                last_outage = warning
            historical = dict(row)
            historical["historical"] = True
            historical["reachable"] = False
            updated.append(historical)
            continue
        payload = load_fixture(Path(fixture))
        validated = validate_payload(payload)
        new_verdicts = [item.get("verdict") for item in validated.get("claims") or []]
        unreachable = [
            source
            for source in validated.get("sources") or []
            if source.get("reachable") is False
        ]
        current = new_verdicts[0] if new_verdicts else "unverifiable"
        changed = current != previous_verdict
        if unreachable:
            warning = (
                f"Named source unreachable: "
                + ", ".join(str(source.get("id")) for source in unreachable)
            )
            if warning != last_outage:
                notices.append(warning)
                last_outage = warning
            row = dict(row)
            row["historical"] = True
            row["reachable"] = False
        if changed:
            notices.append(
                f"Verdict changed for {row.get('text')}: {previous_verdict} -> {current}"
            )
            row = dict(row)
            row["verdict"] = current
            row["prior_verdict"] = previous_verdict
        updated.append(row)
    write_json(data / "saved-claims.json", {"claims": updated})
    if last_outage:
        from store import save_state

        save_state(data / "state.json", {"last_outage_notice": last_outage})
    if not notices:
        return 0
    sys.stdout.write("\n".join(notices) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
