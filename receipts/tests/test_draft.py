#!/usr/bin/env python3
"""A6 — SPEC §10.6 cancel help and drafts. Never sent."""

from __future__ import annotations

import tempfile
from pathlib import Path

from helpers import make_env, run_script


def test_a6() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = tmp / "data"
        data.mkdir()
        env = make_env(tmp)
        help_result = run_script("cancel_help.py", ["--service", "Netflix"], env)
        assert help_result.returncode == 0, help_result.stderr
        out = help_result.stdout
        assert "http" in out.casefold(), out
        assert "password" not in out.casefold(), out

        draft = run_script(
            "draft.py",
            ["--data", str(data), "--service", "Netflix", "--kind", "cancel"],
            env,
        )
        assert draft.returncode == 0, draft.stderr
        assert draft.stdout.strip(), draft.stdout
        lowered = draft.stdout.casefold()
        assert "sent" not in lowered
        files = list((data / "drafts").glob("*.eml"))
        assert files, "A6: no .eml draft"
        text = files[0].read_text(encoding="utf-8")
        assert "To:" in text or "to:" in text.casefold()
        assert "Subject:" in text or "subject:" in text.casefold()
        assert files[0].read_bytes()  # body present

        refund = run_script(
            "draft.py",
            ["--data", str(data), "--service", "Netflix", "--kind", "refund"],
            env,
        )
        assert refund.returncode == 0, refund.stderr
        refund_files = list((data / "drafts").glob("*.eml"))
        assert len(refund_files) >= 2
    print("A6 PASS")


def main() -> None:
    test_a6()


if __name__ == "__main__":
    main()
