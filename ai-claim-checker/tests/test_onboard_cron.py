#!/usr/bin/env python3
"""A1 — SPEC §8.1 intro, one question at a time, claim interrupts, cron only on yes."""

from __future__ import annotations

import json
import os
import shlex
import tempfile
from pathlib import Path

from helpers import (
    FIXTURES,
    FOOTER,
    INTRO,
    assert_no_live_hermes,
    make_env,
    read_state,
    run_check,
    run_script,
)


def write_hermes(tmp: Path) -> tuple[dict[str, str], Path]:
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


def seed(tmp: Path) -> tuple[Path, Path]:
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
    return data, jobs_path


def assert_not_invoked(marker: Path) -> None:
    assert not marker.exists(), "A1: hermes was invoked"


def assert_job(path: Path, timezone: str) -> None:
    jobs = json.loads(path.read_text(encoding="utf-8"))["jobs"]
    by_id = {job["id"]: job for job in jobs}
    assert set(by_id) == {"unrelated-job", "verity-weekly-recheck"}, [job["id"] for job in jobs]
    job = by_id["verity-weekly-recheck"]
    assert job["timezone"] == timezone, job
    assert job["no_agent"] is True, job
    script = str(job["script"]).replace("\\", "/")
    assert script == "scripts/weekly.py" or script.endswith("/scripts/weekly.py"), job
    parts = job["schedule"]["expr"].split()
    assert len(parts) == 5, job
    minute, hour, dom, month, dow = parts
    assert minute in {"0", "00"}, job
    assert hour in {"8", "08"}, job
    assert (dom, month, dow) == ("*", "*", "1"), job


def test_a1() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        data, jobs_path = seed(tmp)
        env, marker = write_hermes(tmp)
        jobs_before = jobs_path.read_bytes()

        intro = run_script("onboard.py", ["--data", str(data), "--step", "intro"], env)
        assert intro.returncode == 0, intro.stderr
        assert intro.stdout.strip() == INTRO, intro.stdout
        assert intro.stdout.count("?") == 0
        state = read_state(data)
        assert state["setup_step"] == "intro_done"
        assert state["sentinel"] == "keep-me"
        assert_not_invoked(marker)

        focus_q = run_script("onboard.py", ["--data", str(data), "--step", "focus"], env)
        assert focus_q.returncode == 0, focus_q.stderr
        assert focus_q.stdout.count("?") == 1
        assert "benchmarks" in focus_q.stdout.casefold()

        focus = run_script(
            "onboard.py",
            ["--data", str(data), "--step", "focus", "--answer", "benchmarks"],
            env,
        )
        assert focus.returncode == 0, focus.stderr
        assert read_state(data)["focus"] == "benchmarks"
        assert read_state(data)["sentinel"] == "keep-me"

        interrupted = run_script(
            "onboard.py",
            [
                "--data",
                str(data),
                "--step",
                "evaluators",
                "--claim",
                "Model X scores 90.2 on SWE-bench Verified",
            ],
            env,
        )
        assert interrupted.returncode == 0, interrupted.stderr
        assert "check it now" in interrupted.stdout.casefold()
        assert read_state(data)["setup_interrupted"] is True
        assert jobs_path.read_bytes() == jobs_before

        check = run_check(data, "model-x-swe", FIXTURES / "supported.json", env)
        assert check.returncode == 0, check.stderr
        card = data / "claims" / "model-x-swe" / "claim-card.md"
        html = data / "claims" / "model-x-swe" / "claim-card.html"
        assert card.is_file() and html.is_file()
        assert FOOTER in card.read_text(encoding="utf-8")
        assert FOOTER in html.read_text(encoding="utf-8")
        assert "claim-card.md" in check.stdout.replace("\\", "/")
        assert jobs_path.read_bytes() == jobs_before
        assert read_state(data).get("cron_installed") is not True

        style_q = run_script("onboard.py", ["--data", str(data), "--step", "style"], env)
        assert style_q.returncode == 0, style_q.stderr
        assert style_q.stdout.count("?") == 1
        style = run_script(
            "onboard.py",
            ["--data", str(data), "--step", "style", "--answer", "brief"],
            env,
        )
        assert style.returncode == 0, style.stderr
        assert read_state(data)["style"] == "brief"

        restarted = read_state(data)
        assert restarted["focus"] == "benchmarks"
        assert restarted["style"] == "brief"
        assert restarted["sentinel"] == "keep-me"

        offer = run_script(
            "onboard.py",
            ["--data", str(data), "--step", "weekly-offer"],
            env,
        )
        assert offer.returncode == 0, offer.stderr
        offered = offer.stdout.casefold()
        assert "monday" in offered and "week" in offered
        assert "?" in offer.stdout
        assert jobs_path.read_bytes() == jobs_before

        no_yes = run_script(
            "install_cron.py",
            ["--data", str(data), "--jobs", str(jobs_path)],
            env,
        )
        assert no_yes.returncode == 0, no_yes.stderr
        assert jobs_path.read_bytes() == jobs_before
        assert read_state(data).get("cron_installed") is not True

        yes = run_script(
            "install_cron.py",
            ["--data", str(data), "--jobs", str(jobs_path), "--yes"],
            env,
        )
        assert yes.returncode == 0, yes.stderr
        assert_not_invoked(marker)
        assert_job(jobs_path, "America/New_York")
        assert read_state(data)["tz"] == "America/New_York"
        assert read_state(data)["sentinel"] == "keep-me"

        second = run_script(
            "install_cron.py",
            ["--data", str(data), "--jobs", str(jobs_path), "--yes"],
            env,
        )
        assert second.returncode == 0, second.stderr
        assert_job(jobs_path, "America/New_York")
        assert_not_invoked(marker)
        assert_no_live_hermes(tmp)

    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        data, jobs_path = seed(tmp)
        env, marker = write_hermes(tmp)
        yes = run_script(
            "install_cron.py",
            ["--data", str(data), "--jobs", str(jobs_path), "--yes", "--tz", "America/Chicago"],
            env,
        )
        assert yes.returncode == 0, yes.stderr
        assert_job(jobs_path, "America/Chicago")
        assert read_state(data)["tz"] == "America/Chicago"
        disable = run_script(
            "install_cron.py",
            ["--data", str(data), "--jobs", str(jobs_path), "--disable"],
            env,
        )
        assert disable.returncode == 0, disable.stderr
        jobs = json.loads(jobs_path.read_text(encoding="utf-8"))["jobs"]
        assert [job["id"] for job in jobs] == ["unrelated-job"]
        assert read_state(data)["cron_installed"] is False
        assert_not_invoked(marker)
    print("A1 PASS")


def main() -> None:
    test_a1()


if __name__ == "__main__":
    main()
