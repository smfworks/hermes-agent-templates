#!/usr/bin/env python3
"""Write Daily Brief and Monthly Tune-Up job records. Does not call hermes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from store import JOB_DAILY, JOB_MONTHLY, atomic_write, mutate_json


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install Radar cron records")
    parser.add_argument("--data", required=True)
    parser.add_argument("--jobs", required=True)
    parser.add_argument("--yes-daily", action="store_true")
    parser.add_argument("--yes-monthly", action="store_true")
    parser.add_argument("--disable-daily", action="store_true")
    parser.add_argument("--disable-monthly", action="store_true")
    parser.add_argument("--tz", default="America/New_York")
    parser.add_argument("--hour", default="7")
    parser.add_argument("--minute", default="0")
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


def without(jobs: list, job_id: str) -> list:
    return [job for job in jobs if not (isinstance(job, dict) and job.get("id") == job_id)]


def save(path: Path, loaded: dict) -> None:
    atomic_write(path, json.dumps(loaded, ensure_ascii=False, indent=2) + "\n")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    path = Path(args.jobs)
    loaded = load_jobs(path)
    data = Path(args.data)
    if not any((args.yes_daily, args.yes_monthly, args.disable_daily, args.disable_monthly)):
        return 0
    tz = args.tz or "America/New_York"
    hour = str(int(args.hour))
    minute = str(int(args.minute))
    if args.disable_daily:
        loaded["jobs"] = without(loaded["jobs"], JOB_DAILY)
        mutate_json(data / "profile.json", lambda state: state.update({"daily_cron": False}))
    if args.disable_monthly:
        loaded["jobs"] = without(loaded["jobs"], JOB_MONTHLY)
        mutate_json(data / "profile.json", lambda state: state.update({"monthly_cron": False}))
    if args.yes_daily:
        jobs = without(loaded["jobs"], JOB_DAILY)
        jobs.append(
            {
                "id": JOB_DAILY,
                "timezone": tz,
                "schedule": {"expr": f"{minute} {hour} * * *"},
                "script": "scripts/brief.py",
                "no_agent": True,
            }
        )
        loaded["jobs"] = jobs
        mutate_json(
            data / "profile.json",
            lambda state: state.update({"daily_cron": True, "tz": tz}),
        )
    if args.yes_monthly:
        jobs = without(loaded["jobs"], JOB_MONTHLY)
        jobs.append(
            {
                "id": JOB_MONTHLY,
                "timezone": tz,
                "schedule": {"expr": f"{minute} {hour} * * 1"},
                "script": "scripts/monthly.py",
                "no_agent": True,
            }
        )
        loaded["jobs"] = jobs
        mutate_json(
            data / "profile.json",
            lambda state: state.update({"monthly_cron": True, "tz": tz}),
        )
    save(path, loaded)
    return 0


if __name__ == "__main__":
    sys.exit(main())
