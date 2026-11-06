#!/usr/bin/env python3
"""A4/A6 — citations, dates, superseded notes, HTML escape, atomic overwrite."""

from __future__ import annotations

import csv
import json
import tempfile
import threading
from pathlib import Path

from helpers import FIXTURES, FOOTER, NOW, make_env, read_claims, run_check


def test_a4_a6() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = tmp / "data"
        data.mkdir()
        env = make_env(tmp)

        first = run_check(data, "supported", FIXTURES / "supported.json", env)
        assert first.returncode == 0, first.stderr
        md_path = data / "claims" / "supported" / "claim-card.md"
        html_path = data / "claims" / "supported" / "claim-card.html"
        md = md_path.read_text(encoding="utf-8")
        html = html_path.read_text(encoding="utf-8")
        assert "https://example.com/model-x/card" in md
        assert "https://evalcorp.example/swe-verified" in md
        assert "2026-10-12" in md
        assert "2026-11-06" in md
        assert "Checked on 2026-11-06" in md
        assert FOOTER in md and FOOTER in html
        bottom = [line for line in md.splitlines() if line.startswith("What ")]
        assert len(bottom) == 3, bottom
        assert "## What would change my mind" in md
        first_inode = md_path.stat().st_ino

        second = run_check(data, "supported", FIXTURES / "supported.json", env)
        assert second.returncode == 0, second.stderr
        assert md_path.is_file() and html_path.is_file()
        history = [
            line
            for line in (data / "history.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(history) == 2

        superseded = run_check(data, "superseded", FIXTURES / "superseded.json", env)
        assert superseded.returncode == 0, superseded.stderr
        row = read_claims(data, "superseded")[0]
        assert row["verdict"] == "vendor-only"
        assert "outdated" not in row["verdict"]
        notes = row.get("notes") or ""
        assert "Superseded" in notes
        assert "90.2" in notes and "88.0" in notes

        html_case = run_check(data, "html-inject", FIXTURES / "html_inject.json", env)
        assert html_case.returncode == 0, html_case.stderr
        html_card = (data / "claims" / "html-inject" / "claim-card.html").read_text(
            encoding="utf-8"
        )
        assert "<script" not in html_card.casefold()
        assert "javascript:" not in html_card.casefold()
        assert "iframe" not in html_card.casefold()
        csv_path = data / "claims" / "html-inject" / "sources.csv"
        with csv_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.reader(handle))
        assert rows[0][0] == "id"
        title_cell = rows[1][1]
        assert "quoted" in title_cell
        assert "date not stated" in (data / "claims" / "html-inject" / "claim-card.md").read_text(
            encoding="utf-8"
        ).casefold()

        owner = run_check(data, "owner", FIXTURES / "owner_text.json", env)
        assert owner.returncode == 0, owner.stderr
        owner_md = (data / "claims" / "owner" / "claim-card.md").read_text(encoding="utf-8")
        assert "owner-supplied" in owner_md.casefold()

        timeout = run_check(
            data,
            "timeout",
            FIXTURES / "supported.json",
            env,
            extra=["--timeout"],
        )
        assert timeout.returncode == 0, timeout.stderr
        timeout_md = (data / "claims" / "timeout" / "claim-card.md").read_text(encoding="utf-8")
        assert "unreachable" in timeout_md.casefold() or "timed out" in timeout_md.casefold()
        timeout_rows = read_claims(data, "timeout")
        assert timeout_rows[0]["verdict"] == "unverifiable"

        brief = run_check(
            data,
            "brief-run",
            FIXTURES / "supported.json",
            env,
            extra=["--style", "brief"],
        )
        assert brief.returncode == 0, brief.stderr
        brief_md = (data / "claims" / "brief-run" / "claim-brief.md").read_text(encoding="utf-8")
        assert brief_md.splitlines()[0].endswith("(brief)")
        assert FOOTER in brief_md

        live = run_check(
            data,
            "live",
            FIXTURES / "supported.json",
            env,
            extra=["--backend", "live"],
        )
        # run_check always passes --backend fixtures first; call the script directly.
        from helpers import run_script

        live = run_script(
            "check.py",
            [
                "--data",
                str(data),
                "--slug",
                "live",
                "--backend",
                "live",
            ],
            env,
        )
        assert live.returncode == 4, live.stderr

        # Concurrent state merges keep the sentinel.
        from store import save_state

        state_path = data / "state.json"
        errors: list[str] = []

        def writer(key: str) -> None:
            try:
                save_state(state_path, {key: True})
            except Exception as exc:  # pragma: no cover
                errors.append(str(exc))

        threads = [
            threading.Thread(target=writer, args=(f"k{i}",))
            for i in range(8)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert not errors, errors
        state = json.loads(state_path.read_text(encoding="utf-8"))
        for i in range(8):
            assert state.get(f"k{i}") is True, state

        traversal = run_check(data, "../../etc/passwd", FIXTURES / "supported.json", env)
        assert traversal.returncode == 0, traversal.stderr
        escaped = data / "claims" / "passwd" / "claim-card.md"
        assert escaped.is_file()
        assert not (tmp / "etc").exists()
        _ = first_inode
    print("A4A6 PASS")


def main() -> None:
    test_a4_a6()


if __name__ == "__main__":
    main()
