#!/usr/bin/env python3
"""Record Receipts cron jobs. Does not call hermes. Writes jobs only on --yes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from store import atomic_write, load_state, save_state

SCAN_ID = "money-back-weekly-scan"
REMIND_ID = "money-back-renewal-reminders"
OWNED = {SCAN_ID, REMIND_ID}
TZ = "America/New_York"


def default_jobs(cadence: str) -> list[dict]:
    if cadence == "daily":
        scan_expr = "0 8 * * *"
    else:
        scan_expr = "0 9 * * 0"
    return [
        {
            "id": SCAN_ID,
            "name": "Receipts scan",
            "timezone": TZ,
            "schedule": {"expr": scan_expr},
            "script": "scripts/scan.py",
            "no_agent": True,
        },
        {
            "id": REMIND_ID,
            "name": "Receipts renewal reminders",
            "timezone": TZ,
            "schedule": {"expr": "30 8 * * *"},
            "script": "scripts/remind.py",
            "no_agent": True,
        },
    ]


def load_jobs(path: Path) -> dict:
    if not path.is_file():
        return {"jobs": []}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise SystemExit("jobs file must be a JSON object")
    if not isinstance(loaded.get("jobs"), list):
        loaded["jobs"] = []
    return loaded


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record Receipts cron jobs.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--jobs", required=True)
    parser.add_argument("--yes", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.yes:
        return 0
    data = Path(args.data)
    jobs_path = Path(args.jobs)
    state = load_state(data / "state.json")
    cadence = state.get("cadence") or "weekly"
    document = load_jobs(jobs_path)
    kept = [job for job in document["jobs"] if job.get("id") not in OWNED]
    document["jobs"] = kept + default_jobs(str(cadence))
    atomic_write(jobs_path, json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    save_state(data / "state.json", {"tz": TZ, "cron_installed": True})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
