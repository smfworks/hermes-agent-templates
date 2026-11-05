#!/usr/bin/env python3
"""Deterministic post metrics. Counts only. No network and no model calls."""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from zoneinfo import ZoneInfo

from store import atomic_write, parse_time, shift_days

URL_RE = re.compile(r"https?://\S+")
HOOK_NAME_RE = re.compile(r"(?<![A-Za-z])[A-Z][a-zA-Z]{2,}")
METRIC_KEYS = (
    "posts_in_window",
    "posts_per_day",
    "share_replies",
    "share_quotes",
    "share_originals",
    "emoji_only",
    "link_only",
    "hook_number_or_name",
    "median_likes",
    "max_likes",
    "views_present",
    "most_active_hours",
    "best_post_id",
    "worst_habit",
    "worst_habit_count",
    "worst_habit_vs_median",
)


def whole_number(value: int | float) -> int | float:
    number = float(value)
    if number.is_integer():
        return int(number)
    return number


def as_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool) or value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return default


def metric_map(post: dict) -> dict:
    raw = post.get("public_metrics")
    if isinstance(raw, dict):
        return raw
    return {}


def ref_types(post: dict) -> set[str]:
    found: set[str] = set()
    raw = post.get("referenced_tweets")
    if not isinstance(raw, list):
        return found
    for item in raw:
        if isinstance(item, dict) and item.get("type"):
            found.add(str(item["type"]))
    return found


def is_retweet(post: dict) -> bool:
    return "retweeted" in ref_types(post)


def is_reply(post: dict) -> bool:
    return "replied_to" in ref_types(post)


def is_quote(post: dict) -> bool:
    kinds = ref_types(post)
    return "quoted" in kinds and "replied_to" not in kinds


def likes_of(post: dict) -> int:
    return as_int(metric_map(post).get("likes"), 0)


def views_of(post: dict) -> int:
    metrics = metric_map(post)
    if "impressions" in metrics:
        return as_int(metrics.get("impressions"), 0)
    if "views" in metrics:
        return as_int(metrics.get("views"), 0)
    return 0


def has_numeric_views(post: dict) -> bool:
    metrics = metric_map(post)
    for key in ("impressions", "views"):
        value = metrics.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return True
    return False


def first_line(text: str) -> str:
    lines = text.splitlines()
    if not lines:
        return ""
    return lines[0]


def emoji_only(text: str) -> bool:
    remaining = URL_RE.sub("", text)
    if remaining.strip() == "":
        return False
    for char in remaining:
        if char.isspace():
            continue
        if unicodedata.category(char) != "So":
            return False
    return True


def link_only(text: str) -> bool:
    parts = text.split()
    if not parts:
        return False
    return all(URL_RE.fullmatch(part) is not None for part in parts)


def has_hook(text: str) -> bool:
    line = first_line(text)
    if re.search(r"\d", line):
        return True
    return HOOK_NAME_RE.search(line) is not None


