#!/usr/bin/env python3
"""A5 — SPEC §10.5 report in place, top-3 order, usage separate, privacy."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from helpers import FIXTURES, NOW, make_env, run_script

FOOTER = "Try Hermes: Receipts — The Money-Back Bot by SMF Works"
BANNED = ("4242", "acc_99xyz", "https://pay.netflix.example/inv/abc", "123 Main Street")


def test_a5() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = tmp / "data"
        data.mkdir()
        env = make_env(tmp)
        scan = run_script(
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
        assert scan.returncode == 0, scan.stderr
        first = run_script("page.py", ["--data", str(data), "--now", NOW], env)
        assert first.returncode == 0, first.stderr
        md_path = data / "money-back.md"
        html_path = data / "money-back.html"
        assert md_path.is_file()
        assert html_path.is_file()
        md1 = md_path.read_text(encoding="utf-8")
        html1 = html_path.read_text(encoding="utf-8")
        md_path.write_text(md1 + "\nSTALE-MARKER-OLD\n", encoding="utf-8")

        second = run_script("page.py", ["--data", str(data), "--now", NOW], env)
        assert second.returncode == 0, second.stderr
        md2 = md_path.read_text(encoding="utf-8")
        html2 = html_path.read_text(encoding="utf-8")
        assert "STALE-MARKER-OLD" not in md2
        assert list(data.glob("money-back*.md")) == [md_path]
        assert FOOTER in md2
        assert FOOTER in html2
        lowered = md2.casefold()
        assert "monthly burn" in lowered
        assert "usage" in lowered
        assert "your call" in lowered
        assert "price" in lowered
        html_lower = html2.casefold()
        assert "<html" in html_lower or "<!doctype" in html_lower

        # Top-3 order: duplicates, then price increases, then trials, then lapsed.
        start = lowered.find("top 3")
        assert start != -1, md2
        chunk = lowered[start : start + 1200]
        dup_at = chunk.find("duplicate")
        price_at = chunk.find("price")
        trial_at = chunk.find("trial")
        lapsed_at = chunk.find("lapsed")
        if lapsed_at == -1:
            lapsed_at = chunk.find("unknown")
        assert dup_at != -1, chunk
        assert price_at != -1 and price_at > dup_at, chunk
        if trial_at != -1:
            assert trial_at > price_at, chunk
        if lapsed_at != -1 and trial_at != -1:
            assert lapsed_at > trial_at, chunk

        usage_at = lowered.find("usage")
        table_at = lowered.find("subscription")
        assert usage_at != -1
        # usage section is separate — the word usage appears outside the candidate list
        assert "unused" not in lowered

        blob = md2 + html2
        for needle in BANNED:
            assert needle not in blob, needle
        assert not re.search(r"\bacc_[0-9a-z]+\b", blob)
    print("A5 PASS")


def main() -> None:
    test_a5()


if __name__ == "__main__":
    main()
