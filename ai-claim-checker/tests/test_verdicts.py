#!/usr/bin/env python3
"""A2 — SPEC §8.2 four fixture verdicts. Enum has exactly four values."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from helpers import FIXTURES, VERDICTS, make_env, read_claims, run_check


def verdicts_of(data: Path, slug: str) -> list[str]:
    return [row["verdict"] for row in read_claims(data, slug)]


def test_a2() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = tmp / "data"
        data.mkdir()
        env = make_env(tmp)

        supported = run_check(data, "supported", FIXTURES / "supported.json", env)
        assert supported.returncode == 0, supported.stderr
        assert verdicts_of(data, "supported") == ["supported"]

        vendor = run_check(data, "vendor-only", FIXTURES / "vendor_only.json", env)
        assert vendor.returncode == 0, vendor.stderr
        assert verdicts_of(data, "vendor-only") == ["vendor-only"]

        contradicted = run_check(data, "contradicted", FIXTURES / "contradicted.json", env)
        assert contradicted.returncode == 0, contradicted.stderr
        assert verdicts_of(data, "contradicted") == ["contradicted"]
        card = (data / "claims" / "contradicted" / "claim-card.md").read_text(encoding="utf-8")
        assert "90.2" in card and "71.4" in card

        unverifiable = run_check(data, "unverifiable", FIXTURES / "unverifiable.json", env)
        assert unverifiable.returncode == 0, unverifiable.stderr
        assert verdicts_of(data, "unverifiable") == ["unverifiable"]

        seen = set()
        for slug in ("supported", "vendor-only", "contradicted", "unverifiable"):
            for row in read_claims(data, slug):
                assert row["verdict"] in VERDICTS
                seen.add(row["verdict"])
                assert "outdated" not in row["verdict"]
        assert seen == VERDICTS, seen
    print("A2 PASS")


def main() -> None:
    test_a2()


if __name__ == "__main__":
    main()
