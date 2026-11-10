#!/usr/bin/env python3
"""A1 — intro, one question, persist, cron only on yes."""

from __future__ import annotations

import json
import os
import shlex
import tempfile
from pathlib import Path

from helpers import INTRO, make_env, run_script


def write_hermes(tmp: Path):
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
    return env, marker


def test_a1() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = tmp / "data"
        data.mkdir()
        env, marker = write_hermes(tmp)
        jobs = tmp / "jobs.json"
        jobs.write_text(json.dumps({"jobs": [{"id": "keep"}]}), encoding="utf-8")
        before = jobs.read_bytes()

        intro = run_script("onboard.py", ["--data", str(data), "--step", "intro"], env)
        assert intro.returncode == 0, intro.stderr
        assert intro.stdout.strip() == INTRO
        assert intro.stdout.count("?") == 0
        assert not marker.exists()

        q = run_script("onboard.py", ["--data", str(data), "--step", "use"], env)
        assert q.returncode == 0, q.stderr
        assert q.stdout.count("?") == 1
        ans = run_script(
            "onboard.py",
            ["--data", str(data), "--step", "use", "--answer", "coding"],
            env,
        )
        assert ans.returncode == 0, ans.stderr
        profile = json.loads((data / "profile.json").read_text(encoding="utf-8"))
        assert profile["use"] == "coding"

        no = run_script("install_cron.py", ["--data", str(data), "--jobs", str(jobs)], env)
        assert no.returncode == 0, no.stderr
        assert jobs.read_bytes() == before

        yes = run_script(
            "install_cron.py",
            ["--data", str(data), "--jobs", str(jobs), "--yes-daily", "--tz", "America/Chicago"],
            env,
        )
        assert yes.returncode == 0, yes.stderr
        loaded = json.loads(jobs.read_text(encoding="utf-8"))
        ids = [job["id"] for job in loaded["jobs"]]
        assert "keep" in ids and "radar-daily-brief" in ids
        daily = next(job for job in loaded["jobs"] if job["id"] == "radar-daily-brief")
        assert daily["timezone"] == "America/Chicago"
        assert daily["no_agent"] is True
        assert not marker.exists()

        yes2 = run_script(
            "install_cron.py",
            ["--data", str(data), "--jobs", str(jobs), "--yes-monthly"],
            env,
        )
        assert yes2.returncode == 0, yes2.stderr
        loaded = json.loads(jobs.read_text(encoding="utf-8"))
        assert len([job for job in loaded["jobs"] if job["id"] == "radar-monthly-tuneup"]) == 1

        off = run_script(
            "install_cron.py",
            ["--data", str(data), "--jobs", str(jobs), "--disable-daily", "--disable-monthly"],
            env,
        )
        assert off.returncode == 0, off.stderr
        loaded = json.loads(jobs.read_text(encoding="utf-8"))
        assert [job["id"] for job in loaded["jobs"]] == ["keep"]
    print("A1 PASS")


if __name__ == "__main__":
    test_a1()
