#!/usr/bin/env python3
"""Record default Daily Wisdom cron jobs. Does not call hermes or register a live job."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sitting import atomic_write, load_state, save_state

SITTING_ID = "daily-wisdom-sitting"
WEEKLY_ID = "daily-wisdom-weekly"
OWNED = {SITTING_ID, WEEKLY_ID}
TZ = "America/New_York"


def default_jobs() -> list[dict]:
    return [
        {
            "id": SITTING_ID,
            "name": "Daily Wisdom sitting",
            "timezone": TZ,
            "schedule": {"expr": "0 8 * * *"},
            "script": "scripts/sitting.py",
            "no_agent": True,
        },
        {
            "id": WEEKLY_ID,
            "name": "Daily Wisdom weekly page",
            "timezone": TZ,
            "schedule": {"expr": "0 18 * * 0"},
            "script": "scripts/weekly.py",
            "no_agent": True,
        },
    ]


def load_jobs(path: Path) -> dict:
    if not path.is_file():
        return {"jobs": []}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise SystemExit("jobs file must be a JSON object")
    jobs = loaded.get("jobs")
    if not isinstance(jobs, list):
        loaded["jobs"] = []
    return loaded


def write_skip(data: Path, jobs_path: Path) -> None:
    document = load_jobs(jobs_path)
    kept = [job for job in document["jobs"] if job.get("id") not in OWNED]
    document["jobs"] = kept + default_jobs()
    atomic_write(jobs_path, json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    state = load_state(data / "state.json")
    prefs = state.get("prefs")
    if not isinstance(prefs, dict):
        prefs = {}
    else:
        prefs = dict(prefs)
    prefs["rotation"] = "full"
    state["prefs"] = prefs
    state["tz"] = TZ
    state["schedule"] = {"sitting": "0 8 * * *", "weekly": "0 18 * * 0"}
    save_state(data / "state.json", state)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record Daily Wisdom cron defaults.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--jobs", required=True)
    parser.add_argument("--skip", action="store_true", help="Use default time, rotation, and weekly slot")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.skip:
        raise SystemExit("pass --skip to record the default schedule without a live cron call")
    write_skip(Path(args.data), Path(args.jobs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
