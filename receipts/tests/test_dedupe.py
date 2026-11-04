#!/usr/bin/env python3
"""A3 — SPEC §10.3 re-scan is idempotent; reminders do not repeat."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from helpers import FIXTURES, NOW, make_env, run_script
from test_scan import load_csv, load_findings


def test_a3() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = tmp / "data"
        data.mkdir()
        env = make_env(tmp)
        args = [
            "--data",
            str(data),
            "--inbox",
            str(FIXTURES),
            "--backend",
            "fixtures",
            "--now",
            NOW,
        ]
        first = run_script("scan.py", args, env)
        assert first.returncode == 0, first.stderr
        csv1 = (data / "subscriptions.csv").read_text(encoding="utf-8")
        findings1 = load_findings(data / "findings.jsonl")
        alerted = {f["id"]: f.get("alerted_at") for f in findings1}

        second = run_script("scan.py", args, env)
        assert second.returncode == 0, second.stderr
        csv2 = (data / "subscriptions.csv").read_text(encoding="utf-8")
        assert csv1 == csv2, "A3: CSV changed on re-scan"
        rows1 = load_csv(data / "subscriptions.csv")
        keys = [(r["service"], r["plan"], r["cadence"]) for r in rows1]
        assert len(keys) == len(set(keys)), keys

        findings2 = load_findings(data / "findings.jsonl")
        ids2 = [f["id"] for f in findings2]
        assert len(ids2) == len(set(ids2))
        for finding in findings2:
            if finding["id"] in alerted:
                assert finding.get("alerted_at") == alerted[finding["id"]], finding

        window_state = json.loads((data / "state.json").read_text(encoding="utf-8"))
        window_state["window"] = 5
        window_state["tz"] = "America/New_York"
        (data / "state.json").write_text(json.dumps(window_state), encoding="utf-8")

        r1 = run_script("remind.py", ["--data", str(data), "--now", NOW], env)
        assert r1.returncode == 0, r1.stderr
        out1 = r1.stdout.strip()
        r2 = run_script("remind.py", ["--data", str(data), "--now", NOW], env)
        assert r2.returncode == 0, r2.stderr
        assert r2.stdout.strip() == "", r2.stdout
        if out1:
            state = json.loads((data / "state.json").read_text(encoding="utf-8"))
            assert state.get("reminded"), state
    print("A3 PASS")


def main() -> None:
    test_a3()


if __name__ == "__main__":
    main()
