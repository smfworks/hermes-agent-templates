#!/usr/bin/env python3
"""Write a local jobs file. Does not call hermes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from store import FileLock, atomic_write, mutate_json, require_slug

CRON_EXPR = "7 6,18 * * *"
DEFAULT_TZ = "America/New_York"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install or stop a fare watch job record.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--jobs", required=True)
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--no", action="store_true")
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--booked", action="store_true")
    parser.add_argument("--booked-stop", action="store_true")
    parser.add_argument("--tz", default=DEFAULT_TZ)
    parser.add_argument("--times", default="06:07,18:07")
    parser.add_argument("--now", default="")
    return parser.parse_args(argv)


def load_jobs(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return loaded
    if isinstance(loaded, dict):
        jobs = loaded.get("jobs", [])
        if isinstance(jobs, list):
            return jobs
    return []


def save_jobs(path: Path, jobs: list[dict]) -> None:
    with FileLock(path):
        atomic_write(path, json.dumps({"jobs": jobs}, ensure_ascii=False, indent=2) + "\n")


def schedule_for(times: str) -> str:
    slots = [part.strip() for part in times.split(",") if part.strip()]
    if not slots:
        return CRON_EXPR
    hours: list[str] = []
    minute = "7"
    for slot in slots:
        hour, minute = slot.split(":", 1)
        hours.append(str(int(hour)))
        minute = str(int(minute))
    return f"{minute} {','.join(hours)} * * *"


def set_watch(data: Path, slug: str, *, watch_yes: bool | None = None, paused: bool | None = None) -> None:
    trip = data / "trips" / f"{slug}-state.json"
    profile = data / "state.json"

    def apply(state: dict) -> None:
        if watch_yes is not None:
            state["watch_yes"] = watch_yes
        if paused is not None:
            state["paused"] = paused

    if trip.is_file() or watch_yes is not None or paused is not None:
        mutate_json(trip, apply)
    if watch_yes is not None and profile.is_file():
        mutate_json(profile, apply)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        slug = require_slug(args.slug)
    except SystemExit:
        print("invalid slug", file=sys.stderr)
        return 2
    data = Path(args.data)
    jobs_path = Path(args.jobs)
    name = f"fare-hawk-watch-{slug}"
    if not any((args.yes, args.no, args.stop, args.booked, args.booked_stop)):
        return 0
    if args.no and not any((args.yes, args.stop, args.booked, args.booked_stop)):
        set_watch(data, slug, watch_yes=False)
        return 0
    if args.stop or args.booked_stop:
        jobs = [job for job in load_jobs(jobs_path) if job.get("name") != name]
        save_jobs(jobs_path, jobs)
        set_watch(data, slug, watch_yes=False, paused=False)
        print("Watch stopped.")
        return 0
    if args.booked and not args.yes:
        jobs = load_jobs(jobs_path)
        for job in jobs:
            if job.get("name") == name:
                job["paused"] = True
        save_jobs(jobs_path, jobs)
        set_watch(data, slug, paused=True)
        print("Stop the price watch?")
        return 0
    if args.yes:
        jobs = [job for job in load_jobs(jobs_path) if job.get("name") != name]
        jobs.append(
            {
                "name": name,
                "schedule": schedule_for(args.times),
                "timezone": args.tz or DEFAULT_TZ,
                "paused": False,
            }
        )
        # Keep unrelated jobs in their original order, with this name once.
        save_jobs(jobs_path, jobs)
        set_watch(data, slug, watch_yes=True, paused=False)
        print(name)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
