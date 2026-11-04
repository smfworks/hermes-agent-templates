#!/usr/bin/env python3
"""A1 — SPEC §10.1 install_cron.py --skip writes two tz-aware jobs."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install_cron.py"


def make_env(tmp: Path) -> dict[str, str]:
    env = os.environ.copy()
    home = tmp / "home"
    home.mkdir(exist_ok=True)
    env["HOME"] = str(home)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def run(data: Path, jobs: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    assert SCRIPT.is_file(), f"A1: missing {SCRIPT}"
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--data",
            str(data),
            "--jobs",
            str(jobs),
            "--skip",
        ],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        cwd=str(ROOT),
        env=env,
        stdin=subprocess.DEVNULL,
        timeout=30,
    )


def load_jobs(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict), "A1: jobs file is a JSON object"
    jobs = data["jobs"]
    assert isinstance(jobs, list), "A1: jobs is a list"
    return jobs


def cron_fields(job: dict) -> list[str]:
    schedule = job.get("schedule")
    assert isinstance(schedule, dict), f"A1: {job.get('id')} schedule is an object"
    expr = schedule.get("expr")
    assert isinstance(expr, str), f"A1: {job.get('id')} schedule.expr missing"
    parts = expr.split()
    assert len(parts) == 5, f"A1: {job.get('id')} expr {expr!r}"
    return parts


def test_a1_skip_writes_two_jobs() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = tmp / "data"
        data.mkdir()
        (data / "state.json").write_text(
            json.dumps({"streak": 3, "sentinel": "keep-me"}),
            encoding="utf-8",
        )
        jobs_path = tmp / "jobs.json"
        jobs_path.write_text(
            json.dumps({"jobs": [{"id": "unrelated-job", "name": "keep"}]}),
            encoding="utf-8",
        )
        marker = tmp / "hermes-invoked"
        bindir = tmp / "bin"
        bindir.mkdir()
        hermes = bindir / "hermes"
        hermes.write_text(
            f"#!/bin/sh\necho invoked > {shlex.quote(str(marker))}\nexit 99\n",
            encoding="utf-8",
        )
        hermes.chmod(0o755)
        env = make_env(tmp)
        env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")

        first = run(data, jobs_path, env)
        assert first.returncode == 0, first.stderr
        assert not marker.exists(), "A1: hermes was invoked"
        assert_jobs(jobs_path)
        assert_state(data)

        second = run(data, jobs_path, env)
        assert second.returncode == 0, second.stderr
        assert not marker.exists(), "A1: hermes was invoked on the second run"
        assert_jobs(jobs_path)
        assert_state(data)
        assert not (tmp / "home" / ".hermes").exists(), "A1: wrote a live Hermes home"
    print("A1 PASS")


def assert_jobs(path: Path) -> None:
    jobs = load_jobs(path)
    by_id = {job["id"]: job for job in jobs}
    assert by_id.keys() >= {"unrelated-job", "daily-wisdom-sitting", "daily-wisdom-weekly"}
    assert len(jobs) == 3, [job["id"] for job in jobs]
    sitting = by_id["daily-wisdom-sitting"]
    weekly = by_id["daily-wisdom-weekly"]
    for job in (sitting, weekly):
        assert job.get("timezone") == "America/New_York", job
    sit_min, sit_hour, sit_dom, sit_mon, sit_dow = cron_fields(sitting)
    assert sit_min == "0", sitting
    assert sit_hour in {"8", "08"}, sitting
    assert (sit_dom, sit_mon, sit_dow) == ("*", "*", "*"), sitting
    week_min, week_hour, week_dom, week_mon, week_dow = cron_fields(weekly)
    assert (week_min, week_hour, week_dom, week_mon) == ("0", "18", "*", "*"), weekly
    assert week_dow in {"0", "7"}, weekly
    assert (ROOT / "scripts" / "cron_sitting.sh").is_file(), "A1: missing cron_sitting.sh"
    assert (ROOT / "scripts" / "cron_weekly.sh").is_file(), "A1: missing cron_weekly.sh"
    sitting_script = sitting.get("script")
    weekly_script = weekly.get("script")
    assert sitting_script in {"cron_sitting.sh", "scripts/cron_sitting.sh"}, sitting
    assert weekly_script in {"cron_weekly.sh", "scripts/cron_weekly.sh"}, weekly


def assert_state(data: Path) -> None:
    state = json.loads((data / "state.json").read_text(encoding="utf-8"))
    assert isinstance(state, dict), state
    assert state.get("tz") == "America/New_York", state
    prefs = state.get("prefs")
    assert isinstance(prefs, dict), state
    assert prefs.get("rotation") == "full", prefs
    assert state.get("streak") == 3, state
    assert state.get("sentinel") == "keep-me", state


def main() -> None:
    test_a1_skip_writes_two_jobs()


if __name__ == "__main__":
    main()
