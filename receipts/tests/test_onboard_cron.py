#!/usr/bin/env python3
"""A1 — SPEC §10.1 intro, email, scan+report before later questions, skip defaults, cron only on yes."""

from __future__ import annotations

import json
import os
import shlex
import tempfile
from pathlib import Path

from helpers import FIXTURES, NOW, ROOT, make_env, run_script

INTRO_NEEDLE = "I'm Receipts, your money-back bot"
SCAN = ROOT / "scripts" / "scan.py"
ONBOARD = ROOT / "scripts" / "onboard.py"
INSTALL = ROOT / "scripts" / "install_cron.py"


def test_a1() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = tmp / "data"
        data.mkdir()
        (data / "state.json").write_text(
            json.dumps({"sentinel": "keep-me"}),
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

        intro = run_script("onboard.py", ["--data", str(data), "--step", "intro"], env)
        assert intro.returncode == 0, intro.stderr
        assert INTRO_NEEDLE in intro.stdout, intro.stdout
        assert "Gmail or IMAP" in intro.stdout, intro.stdout
        state = json.loads((data / "state.json").read_text(encoding="utf-8"))
        assert state["setup_step"] == "intro_done"
        assert state["sentinel"] == "keep-me"

        email = run_script(
            "onboard.py",
            [
                "--data",
                str(data),
                "--step",
                "email",
                "--backend",
                "fixtures",
                "--account",
                "owner@example.com",
            ],
            env,
        )
        assert email.returncode == 0, email.stderr
        assert "Heads-up" not in email.stdout
        state = json.loads((data / "state.json").read_text(encoding="utf-8"))
        assert state["setup_step"] == "email_done"
        assert "window" not in state

        scan = run_script(
            "onboard.py",
            [
                "--data",
                str(data),
                "--step",
                "scan",
                "--inbox",
                str(FIXTURES),
                "--now",
                NOW,
                "--backend",
                "fixtures",
            ],
            env,
        )
        assert scan.returncode == 0, scan.stderr
        assert (data / "money-back.md").is_file(), "A1: report missing after first scan"
        assert (data / "subscriptions.csv").is_file()
        state = json.loads((data / "state.json").read_text(encoding="utf-8"))
        assert state["setup_step"] == "scanned"
        assert "window" not in state
        assert "Heads-up" in scan.stdout or "heads-up" in scan.stdout.casefold()

        window = run_script(
            "onboard.py",
            ["--data", str(data), "--step", "window", "--skip"],
            env,
        )
        assert window.returncode == 0, window.stderr
        state = json.loads((data / "state.json").read_text(encoding="utf-8"))
        assert state["window"] == 5
        assert state["setup_step"] == "window_done"

        cadence = run_script(
            "onboard.py",
            ["--data", str(data), "--step", "cadence", "--skip"],
            env,
        )
        assert cadence.returncode == 0, cadence.stderr
        state = json.loads((data / "state.json").read_text(encoding="utf-8"))
        assert state["cadence"] == "weekly"
        assert state["tz"] == "America/New_York"
        assert state["setup_step"] == "cadence_done"
        jobs = json.loads(jobs_path.read_text(encoding="utf-8"))["jobs"]
        assert [j["id"] for j in jobs] == ["unrelated-job"]

        no_yes = run_script(
            "install_cron.py",
            ["--data", str(data), "--jobs", str(jobs_path)],
            env,
        )
        assert no_yes.returncode == 0, no_yes.stderr
        jobs = json.loads(jobs_path.read_text(encoding="utf-8"))["jobs"]
        assert [j["id"] for j in jobs] == ["unrelated-job"], jobs
        assert not marker.exists(), "A1: hermes was invoked"

        yes = run_script(
            "install_cron.py",
            ["--data", str(data), "--jobs", str(jobs_path), "--yes"],
            env,
        )
        assert yes.returncode == 0, yes.stderr
        assert not marker.exists(), "A1: hermes was invoked on --yes"
        jobs = json.loads(jobs_path.read_text(encoding="utf-8"))["jobs"]
        by_id = {job["id"]: job for job in jobs}
        assert by_id.keys() >= {
            "unrelated-job",
            "money-back-weekly-scan",
            "money-back-renewal-reminders",
        }
        assert len(jobs) == 3, [job["id"] for job in jobs]
        for job_id in ("money-back-weekly-scan", "money-back-renewal-reminders"):
            assert by_id[job_id].get("timezone") == "America/New_York", by_id[job_id]
        scan_job = by_id["money-back-weekly-scan"]
        parts = scan_job["schedule"]["expr"].split()
        assert len(parts) == 5
        assert parts[0] == "0"
        assert parts[1] in {"9", "09"}
        assert parts[4] in {"0", "7"}
        remind = by_id["money-back-renewal-reminders"]
        rparts = remind["schedule"]["expr"].split()
        assert rparts[0] == "30"
        assert rparts[1] in {"8", "08"}

        second = run_script(
            "install_cron.py",
            ["--data", str(data), "--jobs", str(jobs_path), "--yes"],
            env,
        )
        assert second.returncode == 0, second.stderr
        jobs = json.loads(jobs_path.read_text(encoding="utf-8"))["jobs"]
        assert len(jobs) == 3
        assert not (tmp / "home" / ".hermes").exists()
        assert json.loads((data / "state.json").read_text(encoding="utf-8"))["sentinel"] == "keep-me"
    print("A1 PASS")


def main() -> None:
    test_a1()


if __name__ == "__main__":
    main()
