#!/usr/bin/env python3
"""Write movies/<slug>/movie.md and movie.html in place."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from util import atomic_write, merge_state

FOOTER = "Try Hermes: Explain It Like a Movie by SMF Works"
AI_LABEL = "Made with AI"
ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "report.html"


def tagged(line: dict) -> str:
    return f"{line['text']} [{line['cite']}]"


def markdown(script: dict, status: str) -> str:
    parts = [
        f"# {script['title']}",
        "",
        f"Status: {status}",
        "",
        "## Script",
        "",
    ]
    labels = {"hook": "Hook", "beat": "Beat", "takeaway": "Takeaway"}
    beat_n = 0
    for line in script["lines"]:
        role = line["role"]
        if role == "beat":
            beat_n += 1
            heading = f"Beat {beat_n}"
        else:
            heading = labels.get(role, role)
        parts.append(f"**{heading}.** {tagged(line)}")
        parts.append("")
    parts.extend(["## Sources", ""])
    for src in script.get("sources") or []:
        parts.append(
            f"[{src['n']}] {src.get('title') or src['url']} — {src['url']} (fetched {src.get('fetched', '')})"
        )
    parts.extend(["", "## Shot notes", ""])
    for line in script["lines"]:
        shot = line.get("shot") or {}
        parts.append(
            f"- [{line['cite']}] visual: {shot.get('visual', '')}; on-screen: {shot.get('on_screen', '')}"
        )
    caps = script.get("captions") or {}
    parts.extend(
        [
            "",
            "## Captions",
            "",
            "### X",
            "",
            caps.get("x", AI_LABEL),
            "",
            "### TikTok",
            "",
            caps.get("tiktok", AI_LABEL),
            "",
            AI_LABEL,
            "",
            FOOTER,
            "",
        ]
    )
    return "\n".join(parts)


def html_report(script: dict, status: str) -> str:
    template = TEMPLATE.read_text(encoding="utf-8")
    script_html = []
    beat_n = 0
    labels = {"hook": "Hook", "beat": "Beat", "takeaway": "Takeaway"}
    for line in script["lines"]:
        role = line["role"]
        if role == "beat":
            beat_n += 1
            heading = f"Beat {beat_n}"
        else:
            heading = labels.get(role, role)
        script_html.append(
            f"<p><strong>{html.escape(heading)}.</strong> {html.escape(tagged(line))}</p>"
        )
    sources_html = []
    for src in script.get("sources") or []:
        sources_html.append(
            "<li>"
            f"[{src['n']}] {html.escape(str(src.get('title') or src['url']))} — "
            f"{html.escape(str(src['url']))} (fetched {html.escape(str(src.get('fetched', '')))})"
            "</li>"
        )
    shots_html = []
    for line in script["lines"]:
        shot = line.get("shot") or {}
        shots_html.append(
            "<li>"
            f"[{line['cite']}] visual: {html.escape(str(shot.get('visual', '')))}; "
            f"on-screen: {html.escape(str(shot.get('on_screen', '')))}"
            "</li>"
        )
    caps = script.get("captions") or {}
    filled = (
        template.replace("{{title}}", html.escape(script["title"]))
        .replace("{{status}}", html.escape(status))
        .replace("{{script}}", "\n".join(script_html))
        .replace("{{sources}}", "\n".join(sources_html))
        .replace("{{shots}}", "\n".join(shots_html))
        .replace("{{caption_x}}", html.escape(caps.get("x", AI_LABEL)))
        .replace("{{caption_tiktok}}", html.escape(caps.get("tiktok", AI_LABEL)))
        .replace("{{ai_label}}", AI_LABEL)
        .replace("{{footer}}", FOOTER)
    )
    return filled


def status_text(args: argparse.Namespace) -> str:
    if args.status == "rendering":
        return "Video rendering"
    if args.status == "video":
        return args.video
    # failure
    err = args.error or "Render failed."
    nxt = args.next or "Install ffmpeg and espeak-ng (or piper), then rerun movie-produce."
    return f"Render failed. {err} Next step: {nxt}"


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write the movie report in place.")
    parser.add_argument("--script", required=True)
    parser.add_argument("--out", required=True, help="Slug directory.")
    parser.add_argument("--status", required=True, choices=("rendering", "video", "failure"))
    parser.add_argument("--video", default="")
    parser.add_argument("--error", default="")
    parser.add_argument("--next", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    script = json.loads(Path(args.script).read_text(encoding="utf-8"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    status = status_text(args)
    atomic_write(out / "movie.md", markdown(script, status))
    atomic_write(out / "movie.html", html_report(script, status))
    merge_state(out / "state.json", last_status=status, offered_style_lock=True)
    print(out / "movie.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
