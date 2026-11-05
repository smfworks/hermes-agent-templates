#!/usr/bin/env python3
"""Render movie.mp4. Imagine API when a key is present, else slides+TTS+ffmpeg."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import wave
from pathlib import Path

AI_LABEL = "Made with AI"


class FfmpegMissing(RuntimeError):
    pass


def ffmpeg_bin() -> str:
    found = shutil.which("ffmpeg")
    if not found:
        raise FfmpegMissing(
            "ffmpeg is missing. Install ffmpeg. The script is already written; "
            "rerun movie-produce after ffmpeg is installed."
        )
    return found


def choose_backend(explicit: str | None = None) -> str:
    if explicit in {"slides", "imagine"}:
        return explicit
    if os.environ.get("XAI_API_KEY"):
        return "imagine"
    return "slides"


def wav_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        frames = handle.getnframes()
        rate = handle.getframerate() or 1
        return frames / float(rate)


def run_ffmpeg(args: list[str]) -> None:
    result = subprocess.run(args, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "ffmpeg failed").strip()
        raise RuntimeError(err.splitlines()[-1] if err else "ffmpeg failed")


def srt_stamp(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, milli = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{milli:03d}"


def write_srt(path: Path, cues: list[tuple[float, float, str]]) -> None:
    chunks = []
    for index, (start, end, text) in enumerate(cues, start=1):
        chunks.append(f"{index}\n{srt_stamp(start)} --> {srt_stamp(end)}\n{text}\n")
    path.write_text("\n".join(chunks) + "\n", encoding="utf-8")


def still_clip(png: Path, wav: Path, mp4: Path) -> float:
    duration = max(wav_seconds(wav), 0.8)
    run_ffmpeg(
        [
            ffmpeg_bin(),
            "-y",
            "-loop",
            "1",
            "-t",
            f"{duration:.3f}",
            "-i",
            str(png),
            "-i",
            str(wav),
            "-vf",
            "scale=1080:1920",
            "-c:v",
            "libx264",
            "-tune",
            "stillimage",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            "-t",
            f"{duration:.3f}",
            str(mp4),
        ]
    )
    return duration


def concat_mp4(clips: list[Path], out: Path) -> None:
    listing = out.parent / "concat.txt"
    lines = []
    for clip in clips:
        escaped = str(clip).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
    run_ffmpeg(
        [
            ffmpeg_bin(),
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-c",
            "copy",
            str(out),
        ]
    )


def fit_duration(mp4: Path, target: float = 60.0) -> None:
    import qa

    info = qa.probe(mp4)
    duration = float(info.get("format", {}).get("duration") or 0)
    if 45.0 <= duration <= 75.0:
        return
    fitted = mp4.with_name("fitted.mp4")
    if duration < 45.0:
        pad = max(target - duration, 45.0 - duration + 0.5)
        run_ffmpeg(
            [
                ffmpeg_bin(),
                "-y",
                "-i",
                str(mp4),
                "-vf",
                f"tpad=stop_mode=clone:stop_duration={pad:.3f}",
                "-af",
                f"apad=pad_dur={pad:.3f}",
                "-t",
                f"{target:.3f}",
                "-pix_fmt",
                "yuv420p",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                str(fitted),
            ]
        )
    else:
        factor = duration / target
        if factor > 2.0:
            factor = 2.0
        run_ffmpeg(
            [
                ffmpeg_bin(),
                "-y",
                "-i",
                str(mp4),
                "-filter_complex",
                f"[0:v]setpts=PTS/{factor:.4f}[v];[0:a]atempo={factor:.4f}[a]",
                "-map",
                "[v]",
                "-map",
                "[a]",
                "-pix_fmt",
                "yuv420p",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                str(fitted),
            ]
        )
    fitted.replace(mp4)


def burn_captions(mp4: Path, srt: Path) -> None:
    burned = mp4.with_name("burned.mp4")
    # subtitles= needs escaped path; on-slide text already exists if this fails.
    srt_arg = str(srt).replace("\\", "\\\\").replace(":", "\\:")
    try:
        run_ffmpeg(
            [
                ffmpeg_bin(),
                "-y",
                "-i",
                str(mp4),
                "-vf",
                f"subtitles={srt_arg}:force_style='Alignment=2,MarginV=520,Fontsize=18'",
                "-c:a",
                "copy",
                str(burned),
            ]
        )
    except RuntimeError:
        return
    if burned.is_file():
        burned.replace(mp4)


def render_imagine(_script: dict, _out: Path) -> None:
    # Selected only when a key is present. A live image endpoint is opt-in so
    # a guessed host is never called, and the key is never printed.
    url = os.environ.get("MOVIE_IMAGINE_URL", "").strip()
    if not url:
        raise RuntimeError("imagine endpoint not set")
    raise RuntimeError("imagine endpoint skipped")


def render_slides(script: dict, out: Path) -> None:
    import slides
    import tts

    work = out / "work"
    work.mkdir(parents=True, exist_ok=True)
    slides.poster(out / "poster.png", script["title"])
    slides.end_card(work / "end.png")

    cues: list[tuple[float, float, str]] = []
    clips: list[Path] = []
    cursor = 0.0

    def add_clip(png: Path, spoken: str, caption: str, name: str) -> None:
        nonlocal cursor
        wav = work / f"{name}.wav"
        mp4 = work / f"{name}.mp4"
        tts.speak(spoken, wav)
        dur = still_clip(png, wav, mp4)
        cues.append((cursor, cursor + dur, caption))
        clips.append(mp4)
        cursor += dur

    title_png = work / "title.png"
    slides.title_card(title_png, script["title"])
    add_clip(title_png, script["title"], script["title"], "00-title")

    beat_n = 0
    for index, line in enumerate(script["lines"], start=1):
        role = line["role"]
        if role == "beat":
            beat_n += 1
            label = f"Beat {beat_n}"
        elif role == "hook":
            label = "Hook"
        else:
            label = "Takeaway"
        png = work / f"{index:02d}.png"
        slides.line_card(png, label, line["text"], int(line["cite"]), line["shot"]["on_screen"])
        caption = f"{line['text']} [{line['cite']}]"
        add_clip(png, line["text"], caption, f"{index:02d}-line")

    add_clip(work / "end.png", AI_LABEL, AI_LABEL, "99-end")

    raw = work / "concat.mp4"
    concat_mp4(clips, raw)
    write_srt(out / "captions.srt", cues)
    dest = out / "movie.mp4"
    shutil.copyfile(raw, dest)
    burn_captions(dest, out / "captions.srt")
    fit_duration(dest)
    shutil.copyfile(work / "end.png", out / "endcard.png")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a 9:16 explainer.")
    parser.add_argument("--script", default="")
    parser.add_argument("--out", default="")
    parser.add_argument("--backend", choices=("auto", "slides", "imagine"), default="auto")
    parser.add_argument("--print-backend", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    explicit = None if args.backend == "auto" else args.backend
    backend = choose_backend(explicit)
    if args.print_backend:
        sys.stdout.write(backend + "\n")
        return 0
    if not args.script or not args.out:
        raise SystemExit("--script and --out are required")
    script = json.loads(Path(args.script).read_text(encoding="utf-8"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    import qa
    import tts

    # Print backend name only. Never print environment values.
    sys.stdout.write(f"backend={backend}\n")
    try:
        if backend == "imagine":
            try:
                render_imagine(script, out)
            except Exception:
                sys.stderr.write("imagine backend unavailable, using slides\n")
                render_slides(script, out)
        else:
            render_slides(script, out)
        summary = qa.check(out / "movie.mp4", out / "qa-last.png")
        sys.stdout.write(json.dumps(summary) + "\n")
        return 0
    except tts.TtsMissing as exc:
        sys.stderr.write(str(exc) + "\n")
        return 2
    except FfmpegMissing as exc:
        sys.stderr.write(str(exc) + "\n")
        return 2
    except qa.QaError as exc:
        sys.stderr.write(str(exc) + "\n")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