def median(values: list[int]) -> int | float:
    if not values:
        return 0
    ordered = sorted(values)
    count = len(ordered)
    if count % 2 == 1:
        return int(ordered[count // 2])
    average = (ordered[count // 2 - 1] + ordered[count // 2]) / 2
    return whole_number(average)


def compute_metrics(
    posts: list[dict],
    now: str,
    tz: str,
    window_start: str | None = None,
) -> dict:
    start_text = window_start or shift_days(now, -7)
    start = parse_time(start_text)
    end = parse_time(now)
    zone = ZoneInfo(tz)
    counted: list[dict] = []
    for post in posts:
        if not isinstance(post, dict) or is_retweet(post):
            continue
        created_raw = post.get("created_at")
        if not isinstance(created_raw, str):
            continue
        try:
            created = parse_time(created_raw)
        except ValueError:
            continue
        if start <= created <= end:
            counted.append(post)

    day_counts: dict[str, int] = {}
    hour_counts: dict[int, int] = {}
    reply_likes: list[int] = []
    quote_count = 0
    original_count = 0
    emoji_likes: list[int] = []
    link_likes: list[int] = []
    hook_count = 0
    no_hook_likes: list[int] = []
    all_likes: list[int] = []
    views_present = False

    for post in counted:
        text = str(post.get("text") or "")
        created = parse_time(str(post["created_at"])).astimezone(zone)
        day = created.date().isoformat()
        day_counts[day] = day_counts.get(day, 0) + 1
        hour_counts[created.hour] = hour_counts.get(created.hour, 0) + 1
        likes = likes_of(post)
        all_likes.append(likes)
        if has_numeric_views(post):
            views_present = True
        if is_reply(post):
            reply_likes.append(likes)
        elif is_quote(post):
            quote_count += 1
        else:
            original_count += 1
        if emoji_only(text):
            emoji_likes.append(likes)
        if link_only(text):
            link_likes.append(likes)
        if has_hook(text):
            hook_count += 1
        else:
            no_hook_likes.append(likes)

    overall = median(all_likes)
    patterns: list[tuple[int | float, int, str, int, int | float]] = []
    if len(link_likes) >= 3:
        link_median = median(link_likes)
        patterns.append((link_median, 0, "link_only", len(link_likes), link_median))
    if len(emoji_likes) >= 3:
        emoji_median = median(emoji_likes)
        patterns.append((emoji_median, 1, "emoji_only", len(emoji_likes), emoji_median))
    if len(reply_likes) > original_count and len(reply_likes) >= 3:
        reply_median = median(reply_likes)
        patterns.append((reply_median, 2, "reply_heavy", len(reply_likes), reply_median))
    if len(no_hook_likes) >= 3:
        hookless_median = median(no_hook_likes)
        patterns.append((hookless_median, 3, "no_hook", len(no_hook_likes), hookless_median))

    if patterns:
        _median, _priority, habit, habit_count, habit_median = min(patterns)
        habit_vs = whole_number(habit_median - overall)
    else:
        habit = "no_hook"
        habit_count = len(no_hook_likes)
        habit_vs = 0

    if counted:
        best = min(
            counted,
            key=lambda post: (-likes_of(post), -views_of(post), str(post.get("id"))),
        )
        best_id = best.get("id")
    else:
        best_id = ""

    if hour_counts:
        peak = max(hour_counts.values())
        active = sorted(hour for hour, count in hour_counts.items() if count == peak)
    else:
        active = []

    per_day = {day: day_counts[day] for day in sorted(day_counts) if day_counts[day] > 0}
    metrics = {
        "posts_in_window": len(counted),
        "posts_per_day": per_day,
        "share_replies": len(reply_likes),
        "share_quotes": quote_count,
        "share_originals": original_count,
        "emoji_only": len(emoji_likes),
        "link_only": len(link_likes),
        "hook_number_or_name": hook_count,
        "median_likes": overall,
        "max_likes": max(all_likes) if all_likes else 0,
        "views_present": views_present,
        "most_active_hours": active,
        "best_post_id": best_id,
        "worst_habit": habit,
        "worst_habit_count": habit_count,
        "worst_habit_vs_median": habit_vs,
    }
    if set(metrics) != set(METRIC_KEYS):
        missing = set(METRIC_KEYS) - set(metrics)
        extra = set(metrics) - set(METRIC_KEYS)
        raise RuntimeError(f"metric keys drifted missing={missing} extra={extra}")
    return metrics


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Count roast metrics for a post list")
    parser.add_argument("--posts", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--now", required=True)
    parser.add_argument("--tz", required=True)
    parser.add_argument("--window-start", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    loaded = json.loads(Path(args.posts).read_text(encoding="utf-8"))
    if not isinstance(loaded, list):
        print("posts file must be a JSON list", file=sys.stderr)
        return 1
    metrics = compute_metrics(
        loaded,
        now=args.now,
        tz=args.tz,
        window_start=args.window_start,
    )
    atomic_write(
        Path(args.out),
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
