#!/usr/bin/env python3
"""ffprobe QA: 45–75s, 1080x1920, audio present, end card present."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from PIL import Image

GOLD = (201, 162, 39)


class QaError(RuntimeError):
    pass


def ffprobe_bin() -> str:
    found = shutil.which("ffprobe")
    if not found:
        raise QaError("ffprobe is missing. Install ffmpeg.")
    return found


def probe(path: Path) -> dict:
    result = subprocess.run(
        [
            ffprobe_bin(),
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise QaError(result.stderr.strip() or "ffprobe failed")
    return json.loads(result.stdout)


def last_frame(mp4: Path, png: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise QaError("ffmpeg is missing.")
    png.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [ffmpeg, "-y", "-sseof", "-0.4", "-i", str(mp4), "-frames:v", "1", str(png)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not png.is_file():
        raise QaError("could not extract last frame")


def near_gold(pixel: tuple[int, int, int], tol: int = 40) -> bool:
    return all(abs(pixel[i] - GOLD[i]) <= tol for i in range(3))


def check(mp4: Path, frame_png: Path | None = None) -> dict:
    info = probe(mp4)
    duration = float(info.get("format", {}).get("duration") or 0)
    if not 45.0 <= duration <= 75.0:
        raise QaError(f"duration {duration:.1f}s is outside 45–75")
    video = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    audio = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    if not video:
        raise QaError("no video stream")
    if int(video.get("width") or 0) != 1080 or int(video.get("height") or 0) != 1920:
        raise QaError(f"size {video.get('width')}x{video.get('height')} is not 1080x1920")
    if not audio:
        raise QaError("no audio stream")
    frame_path = frame_png or (mp4.parent / "qa-last.png")
    last_frame(mp4, frame_path)
    pix = Image.open(frame_path).convert("RGB").getpixel((540, 1664))
    if not near_gold(pix):
        raise QaError(f"end card gold bar missing, pixel={pix}")
    return {"duration": duration, "width": 1080, "height": 1920, "audio": True, "end_card": True}
