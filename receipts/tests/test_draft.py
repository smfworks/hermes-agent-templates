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


def test_draft_service_traversal_contained() -> None:
    """hsf_c1ee8922: a separator-bearing --service must not escape data/drafts."""
    import subprocess
    import sys
    from pathlib import Path

    here = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = tmp / "data"
        data.mkdir()
        r = subprocess.run(
            [sys.executable, str(here.parent / "scripts" / "draft.py"),
             "--service", "../../evil", "--data", str(data)],
            capture_output=True, text=True, timeout=60, cwd=str(here.parent / "scripts"))
        assert r.returncode == 0
        assert (data / "drafts" / "unknown-service-cancel.eml").exists()
        assert not (tmp / "evil").exists() and not (data / "evil").exists()


def test_draft_crlf_header_neutralized() -> None:
    """hsf_01f59bcf: CR/LF in --service must not inject headers into the .eml."""
    import subprocess
    import sys
    from pathlib import Path

    here = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = tmp / "data"
        data.mkdir()
        r = subprocess.run(
            [sys.executable, str(here.parent / "scripts" / "draft.py"),
             "--service", "x\nBcc: a@b", "--data", str(data)],
            capture_output=True, text=True, timeout=60, cwd=str(here.parent / "scripts"))
        assert r.returncode == 0
        eml = (data / "drafts" / "unknown-service-cancel.eml").read_text()
        assert eml.count("To:") == 1
        assert "Bcc:" not in eml
