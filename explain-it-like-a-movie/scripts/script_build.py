#!/usr/bin/env python3
"""Build script.json from sourced facts. Unsourced lines are cut."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from util import slugify, write_json

AI_LABEL = "Made with AI"
FOOTER = "Try Hermes: Explain It Like a Movie by SMF Works"


def sourced_facts(facts: list[dict]) -> list[dict]:
    kept = []
    for fact in facts:
        cite = fact.get("source")
        text = (fact.get("text") or "").strip()
        if not text:
            continue
        if cite in (None, "", 0, "0"):
            continue
        kept.append({"text": text, "source": int(cite), "example": fact.get("example") or ""})
    return kept


def shot_for(text: str, on_screen: str) -> dict:
    return {"visual": f"9:16 card, {text[:80]}", "on_screen": on_screen}


def build(payload: dict) -> dict:
    sources = payload.get("sources") or []
    by_n = {int(src["n"]): src for src in sources}
    facts = sourced_facts(payload.get("facts") or [])
    if not facts:
        raise SystemExit("no sourced facts remain")
    title = payload.get("title") or facts[0]["text"][:80]
    slug = payload.get("slug") or slugify(title)

    # Hook, three beats, takeaway. Reuse last facts if the list is short.
    while len(facts) < 5:
        facts.append(facts[-1])
    hook_fact, b1, b2, b3, take = facts[0], facts[1], facts[2], facts[3], facts[-1]

    def line(role: str, fact: dict, prefix: str) -> dict:
        cite = int(fact["source"])
        if cite not in by_n:
            raise SystemExit(f"missing source [{cite}]")
        body = fact["text"]
        extra = fact.get("example") or ""
        text = f"{prefix}{body}"
        if extra and extra not in text:
            text = f"{text} {extra}".strip()
        on_screen = body[:90]
        return {
            "role": role,
            "text": text,
            "cite": cite,
            "shot": shot_for(body, on_screen),
        }

    lines = [
        line("hook", hook_fact, ""),
        line("beat", b1, ""),
        line("beat", b2, ""),
        line("beat", b3, ""),
        line("takeaway", take, ""),
    ]
    # Force hook into a question if it is not one.
    if not lines[0]["text"].rstrip().endswith("?"):
        lines[0]["text"] = lines[0]["text"].rstrip(".") + "?"

    words = " ".join(item["text"] for item in lines)
    caption_body = " ".join(item["text"] for item in lines)
    script = {
        "slug": slug,
        "title": title,
        "lines": lines,
        "sources": sources,
        "captions": {
            "x": f"{caption_body}\n\n{AI_LABEL}",
            "tiktok": f"{caption_body}\n\n{AI_LABEL}",
        },
        "word_count": len(words.split()),
        "ai_label": AI_LABEL,
        "footer": FOOTER,
    }
    return script


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a sourced movie script.")
    parser.add_argument("--facts", required=True, help="JSON with title, facts, sources.")
    parser.add_argument("--out", required=True, help="script.json path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = json.loads(Path(args.facts).read_text(encoding="utf-8"))
    script = build(payload)
    write_json(Path(args.out), script)
    sys.stdout.write(json.dumps({"slug": script["slug"], "lines": len(script["lines"])}) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
