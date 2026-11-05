#!/usr/bin/env python3
"""A1/A4 — backend selection, no key in logs, no-key slides render + ffprobe QA."""

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
FAKE_KEY = "movie-test-key-present-xyz"


def run(args: list[str], env: dict[str, str] | None = None, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    merged["PYTHONIOENCODING"] = "utf-8"
    merged["PYTHONUTF8"] = "1"
    return subprocess.run(
        args,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        cwd=str(ROOT),
        env=merged,
        stdin=subprocess.DEVNULL,
        timeout=timeout,
    )


def test_backend_selection() -> None:
    clean = os.environ.copy()
    clean.pop("XAI_API_KEY", None)
    slides = run(
        [sys.executable, str(SCRIPTS / "render.py"), "--print-backend"],
        env={**clean, "XAI_API_KEY": ""},
    )
    assert slides.returncode == 0, slides.stderr
    assert slides.stdout.strip() == "slides", slides.stdout

    imagine = run(
        [sys.executable, str(SCRIPTS / "render.py"), "--print-backend"],
        env={"XAI_API_KEY": FAKE_KEY},
    )
    assert imagine.returncode == 0, imagine.stderr
    assert imagine.stdout.strip() == "imagine", imagine.stdout
    assert FAKE_KEY not in imagine.stdout
    assert FAKE_KEY not in imagine.stderr


def test_key_not_logged_on_fallback_render() -> None:
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
        out = tmp / "movie"
        rendered = run(
            [
                sys.executable,
                str(SCRIPTS / "render.py"),
                "--script",
                str(script_path),
                "--out",
                str(out),
                "--backend",
                "auto",
            ],
            env={"XAI_API_KEY": FAKE_KEY},
            timeout=300,
        )
        blob = rendered.stdout + rendered.stderr
        assert FAKE_KEY not in blob, blob
        assert "backend=imagine" in rendered.stdout
        assert "using slides" in rendered.stderr
        assert rendered.returncode == 0, rendered.stderr
        mp4 = out / "movie.mp4"
        assert mp4.is_file(), rendered.stderr
        srt = (out / "captions.srt").read_text(encoding="utf-8")
        assert "Made with AI" in srt
        summary = json.loads(rendered.stdout.strip().splitlines()[-1])
        assert 45.0 <= float(summary["duration"]) <= 75.0
        assert summary["width"] == 1080
        assert summary["height"] == 1920
        assert summary["audio"] is True
        assert summary["end_card"] is True
        assert (out / "poster.png").is_file()


def test_no_key_slides() -> None:
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
        out = tmp / "movie"
        env = {"XAI_API_KEY": ""}
        rendered = run(
            [
                sys.executable,
                str(SCRIPTS / "render.py"),
                "--script",
                str(script_path),
                "--out",
                str(out),
                "--backend",
                "slides",
            ],
            env=env,
            timeout=300,
        )
        assert rendered.returncode == 0, rendered.stderr
        assert "backend=slides" in rendered.stdout
        assert (out / "movie.mp4").is_file()


def main() -> None:
    test_backend_selection()
    test_key_not_logged_on_fallback_render()
    test_no_key_slides()
    print("A1/A4 PASS")


if __name__ == "__main__":
    main()
