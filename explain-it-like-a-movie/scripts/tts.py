#!/usr/bin/env python3
"""Find piper or espeak-ng and speak a line to a WAV file."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


class TtsMissing(RuntimeError):
    """No speech binary. Script still delivered; render stops."""


def _which(name: str) -> str | None:
    return shutil.which(name)


def describe_install() -> str:
    return (
        "TTS is missing. Install espeak-ng (apt install espeak-ng / pacman -S espeak-ng) "
        "or piper, and set PIPER_MODEL to an onnx voice. The script is already written; "
        "rerun movie-produce after TTS is installed."
    )


def available() -> str | None:
    if _which("espeak-ng") or _which("espeak"):
        return "espeak-ng" if _which("espeak-ng") else "espeak"
    piper = os.environ.get("PIPER_BIN") or _which("piper")
    model = os.environ.get("PIPER_MODEL")
    if piper and model and Path(piper).is_file() and Path(model).is_file():
        return "piper"
    return None


def speak(text: str, wav: Path, wpm: int = 150) -> None:
    wav.parent.mkdir(parents=True, exist_ok=True)
    engine = available()
    if engine is None:
        raise TtsMissing(describe_install())
    if engine in {"espeak-ng", "espeak"}:
        binary = _which(engine)
        assert binary
        result = subprocess.run(
            [binary, "-w", str(wav), "-s", str(wpm), "--", text],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not wav.is_file():
            raise RuntimeError(result.stderr.strip() or "espeak failed")
        return
    model = os.environ["PIPER_MODEL"]
    binary = os.environ.get("PIPER_BIN") or _which("piper")
    assert binary
    result = subprocess.run(
        [binary, "-m", model, "-f", str(wav)],
        check=False,
        input=text + "\n",
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not wav.is_file():
        err = (result.stderr or result.stdout or "piper failed").strip()
        raise RuntimeError(err)
