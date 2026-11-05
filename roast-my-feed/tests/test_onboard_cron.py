#!/usr/bin/env python3
"""A1 — SPEC §8.1 intro, handle strip, audit before the weekly offer, cron only on yes."""

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
    TZ,
    assert_no_live_hermes,
    make_env,
    read_state,
    run_audit,
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


def test_a1() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        data, jobs_path = seed(tmp)
        env, marker = write_hermes(tmp)
        jobs_before = jobs_path.read_bytes()

        intro = run_script("onboard.py", ["--data", str(data), "--step", "intro"], env)
        assert intro.returncode == 0, intro.stderr
        assert intro.stdout.strip() == INTRO, intro.stdout
        assert intro.stdout.count("?") == 1
        state = read_state(data)
        assert state["setup_step"] == "intro_done"
        assert state["sentinel"] == "keep-me"
        assert not (data / "history.jsonl").exists()
        assert not (data / "roast").exists()
        assert_not_invoked(marker)

        handles = (
            ("@OtherName", "OtherName"),
            ("https://x.com/fixtureuser", "fixtureuser"),
            ("https://twitter.com/fixtureuser/status/123456789", "fixtureuser"),
            ("https://www.x.com/fixtureuser/", "fixtureuser"),
            ("https://mobile.twitter.com/fixtureuser?lang=en", "fixtureuser"),
            ("HTTP://X.com/fixtureuser", "fixtureuser"),
            ("@fixtureuser", "fixtureuser"),
        )
        for raw_handle, expected in handles:
            saved = run_script(
                "onboard.py",
                ["--data", str(data), "--step", "handle", "--handle", raw_handle],
                env,
            )
            assert saved.returncode == 0, saved.stderr
            state = read_state(data)
            assert state["handle"] == expected, (raw_handle, state)
            assert state["sentinel"] == "keep-me"
            assert state.get("cron_installed") is not True
        assert not (data / "history.jsonl").exists()
        assert not (data / "roast").exists()
        assert jobs_path.read_bytes() == jobs_before
        assert_not_invoked(marker)

        audit = run_audit(data, "fixtureuser", FIXTURES / "feed.json", env)
        assert audit.returncode == 0, audit.stderr
        assert "roast/fixtureuser/roast.md" in audit.stdout.replace("\\", "/")
        assert FOOTER in audit.stdout
        report = data / "roast" / "fixtureuser" / "roast.md"
        html = data / "roast" / "fixtureuser" / "roast.html"
        assert report.is_file() and html.is_file()
        assert FOOTER in report.read_text(encoding="utf-8")
        assert FOOTER in html.read_text(encoding="utf-8")
        history = (data / "history.jsonl").read_text(encoding="utf-8").splitlines()
        assert len([line for line in history if line.strip()]) == 1
        state = read_state(data)
        assert state["handle"] == "fixtureuser"
        assert state["sentinel"] == "keep-me"
        assert state.get("cron_installed") is not True
        assert jobs_path.read_bytes() == jobs_before
        assert_not_invoked(marker)

        offer = run_script(
            "onboard.py",
            ["--data", str(data), "--step", "weekly-offer"],
            env,
        )
        assert offer.returncode == 0, offer.stderr
        offered = offer.stdout.casefold()
        assert "monday" in offered, offer.stdout
        assert "week" in offered, offer.stdout
        assert "?" in offer.stdout
        assert jobs_path.read_bytes() == jobs_before
        assert read_state(data).get("cron_installed") is not True
        assert_not_invoked(marker)

        no_yes = run_script(
            "install_cron.py",
            ["--data", str(data), "--jobs", str(jobs_path)],
            env,
        )
        assert no_yes.returncode == 0, no_yes.stderr
        assert jobs_path.read_bytes() == jobs_before
        assert_not_invoked(marker)

        yes = run_script(
            "install_cron.py",
            ["--data", str(data), "--jobs", str(jobs_path), "--yes"],
            env,
        )
        assert yes.returncode == 0, yes.stderr
        assert_not_invoked(marker)
        assert_job(jobs_path, "America/New_York")
        state = read_state(data)
        assert state["tz"] == "America/New_York"
        assert state["sentinel"] == "keep-me"
        assert state["handle"] == "fixtureuser"

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
        assert read_state(data)["sentinel"] == "keep-me"
        assert_not_invoked(marker)

    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = tmp / "data"
        data.mkdir()
        env, marker = write_hermes(tmp)
        audit = run_audit(data, "FixtureUser", FIXTURES / "feed.json", env)
        assert audit.returncode == 0, audit.stderr
        assert (data / "roast" / "FixtureUser" / "roast.md").is_file()
        assert not (data / "roast" / "fixtureuser").exists()
        assert "roast/FixtureUser/roast.md" in audit.stdout.replace("\\", "/")
        assert_not_invoked(marker)
        assert_no_live_hermes(tmp)
    print("A1 PASS")


def assert_job(path: Path, timezone: str) -> None:
    jobs = json.loads(path.read_text(encoding="utf-8"))["jobs"]
    assert len(jobs) == 2, [job["id"] for job in jobs]
    by_id = {job["id"]: job for job in jobs}
    assert set(by_id) == {"unrelated-job", "roast-weekly-checkin"}, [job["id"] for job in jobs]
    job = by_id["roast-weekly-checkin"]
    assert job["timezone"] == timezone, job
    assert job["no_agent"] is True, job
    script = str(job["script"]).replace("\\", "/")
    assert script == "scripts/audit.py" or script.endswith("/scripts/audit.py"), job
    parts = job["schedule"]["expr"].split()
    assert len(parts) == 5, job
    minute, hour, dom, month, dow = parts
    assert minute in {"0", "00"}, job
    assert hour in {"9", "09"}, job
    assert (dom, month, dow) == ("*", "*", "1"), job


def main() -> None:
    test_a1()


if __name__ == "__main__":
    main()
