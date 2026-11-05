#!/usr/bin/env python3
"""A2 — URL and PDF fixtures; unsourced claims are cut; captions labeled."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
FIXTURES = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(SCRIPTS))

from fetch_source import write_simple_pdf  # noqa: E402


def run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return subprocess.run(
        args,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        cwd=str(cwd or ROOT),
        env=env,
        stdin=subprocess.DEVNULL,
        timeout=60,
    )


def test_url_and_pdf_and_unsourced() -> None:
    html_path = FIXTURES / "page.html"
    facts_path = FIXTURES / "facts.json"
    html = html_path.read_text(encoding="utf-8")
    assert "secret contract" in html

    url_fetch = run(
        [
            sys.executable,
            str(SCRIPTS / "fetch_source.py"),
            "--file",
            str(html_path),
            "--url",
            "https://example.test/bees",
            "--title",
            "Bee dance notes",
            "--n",
            "1",
            "--now",
            "2026-11-05",
        ]
    )
    assert url_fetch.returncode == 0, url_fetch.stderr
    url_rec = json.loads(url_fetch.stdout)
    assert url_rec["url"] == "https://example.test/bees"
    assert url_rec["fetched"] == "2026-11-05"
    assert "waggle dance" in url_rec["text"]
    assert "<p>" not in url_rec["text"]

    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        pdf_path = tmp / "bees.pdf"
        write_simple_pdf(pdf_path, "A forager figure-eights on the comb.")
        pdf_fetch = run(
            [
                sys.executable,
                str(SCRIPTS / "fetch_source.py"),
                "--pdf",
                str(pdf_path),
                "--url",
                "https://example.test/bees.pdf",
                "--title",
                "Comb notes",
                "--n",
                "2",
                "--now",
                "2026-11-05",
            ]
        )
        assert pdf_fetch.returncode == 0, pdf_fetch.stderr
        pdf_rec = json.loads(pdf_fetch.stdout)
        assert "figure-eights" in pdf_rec["text"]
        assert pdf_rec["fetched"] == "2026-11-05"

        out = tmp / "script.json"
        built = run(
            [
                sys.executable,
                str(SCRIPTS / "script_build.py"),
                "--facts",
                str(facts_path),
                "--out",
                str(out),
            ]
        )
        assert built.returncode == 0, built.stderr
        script = json.loads(out.read_text(encoding="utf-8"))

    blob = json.dumps(script)
    assert "secret contract" not in blob
    assert "hidden agency" not in blob
    for line in script["lines"]:
        assert line.get("cite"), line
        marker = f"[{line['cite']}]"
        assert marker == f"[{int(line['cite'])}]", line
        assert int(line["cite"]) in {1, 2}
    assert "Made with AI" in script["captions"]["x"]
    assert "Made with AI" in script["captions"]["tiktok"]
    assert script["lines"][0]["text"].rstrip().endswith("?")


def main() -> None:
    test_url_and_pdf_and_unsourced()
    print("A2 PASS")


if __name__ == "__main__":
    main()
