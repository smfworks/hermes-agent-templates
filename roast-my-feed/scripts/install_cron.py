#!/usr/bin/env python3
"""Write the Monday check-in into a jobs file. Does not register a live cron job."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from store import atomic_write, save_state

JOB_ID = "roast-weekly-checkin"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install the weekly roast job record")
    parser.add_argument("--data", required=True)
    parser.add_argument("--jobs", required=True)
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--tz", default="America/New_York")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.yes:
        return 0
    path = Path(args.jobs)
    if path.is_file():
        loaded = json.loads(path.read_text(encoding="utf-8"))
    else:
        loaded = {"jobs": []}
    if not isinstance(loaded, dict):
        loaded = {"jobs": []}
    jobs = loaded.get("jobs")
    if not isinstance(jobs, list):
        jobs = []
    kept = []
    for job in jobs:
        if isinstance(job, dict) and job.get("id") == JOB_ID:
            continue
        kept.append(job)
    tz = args.tz or "America/New_York"
    kept.append(
        {
            "id": JOB_ID,
            "timezone": tz,
            "schedule": {"expr": "0 9 * * 1"},
            "script": "scripts/audit.py",
            "no_agent": True,
        }
    )
    loaded["jobs"] = kept
    atomic_write(path, json.dumps(loaded, ensure_ascii=False, indent=2) + "\n")
    save_state(Path(args.data) / "state.json", {"tz": tz, "cron_installed": True})
    return 0


if __name__ == "__main__":
    sys.exit(main())
