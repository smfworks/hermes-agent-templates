#!/usr/bin/env python3
"""A7 — save and weekly are separate. Silent when empty or unchanged."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from helpers import FIXTURES, make_env, read_state, run_check, run_script


def test_weekly() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = tmp / "data"
        data.mkdir()
        env = make_env(tmp)
        jobs_path = tmp / "jobs.json"
        jobs_path.write_text(json.dumps({"jobs": []}), encoding="utf-8")

        silent = run_script("weekly.py", ["--data", str(data)], env)
        assert silent.returncode == 0, silent.stderr
        assert silent.stdout.strip() == ""

        check = run_check(
            data,
            "saved",
            FIXTURES / "vendor_only.json",
            env,
            extra=["--save"],
        )
        assert check.returncode == 0, check.stderr
        saved = json.loads((data / "saved-claims.json").read_text(encoding="utf-8"))
        assert saved["claims"], saved
        assert read_state(data).get("cron_installed") is not True

        still = run_script("weekly.py", ["--data", str(data)], env)
        assert still.returncode == 0, still.stderr
        assert still.stdout.strip() == ""

        yes = run_script(
            "install_cron.py",
            ["--data", str(data), "--jobs", str(jobs_path), "--yes"],
            env,
        )
        assert yes.returncode == 0, yes.stderr
        unchanged = run_script("weekly.py", ["--data", str(data)], env)
        assert unchanged.returncode == 0, unchanged.stderr
        assert unchanged.stdout.strip() == ""

        target = tmp / "moving.json"
        shutil.copy(FIXTURES / "vendor_only.json", target)
        saved["claims"][0]["fixture"] = str(target)
        (data / "saved-claims.json").write_text(
            json.dumps(saved, indent=2) + "\n",
            encoding="utf-8",
        )
        shutil.copy(FIXTURES / "supported.json", target)
        changed = run_script("weekly.py", ["--data", str(data)], env)
        assert changed.returncode == 0, changed.stderr
        assert "verdict changed" in changed.stdout.casefold()

        outage_data = tmp / "outage"
        outage_data.mkdir()
        (outage_data / "state.json").write_text(
            json.dumps({"cron_installed": True}),
            encoding="utf-8",
        )
        shutil.copy(FIXTURES / "outage.json", tmp / "outage.json")
        (outage_data / "saved-claims.json").write_text(
            json.dumps(
                {
                    "claims": [
                        {
                            "text": "EvalCorp lists Model X at 90.2",
                            "verdict": "supported",
                            "fixture": str(tmp / "outage.json"),
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        first_out = run_script("weekly.py", ["--data", str(outage_data)], env)
        assert first_out.returncode == 0, first_out.stderr
        assert "unreachable" in first_out.stdout.casefold()
        second_out = run_script("weekly.py", ["--data", str(outage_data)], env)
        assert second_out.returncode == 0, second_out.stderr
        assert second_out.stdout.strip() == ""
    print("A7 PASS")


def main() -> None:
    test_weekly()


if __name__ == "__main__":
    main()
