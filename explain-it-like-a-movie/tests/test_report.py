#!/usr/bin/env python3
"""A3 — report edited in place; status flips; failure writes next step."""

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


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return subprocess.run(
        args,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        cwd=str(ROOT),
        env=env,
        stdin=subprocess.DEVNULL,
        timeout=60,
    )


def test_report_in_place() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        script_path = tmp / "script.json"
        built = run(
            [
                sys.executable,
                str(SCRIPTS / "script_build.py"),
                "--facts",
                str(FIXTURES / "facts.json"),
                "--out",
                str(script_path),
            ]
        )
        assert built.returncode == 0, built.stderr
        out = tmp / "movies" / "bee-dance"
        first = run(
            [
                sys.executable,
                str(SCRIPTS / "report.py"),
                "--script",
                str(script_path),
                "--out",
                str(out),
                "--status",
                "rendering",
            ]
        )
        assert first.returncode == 0, first.stderr
        md = out / "movie.md"
        html = out / "movie.html"
        assert md.is_file() and html.is_file()
        text = md.read_text(encoding="utf-8")
        assert "Status: Video rendering" in text
        assert "Made with AI" in text
        assert "Try Hermes: Explain It Like a Movie by SMF Works" in text
        assert "[1]" in text
        md_path = str(md)
        html_path = str(html)

        video = run(
            [
                sys.executable,
                str(SCRIPTS / "report.py"),
                "--script",
                str(script_path),
                "--out",
                str(out),
                "--status",
                "video",
                "--video",
                str(out / "movie.mp4"),
            ]
        )
        assert video.returncode == 0, video.stderr
        text = md.read_text(encoding="utf-8")
        assert "Video rendering" not in text
        assert "movie.mp4" in text
        assert str(md) == md_path
        assert str(html) == html_path
        assert md.is_file() and html.is_file()

        fail_dir = tmp / "movies" / "bee-fail"
        fail = run(
            [
                sys.executable,
                str(SCRIPTS / "report.py"),
                "--script",
                str(script_path),
                "--out",
                str(fail_dir),
                "--status",
                "failure",
                "--error",
                "TTS is missing.",
                "--next",
                "Install espeak-ng, then rerun movie-produce.",
            ]
        )
        assert fail.returncode == 0, fail.stderr
        fail_text = (fail_dir / "movie.md").read_text(encoding="utf-8")
        assert "Render failed" in fail_text
        assert "TTS is missing" in fail_text
        assert "Install espeak-ng" in fail_text
        assert "Next step" in fail_text


def main() -> None:
    test_report_in_place()
    print("A3 PASS")


if __name__ == "__main__":
    main()
