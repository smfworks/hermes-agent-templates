#!/usr/bin/env python3
"""Run one roast from a fixtures or live read. Overwrites the report in place."""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
from pathlib import Path

from card import archetype_for, share_card_text
from roast_metrics import compute_metrics, is_reply, is_retweet
from store import (
    FOOTER,
    NO_EARLIER,
    NO_TOKEN_MESSAGE,
    PROFILE_LINK_MESSAGE,
    PROTECTED_MESSAGE,
    append_jsonl,
    atomic_write,
    read_jsonl,
    save_state,
    shift_days,
    strip_handle,
    utc_now_text,
)
from x_read import read_posts

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "report.html"
PLACEHOLDER_RE = re.compile(r"\{\{([a-z_]+)\}\}")

HABIT_FIX = {
    "link_only": "put a real sentence before any link",
    "emoji_only": "add words beside the emoji",
    "reply_heavy": "publish an original before the replies",
    "no_hook": "open with a number or a specific name",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write a Roast My Feed audit")
    parser.add_argument("--data", required=True)
    parser.add_argument("--handle", required=True)
    parser.add_argument("--backend", default="fixtures", choices=["fixtures", "live"])
    parser.add_argument("--fixtures", default=None)
    parser.add_argument("--now", default=None)
    parser.add_argument("--tz", default="America/New_York")
    parser.add_argument("--max-pages", type=int, default=20)
    return parser.parse_args(argv)


def emit_status(outcome: dict) -> int:
    status = outcome.get("status")
    if status == "not_found":
        print(PROFILE_LINK_MESSAGE)
        return 2
    if status == "protected":
        print(PROTECTED_MESSAGE)
        return 0
    if status == "no_token":
        print(NO_TOKEN_MESSAGE)
        return 4
    print(outcome.get("detail") or "Read failed.", file=sys.stderr)
    return 1


def fetch(args: argparse.Namespace, handle: str, now: str, start: str) -> dict:
    token = None
    if args.backend == "live":
        token = os.environ.get("X_BEARER_TOKEN", "").strip()
        if not token:
            return {"status": "no_token"}
    return read_posts(
        handle=handle,
        backend=args.backend,
        now=now,
        start=start,
        max_pages=args.max_pages,
        fixtures=args.fixtures,
        token=token,
    )


def post_text(posts: list[dict], post_id: object) -> str:
    wanted = str(post_id)
    for post in posts:
        if str(post.get("id")) == wanted:
            return str(post.get("text") or "")
    return ""


def opener_line(text: str) -> str:
    lines = text.splitlines()
    if not lines:
        return "a concrete opener"
    cleaned = lines[0].strip()
    return cleaned or "a concrete opener"


def build_stats(metrics: dict) -> str:
    per_day = ", ".join(
        f"{day} {count}" for day, count in metrics["posts_per_day"].items()
    )
    hours = ", ".join(str(hour) for hour in metrics["most_active_hours"]) or "none"
    views = "yes" if metrics["views_present"] else "no"
    return "\n".join(
        [
            f"Posts in window: {metrics['posts_in_window']}",
            f"Posts per day: {per_day}",
            f"Replies: {metrics['share_replies']}",
            f"Quotes: {metrics['share_quotes']}",
            f"Originals: {metrics['share_originals']}",
            f"Emoji-only: {metrics['emoji_only']}",
            f"Link-only: {metrics['link_only']}",
            f"Hooks in line one: {metrics['hook_number_or_name']}",
            f"Median likes: {metrics['median_likes']}",
            f"Max likes: {metrics['max_likes']}",
            f"Views present: {views}",
            f"Most active hours: {hours}",
        ]
    )


def build_plan(habit: str, count: int, opener: str) -> str:
    fix = HABIT_FIX.get(habit, "change the pattern that is lagging")
    actions = [
        f"The habit is {habit} ({count} posts). Today, {fix}.",
        f"Open the way the best post did: {opener}",
        f"Publish one original and {fix}.",
        "Use an hour you already show up in.",
        f"Drop one {habit} pattern before it ships.",
        "Keep the line-one move from the best post.",
        "Write down the one move you will repeat tomorrow.",
    ]
    blocks = []
    for number, action in enumerate(actions, start=1):
        blocks.append(f"### Day {number}\n\n{action}")
    return "\n\n".join(blocks)


def build_drafts(posts: list[dict]) -> str:
    picked: list[str] = []
    for post in posts:
        if not isinstance(post, dict) or is_retweet(post) or is_reply(post):
            continue
        text = str(post.get("text") or "").strip()
        if not text:
            continue
        first = text.splitlines()[0].strip()
        if not first or first in picked:
            continue
        picked.append(first)
        if len(picked) == 3:
            break
    fillers = [
        "Here is the concrete thing I shipped.",
        "One detail from the work, then the next step.",
        "A short note on what I am practicing this week.",
    ]
    while len(picked) < 3:
        picked.append(fillers[len(picked)])
    blocks = []
    for number, line in enumerate(picked[:3], start=1):
        blocks.append(f"### Draft {number}\n\n{line}")
    return "\n\n".join(blocks)


def earlier_sentence(previous: dict | None) -> str:
    if not previous:
        return NO_EARLIER
    habit = previous.get("worst_habit")
    count = previous.get("worst_habit_count")
    return f"Last run worst habit {habit} count was {count}."


def build_markdown(
    handle: str,
    window_start: str,
    window_end: str,
    capped: bool,
    archetype: str,
    stats: str,
    best_text: str,
    link: str,
    habit_text: str,
    plan: str,
    drafts: str,
    compare: str,
) -> str:
    window = f"{window_start} to {window_end}"
    if capped:
        window += "\nPage cap reached. This window starts at the oldest post read."
    sections = [
        "# Roast My Feed",
        "",
        "## Window",
        "",
        window,
        "",
        compare,
        "",
        "## Archetype",
        "",
        archetype,
        "",
        "## Stats",
        "",
        stats,
        "",
        "## Best post",
        "",
        best_text,
        "",
        link,
        "",
        "## Worst habit",
        "",
        habit_text,
        "",
        "## 7-day plan",
        "",
        plan,
        "",
        "## Drafts",
        "",
        drafts,
        "",
        FOOTER,
        "",
    ]
    return "\n".join(sections)


def html_text(text: str) -> str:
    return "<br>\n".join(html.escape(line) for line in text.split("\n"))


def build_html(fields: dict[str, str]) -> str:
    template = TEMPLATE.read_text(encoding="utf-8")

    def swap(match: re.Match[str]) -> str:
        return fields.get(match.group(1), match.group(0))

    return PLACEHOLDER_RE.sub(swap, template)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    handle = strip_handle(args.handle)
    now = args.now or utc_now_text()
    outcome = fetch(args, handle, now, shift_days(now, -7))
    if outcome.get("status") != "ok":
        return emit_status(outcome)
    payload = outcome["payload"]
    # A short 7-day read widens to 30 days. A capped read keeps the posts it has.
    if not payload["capped"] and len(payload["posts"]) < 20:
        outcome = fetch(args, handle, now, shift_days(now, -30))
        if outcome.get("status") != "ok":
            return emit_status(outcome)
        payload = outcome["payload"]

    posts = payload["posts"]
    window_start = str(payload["window_start"])
    window_end = str(payload["window_end"])
    metrics = compute_metrics(
        posts,
        now=window_end,
        tz=args.tz,
        window_start=window_start,
    )
    best_text = post_text(posts, metrics["best_post_id"])
    link = f"https://x.com/{handle}/status/{metrics['best_post_id']}"
    archetype = archetype_for(str(metrics["worst_habit"]))
    stats = build_stats(metrics)
    habit_text = (
        f"{metrics['worst_habit']} showed up {metrics['worst_habit_count']} times. "
        "Median likes for that pattern minus the overall median is "
        f"{metrics['worst_habit_vs_median']}."
    )
    plan = build_plan(
        str(metrics["worst_habit"]),
        int(metrics["worst_habit_count"]),
        opener_line(best_text),
    )
    drafts = build_drafts(posts)
    data = Path(args.data)
    history_path = data / "history.jsonl"
    previous_rows = read_jsonl(history_path)
    previous = previous_rows[-1] if previous_rows else None
    compare = earlier_sentence(previous)
    markdown = build_markdown(
        handle=handle,
        window_start=window_start,
        window_end=window_end,
        capped=bool(payload["capped"]),
        archetype=archetype,
        stats=stats,
        best_text=best_text,
        link=link,
        habit_text=habit_text,
        plan=plan,
        drafts=drafts,
        compare=compare,
    )
    best_html = html_text(best_text)
    if best_html:
        best_html += "<br>\n"
    best_html += html.escape(link)
    rendered = build_html(
        {
            "handle": html.escape(handle),
            "window": html_text(f"{window_start} to {window_end}\n{compare}"),
            "archetype": html.escape(archetype),
            "stats": html_text(stats),
            "best_post": best_html,
            "worst_habit": html_text(habit_text),
            "plan": html_text(plan),
            "drafts": html_text(drafts),
        }
    )
    roast_dir = data / "roast" / handle
    md_path = roast_dir / "roast.md"
    html_path = roast_dir / "roast.html"
    atomic_write(md_path, markdown)
    atomic_write(html_path, rendered)
    append_jsonl(
        history_path,
        {
            "handle": handle,
            "at": now,
            "window_start": window_start,
            "window_end": window_end,
            "posts_in_window": int(metrics["posts_in_window"]),
            "worst_habit": metrics["worst_habit"],
            "worst_habit_count": int(metrics["worst_habit_count"]),
            "best_post_id": metrics["best_post_id"],
        },
    )
    save_state(data / "state.json", {"handle": handle, "tz": args.tz})
    sys.stdout.write(md_path.as_posix() + "\n")
    sys.stdout.write(
        share_card_text(handle, metrics, archetype)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
