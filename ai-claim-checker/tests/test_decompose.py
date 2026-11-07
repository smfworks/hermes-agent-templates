#!/usr/bin/env python3
"""A3 — SPEC §8.3 ten-claim cap, not-checkable opinions, mismatch is not proof."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from helpers import FIXTURES, make_env, read_claims, run_check


def test_a3() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = tmp / "data"
        data.mkdir()
        env = make_env(tmp)

        ten = run_check(data, "ten", FIXTURES / "ten_claims.json", env)
        assert ten.returncode == 0, ten.stderr
        claims = read_claims(data, "ten")
        assert len(claims) == 8, [row["id"] for row in claims]
        ids = [row["id"] for row in claims]
        assert "c9" not in ids and "c10" not in ids
        card = (data / "claims" / "ten" / "claim-card.md").read_text(encoding="utf-8")
        assert "Omitted 2" in card
        assert "most beloved" in card
        assert "feels magical" in card
        assert "roadmap" in card.casefold()
        assert "## Not checkable" in card

        mismatch = run_check(data, "mismatch", FIXTURES / "mismatch.json", env)
        assert mismatch.returncode == 0, mismatch.stderr
        row = read_claims(data, "mismatch")[0]
        assert row["verdict"] != "contradicted", row
        assert row["verdict"] != "supported", row
        assert row["verdict"] == "vendor-only", row
        notes = row.get("notes") or ""
        assert "mismatch" in notes.casefold()
        md = (data / "claims" / "mismatch" / "claim-card.md").read_text(encoding="utf-8")
        assert "pass@8" in md or "subset" in md.casefold()
    print("A3 PASS")


def main() -> None:
    test_a3()


if __name__ == "__main__":
    main()
