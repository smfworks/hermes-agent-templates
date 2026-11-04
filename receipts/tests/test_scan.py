#!/usr/bin/env python3
"""A2 / A4 — SPEC §10.2 classification and §10.4 unknown/estimate."""

from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

from helpers import FIXTURES, NOW, make_env, run_script

COLUMNS = [
    "service",
    "plan",
    "amount",
    "currency",
    "cadence",
    "last_charge",
    "next_renewal",
    "renewal_is_estimate",
    "status",
    "kind",
    "source_msg_ids",
    "evidence_quote",
    "notes",
]


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == COLUMNS, reader.fieldnames
        return list(reader)


def load_findings(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def test_a2_a4() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = tmp / "data"
        data.mkdir()
        env = make_env(tmp)
        result = run_script(
            "scan.py",
            [
                "--data",
                str(data),
                "--inbox",
                str(FIXTURES),
                "--backend",
                "fixtures",
                "--now",
                NOW,
            ],
            env,
        )
        assert result.returncode == 0, result.stderr
        rows = load_csv(data / "subscriptions.csv")
        by_key = {(r["service"].casefold(), r["plan"].casefold()): r for r in rows}

        services = {r["service"].casefold() for r in rows}
        assert "netflix" in services
        assert "spotify" in services
        assert "adobe" in services
        assert "disney+" in services or "disney" in services
        assert "dropbox" in services
        assert "github" in services
        assert "cloudsync" in services
        assert "widgetpro" in services
        assert any("times" in s or s == "nyt" or "new york times" in s for s in services)
        assert any("aws" in s or "amazon web services" in s for s in services)

        joined = " ".join(r["service"].casefold() + " " + r["plan"].casefold() for r in rows)
        assert "promo" not in joined
        assert "deals" not in joined
        assert "wireless mouse" not in joined
        assert not any("one-time" in (r["notes"] + r["plan"] + r["service"]).casefold() and "amazon.com" in r["service"].casefold() for r in rows)
        assert not any("mouse" in r["plan"].casefold() for r in rows)

        dropbox_plans = {r["plan"].casefold() for r in rows if r["service"].casefold() == "dropbox"}
        assert "plus" in dropbox_plans
        assert "family" in dropbox_plans

        plus = by_key[("dropbox", "plus")]
        assert plus["amount"] in {"12.99", "12.990"} or plus["amount"].startswith("12.99")
        aws_rows = [r for r in rows if "aws" in r["service"].casefold() or "amazon web" in r["service"].casefold()]
        assert aws_rows, rows
        assert all(r["kind"] == "usage" for r in aws_rows)
        assert any(r["amount"].startswith("70") for r in aws_rows)

        disney = [r for r in rows if "disney" in r["service"].casefold()][0]
        assert disney["status"] == "trial"

        nyt = [r for r in rows if "times" in r["service"].casefold() or r["service"].casefold() in {"nyt"}][0]
        assert nyt["status"] == "unknown"

        cloud = [r for r in rows if "cloudsync" in r["service"].casefold()][0]
        assert cloud["amount"] in {"", "unknown"}

        widget = [r for r in rows if "widgetpro" in r["service"].casefold()][0]
        assert widget["renewal_is_estimate"] == "y"
        assert widget["amount"].startswith("8")

        findings = load_findings(data / "findings.jsonl")
        assert findings, "A2: no findings"
        types = {f["type"] for f in findings}
        assert "price_increase" in types
        assert "duplicate" in types
        assert "usage_spike" in types
        assert "trial_bill" in types or "trial" in types
        assert "lapsed" in types
        for finding in findings:
            evidence = finding["evidence"]
            assert evidence.get("sender"), finding
            assert evidence.get("date"), finding
            assert evidence.get("subject") is not None, finding
            assert evidence.get("message_id"), finding
            assert evidence.get("quote"), finding

        page = run_script("page.py", ["--data", str(data), "--now", NOW], env)
        assert page.returncode == 0, page.stderr
        report = (data / "money-back.md").read_text(encoding="utf-8")
        assert "unknown — open receipt" in report
        assert "estimate" in report.casefold()
    print("A2 A4 PASS")


def main() -> None:
    test_a2_a4()


if __name__ == "__main__":
    main()
