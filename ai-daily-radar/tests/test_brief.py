#!/usr/bin/env python3
"""A2/A5 — cap, silent empty, Quick for two, Friday wrap, HTML escape."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from helpers import FOOTER, NOW, candidate, make_env, run_script, write_fixture


def run_brief(data: Path, fixture: Path, env, extra=None):
    args = ["--data", str(data), "--fixtures", str(fixture), "--now", NOW, "--tz", "America/New_York"]
    if extra:
        args.extend(extra)
    return run_script("brief.py", args, env)


def test_brief() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = tmp / "data"
        data.mkdir()
        (data / "profile.json").write_text(json.dumps({"stack": "coding", "style": "standard"}), encoding="utf-8")
        env = make_env(tmp)

        empty = write_fixture(tmp / "empty.json", [])
        silent = run_brief(data, empty, env)
        assert silent.returncode == 0, silent.stderr
        assert silent.stdout.strip() == ""
        runs = (data / "runs.jsonl").read_text(encoding="utf-8")
        assert "true" in runs  # silent
        assert not (data / "briefs").exists() or not any((data / "briefs").iterdir())

        two = write_fixture(
            tmp / "two.json",
            [candidate("a"), candidate("b", vendor="Beta", product="b")],
        )
        out = run_brief(data, two, env)
        assert out.returncode == 0, out.stderr
        assert "[Shipped]" in out.stdout
        assert FOOTER in out.stdout
        md = (data / "briefs" / "2026-11-06.md").read_text(encoding="utf-8")
        assert md.splitlines()[0].startswith("# AI Daily Radar")

        twelve = [candidate(f"c{i}", stack_match=["coding"] if i < 8 else ["other"]) for i in range(12)]
        big = write_fixture(tmp / "twelve.json", twelve)
        data2 = tmp / "data2"
        data2.mkdir()
        (data2 / "profile.json").write_text(json.dumps({"stack": "coding"}), encoding="utf-8")
        many = run_brief(data2, big, env)
        assert many.returncode == 0, many.stderr
        body = (data2 / "briefs" / "2026-11-06.md").read_text(encoding="utf-8")
        tags = body.count("Tag:") + body.count("[Shipped]")
        assert body.count("https://example.com/") <= 14
        # at most 7 items: Try this today once, seven headlines
        assert body.count("**Try this today:**") == 1

        wrap = write_fixture(
            tmp / "fri.json",
            [candidate("w1"), candidate("w2", vendor="Beta", product="w2")],
            week_lines=["Shift one", "Shift two", "Shift three", "Shift four", "Shift five"],
            ignore={"headline": "Hype launch", "reason": "No primary method."},
            archive=[{"tag": "Shipped", "headline": "Change w1 is out"}],
            wrap_headline="The biggest shift this week was a coding-agent launch.",
        )
        data3 = tmp / "data3"
        data3.mkdir()
        fri = run_brief(data3, wrap, env)
        assert fri.returncode == 0, fri.stderr
        assert "biggest shift" in fri.stdout.casefold()
        week = (data3 / "wraps" / "2026-W45.md").read_text(encoding="utf-8")
        assert "## The week in 5 lines" in week
        assert "## One thing I'd ignore" in week
        daily = (data3 / "briefs" / "2026-11-06.md").read_text(encoding="utf-8")
        assert "## The week in 5 lines" not in daily
        html = (data3 / "briefs" / "2026-11-06.html").read_text(encoding="utf-8")
        assert "<script" not in html.casefold()

        nasty = candidate(
            "html",
            headline='Acme, "quoted"',
            what_changed="<script>alert(1)</script>",
            primary={"url": "javascript:alert(1)", "title": "bad"},
        )
        # unsafe primary is dropped by validate
        data4 = tmp / "data4"
        data4.mkdir()
        bad = write_fixture(tmp / "bad.json", [nasty, candidate("ok")])
        ok = run_brief(data4, bad, env)
        assert ok.returncode == 0, ok.stderr
        html2 = (data4 / "briefs" / "2026-11-06.html").read_text(encoding="utf-8")
        assert "javascript:" not in html2.casefold()
        assert "<script" not in html2.casefold()
    print("A2A5 PASS")


if __name__ == "__main__":
    test_brief()
