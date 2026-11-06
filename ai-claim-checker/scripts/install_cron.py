#!/usr/bin/env python3
"""Write the Monday re-check into a jobs file. Does not register a live cron job."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from store import JOB_ID, atomic_write, save_state


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install the weekly claim re-check record")
    parser.add_argument("--data", required=True)
    parser.add_argument("--jobs", required=True)
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--disable", action="store_true")
    parser.add_argument("--tz", default="America/New_York")
    return parser.parse_args(argv)


def load_jobs(path: Path) -> dict:
    if path.is_file():
        loaded = json.loads(path.read_text(encoding="utf-8"))
    else:
        loaded = {"jobs": []}
    if not isinstance(loaded, dict):
        loaded = {"jobs": []}
    jobs = loaded.get("jobs")
    if not isinstance(jobs, list):
        jobs = []
    loaded["jobs"] = jobs
    return loaded


def without_job(jobs: list) -> list:
    kept = []
    for job in jobs:
        if isinstance(job, dict) and job.get("id") == JOB_ID:
            continue
        kept.append(job)
    return kept


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    path = Path(args.jobs)
    loaded = load_jobs(path)
    if args.disable:
        loaded["jobs"] = without_job(loaded["jobs"])
        atomic_write(path, json.dumps(loaded, ensure_ascii=False, indent=2) + "\n")
        save_state(Path(args.data) / "state.json", {"cron_installed": False})
        return 0
    if not args.yes:
        return 0
    kept = without_job(loaded["jobs"])
    tz = args.tz or "America/New_York"
    kept.append(
        {
            "id": JOB_ID,
            "timezone": tz,
            "schedule": {"expr": "0 8 * * 1"},
            "script": "scripts/weekly.py",
            "no_agent": True,
        }
    )
    loaded["jobs"] = kept
    atomic_write(path, json.dumps(loaded, ensure_ascii=False, indent=2) + "\n")
    save_state(Path(args.data) / "state.json", {"tz": tz, "cron_installed": True})
    return 0


if __name__ == "__main__":
    sys.exit(main())
