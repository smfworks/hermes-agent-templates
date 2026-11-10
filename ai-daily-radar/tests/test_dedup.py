#!/usr/bin/env python3
"""A4 — URL variants, same-story skip, material Update:, ledger after delivery."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from helpers import NOW, candidate, make_env, run_script, write_fixture
from ledger import normalize_url, same_story


def test_dedup() -> None:
    a = "https://example.com/en-us/launch?utm_source=x"
    b = "https://www.example.com/launch/"
    assert normalize_url(a) == normalize_url(b)

    old = candidate("same", vendor="Acme", product="Model", event_type="launch")
    old["at"] = "2026-11-04T12:00:00Z"
    new = candidate("same2", vendor="Acme", product="Model", event_type="launch")
    assert same_story(old, new, NOW)

    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = tmp / "data"
        data.mkdir()
        env = make_env(tmp)
        first = write_fixture(tmp / "first.json", [candidate("s1", vendor="Acme", product="M", event_type="launch")])
        r1 = run_script(
            "brief.py",
            ["--data", str(data), "--fixtures", str(first), "--now", NOW],
            env,
        )
        assert r1.returncode == 0, r1.stderr
        ledger = (data / "ledger.jsonl").read_text(encoding="utf-8").strip()
        assert ledger

        repeat = write_fixture(
            tmp / "repeat.json",
            [candidate("s1b", vendor="Acme", product="M", event_type="launch")],
        )
        r2 = run_script(
            "brief.py",
            ["--data", str(data), "--fixtures", str(repeat), "--now", "2026-11-07T12:00:00Z"],
            env,
        )
        assert r2.returncode == 0, r2.stderr
        # Saturday - not friday wrap. Repeat skipped → silent or no new item
        lines = [line for line in (data / "ledger.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(lines) == 1

        update = write_fixture(
            tmp / "upd.json",
            [
                candidate(
                    "s1c",
                    vendor="Acme",
                    product="M",
                    event_type="launch",
                    usable_now=True,
                    availability="ga",
                    headline="Model is generally available",
                )
            ],
        )
        # mark old as announced in ledger by rewriting
        row = json.loads(lines[0])
        row["tag"] = "Announced"
        row["availability"] = "announced"
        (data / "ledger.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
        r3 = run_script(
            "brief.py",
            ["--data", str(data), "--fixtures", str(update), "--now", "2026-11-08T12:00:00Z"],
            env,
        )
        assert r3.returncode == 0, r3.stderr
        assert "Update:" in r3.stdout

        deferred = tmp / "def"
        deferred.mkdir()
        hold = write_fixture(tmp / "hold.json", [candidate("z")])
        r4 = run_script(
            "brief.py",
            ["--data", str(deferred), "--fixtures", str(hold), "--now", NOW, "--no-deliver"],
            env,
        )
        assert r4.returncode == 0, r4.stderr
        assert not (deferred / "ledger.jsonl").exists() or not (deferred / "ledger.jsonl").read_text().strip()
    print("A4 PASS")


if __name__ == "__main__":
    test_dedup()
