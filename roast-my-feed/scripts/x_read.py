#!/usr/bin/env python3
"""Read public posts. GET only. Fixtures for tests. Never print the bearer token."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from store import (
    NO_TOKEN_MESSAGE,
    PROFILE_LINK_MESSAGE,
    PROTECTED_MESSAGE,
    parse_time,
    shift_days,
    strip_handle,
    utc_now_text,
)

API = "https://api.x.com/2"
# App-only reads share the account read budget. A 429 means wait and try later.
OUTPUT_KEYS = (
    "username",
    "protected",
    "suspended",
    "posts",
    "pages_read",
    "capped",
    "window_start",
    "window_end",
)


def is_retweet(post: dict) -> bool:
    raw = post.get("referenced_tweets")
    if not isinstance(raw, list):
        return False
    for item in raw:
        if isinstance(item, dict) and item.get("type") == "retweeted":
            return True
    return False


def in_window(created: str, start: datetime, end: datetime) -> bool:
    try:
        moment = parse_time(created)
    except ValueError:
        return False
    return start <= moment <= end


def oldest_stamp(posts: list[dict]) -> str | None:
    best: tuple[datetime, str] | None = None
    for post in posts:
        raw = post.get("created_at")
        if not isinstance(raw, str):
            continue
        try:
            moment = parse_time(raw)
        except ValueError:
            continue
        if best is None or moment < best[0]:
            best = (moment, raw)
    if best is None:
        return None
    return best[1]


def payload_for(
    username: str,
    protected: bool,
    suspended: bool,
    posts: list[dict],
    pages_read: int,
    capped: bool,
    window_start: str,
    window_end: str,
) -> dict:
    body = {
        "username": username,
        "protected": protected,
        "suspended": suspended,
        "posts": posts,
        "pages_read": pages_read,
        "capped": capped,
        "window_start": window_start,
        "window_end": window_end,
    }
    if set(body) != set(OUTPUT_KEYS):
        raise RuntimeError("read payload keys drifted")
    return body


def read_pages(pages: list, max_pages: int) -> tuple[list[dict], int, bool]:
    collected: list[dict] = []
    pages_read = 0
    capped = False
    index = 0
    while index < len(pages) and pages_read < max_pages:
        page = pages[index]
        index += 1
        if not isinstance(page, dict):
            pages_read += 1
            continue
        raw_posts = page.get("posts")
        if isinstance(raw_posts, list):
            for post in raw_posts:
                if isinstance(post, dict):
                    collected.append(post)
        pages_read += 1
        token = page.get("next_token")
        if not token:
            break
        if pages_read >= max_pages:
            capped = True
            break
    return collected, pages_read, capped


def posts_from_fixture(
    doc: dict,
    start_text: str,
    now_text: str,
    max_pages: int,
) -> tuple[list[dict], int, bool, str]:
    start = parse_time(start_text)
    end = parse_time(now_text)
    pages = doc.get("pages")
    if isinstance(pages, list):
        # Page fixtures keep every post on the page. Age is applied by the window
        # only when the page cap did not stop the read.
        collected, pages_read, capped = read_pages(pages, max_pages)
        kept = [post for post in collected if not is_retweet(post)]
        if capped:
            window_start = oldest_stamp(kept) or start_text
        else:
            window_start = start_text
        return kept, pages_read, capped, window_start
    raw_posts = doc.get("posts")
    kept = []
    if isinstance(raw_posts, list):
        for post in raw_posts:
            if not isinstance(post, dict) or is_retweet(post):
                continue
            created = post.get("created_at")
            if isinstance(created, str) and in_window(created, start, end):
                kept.append(post)
    return kept, 1, False, start_text


def classify_user(doc: dict, handle: str) -> str:
    if doc.get("protected") is True or doc.get("suspended") is True:
        return "protected"
    username = doc.get("username")
    if not isinstance(username, str) or username.strip() == "":
        return "not_found"
    if username.casefold() != handle.casefold():
        return "not_found"
    return "ok"


def read_fixture(path: Path, handle: str, start: str, now: str, max_pages: int) -> dict:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "error", "detail": "Could not read the fixtures file."}
    if not isinstance(loaded, dict):
        return {"status": "not_found"}
    kind = classify_user(loaded, handle)
    if kind == "protected":
        return {"status": "protected"}
    if kind == "not_found":
        return {"status": "not_found"}
    posts, pages_read, capped, window_start = posts_from_fixture(
        loaded, start, now, max_pages
    )
    body = payload_for(
        username=str(loaded["username"]),
        protected=False,
        suspended=False,
        posts=posts,
        pages_read=pages_read,
        capped=capped,
        window_start=window_start,
        window_end=now,
    )
    return {"status": "ok", "payload": body}


def get_json(url: str, token: str) -> tuple[int, dict]:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": "Bearer " + token,
            "User-Agent": "roast-my-feed-read",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            status = getattr(response, "status", 200)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        status = exc.code
    except urllib.error.URLError:
        return 0, {}
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return status, {}
    if not isinstance(payload, dict):
        return status, {}
    return status, payload


def looks_suspended(payload: dict) -> bool:
    chunks: list[str] = []
    errors = payload.get("errors")
    if isinstance(errors, list):
        for error in errors:
            if isinstance(error, dict):
                for key in ("title", "detail", "type"):
                    chunks.append(str(error.get(key, "")))
    chunks.append(str(payload.get("title", "")))
    chunks.append(str(payload.get("detail", "")))
    return "suspend" in " ".join(chunks).casefold()


def looks_missing(status: int, payload: dict) -> bool:
    if status == 404:
        return True
    if str(payload.get("title", "")) == "Not Found":
        return True
    errors = payload.get("errors")
    if isinstance(errors, list):
        for error in errors:
            if isinstance(error, dict) and str(error.get("title", "")) == "Not Found":
                return True
    return False


def normalize_tweet(tweet: dict) -> dict:
    metrics = tweet.get("public_metrics")
    if not isinstance(metrics, dict):
        metrics = {}
    public: dict = {}
    if "like_count" in metrics:
        public["likes"] = metrics["like_count"]
    elif "likes" in metrics:
        public["likes"] = metrics["likes"]
    if "impression_count" in metrics:
        public["impressions"] = metrics["impression_count"]
    elif "impressions" in metrics:
        public["impressions"] = metrics["impressions"]
    views = metrics.get("views")
    if isinstance(views, (int, float)) and not isinstance(views, bool):
        public["views"] = views
    referenced = tweet.get("referenced_tweets")
    if not isinstance(referenced, list):
        referenced = []
    return {
        "id": str(tweet.get("id") or tweet.get("id_str") or ""),
        "text": str(tweet.get("text") or tweet.get("full_text") or ""),
        "created_at": str(tweet.get("created_at") or ""),
        "public_metrics": public,
        "referenced_tweets": referenced,
        "conversation_id": str(tweet.get("conversation_id") or ""),
    }


def paginate(fetch_page, max_pages: int) -> tuple[list[dict], int, bool, str | None]:
    posts: list[dict] = []
    pages_read = 0
    capped = False
    page_token = None
    while pages_read < max_pages:
        status, payload, next_token = fetch_page(page_token)
        if status == 0:
            return posts, pages_read, capped, "failed"
        if looks_suspended(payload):
            return posts, pages_read, capped, "protected"
        if status != 200 and not payload.get("data"):
            return posts, pages_read, capped, "failed"
        raw_posts = payload.get("data") or []
        if isinstance(raw_posts, list):
            for tweet in raw_posts:
                if isinstance(tweet, dict):
                    posts.append(normalize_tweet(tweet))
        pages_read += 1
        if not next_token:
            break
        if pages_read >= max_pages:
            capped = True
            break
        page_token = next_token
    return posts, pages_read, capped, None


def user_lookup(handle: str, token: str) -> tuple[str, dict]:
    url = (
        API
        + "/users/by/username/"
        + urllib.parse.quote(handle)
        + "?"
        + urllib.parse.urlencode({"user.fields": "created_at,public_metrics,protected"})
    )
    status, payload = get_json(url, token)
    if looks_suspended(payload):
        return "protected", payload
    if looks_missing(status, payload) or status == 0:
        return "not_found", payload
    data = payload.get("data")
    if not isinstance(data, dict) or not data.get("id"):
        return "not_found", payload
    if data.get("protected") is True:
        return "protected", payload
    return "ok", data


def read_timeline(user_id: str, token: str, start: str, max_pages: int):
    def fetch_page(page_token):
        params = {
            "max_results": "100",
            "start_time": start,
            "exclude": "retweets",
            "tweet.fields": "created_at,public_metrics,referenced_tweets,conversation_id",
        }
        if page_token:
            params["pagination_token"] = page_token
        url = (
            API
            + "/users/"
            + urllib.parse.quote(str(user_id))
            + "/tweets?"
            + urllib.parse.urlencode(params)
        )
        status, payload = get_json(url, token)
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        return status, payload, meta.get("next_token")

    return paginate(fetch_page, max_pages)


def read_search(handle: str, token: str, start: str, max_pages: int):
    def fetch_page(page_token):
        params = {
            "query": f"from:{handle} -is:retweet",
            "max_results": "100",
            "start_time": start,
            "tweet.fields": "created_at,public_metrics,referenced_tweets,conversation_id",
        }
        if page_token:
            params["next_token"] = page_token
        url = API + "/tweets/search/recent?" + urllib.parse.urlencode(params)
        status, payload = get_json(url, token)
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        return status, payload, meta.get("next_token")

    return paginate(fetch_page, max_pages)


def finish_live(
    username: str,
    posts: list[dict],
    pages_read: int,
    capped: bool,
    start: str,
    now: str,
) -> dict:
    start_at = parse_time(start)
    end_at = parse_time(now)
    kept = []
    for post in posts:
        if is_retweet(post):
            continue
        created = post.get("created_at")
        if isinstance(created, str) and in_window(created, start_at, end_at):
            kept.append(post)
    if capped:
        window_start = oldest_stamp(kept) or start
    else:
        window_start = start
    body = payload_for(
        username=username,
        protected=False,
        suspended=False,
        posts=kept,
        pages_read=pages_read,
        capped=capped,
        window_start=window_start,
        window_end=now,
    )
    return {"status": "ok", "payload": body}


def read_live(handle: str, token: str, start: str, now: str, max_pages: int) -> dict:
    kind, data = user_lookup(handle, token)
    if kind == "protected":
        return {"status": "protected"}
    if kind == "not_found":
        return {"status": "not_found"}
    username = str(data.get("username") or handle)
    posts, pages_read, capped, problem = read_timeline(str(data["id"]), token, start, max_pages)
    if problem == "protected":
        return {"status": "protected"}
    if problem == "failed":
        posts, pages_read, capped, problem = read_search(handle, token, start, max_pages)
        if problem == "protected":
            return {"status": "protected"}
        if problem == "failed":
            return {"status": "error", "detail": "Live read failed."}
    return finish_live(username, posts, pages_read, capped, start, now)


def parse_archive_time(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z") or "T" in text:
        try:
            return text
        except ValueError:
            return None
    try:
        parsed = datetime.strptime(text, "%a %b %d %H:%M:%S %z %Y")
    except ValueError:
        return None
    return parsed.astimezone(parse_time("1970-01-01T00:00:00Z").tzinfo).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def load_archive_posts(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8")
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError("archive has no array")
    loaded = json.loads(raw[start : end + 1])
    if not isinstance(loaded, list):
        raise ValueError("archive array missing")
    posts = []
    for item in loaded:
        if not isinstance(item, dict):
            continue
        tweet = item.get("tweet") if isinstance(item.get("tweet"), dict) else item
        if not isinstance(tweet, dict):
            continue
        if isinstance(tweet.get("retweeted_status"), dict):
            continue
        created = parse_archive_time(str(tweet.get("created_at") or ""))
        if not created:
            continue
        likes = tweet.get("favorite_count", tweet.get("likes", 0))
        posts.append(
            {
                "id": str(tweet.get("id_str") or tweet.get("id") or ""),
                "text": str(tweet.get("full_text") or tweet.get("text") or ""),
                "created_at": created if created.endswith("Z") or "T" in str(tweet.get("created_at")) else created,
                "public_metrics": {"likes": likes},
                "conversation_id": str(tweet.get("id_str") or tweet.get("id") or ""),
            }
        )
    return posts


def read_archive(path: Path, handle: str, start: str, now: str) -> dict:
    try:
        posts = load_archive_posts(path)
    except (OSError, json.JSONDecodeError, ValueError):
        return {"status": "error", "detail": "Could not read the tweets.js archive."}
    return finish_live(handle, posts, 1, False, start, now)


def read_posts(
    *,
    handle: str,
    backend: str,
    now: str,
    start: str,
    max_pages: int = 20,
    fixtures: str | None = None,
    archive: str | None = None,
    token: str | None = None,
) -> dict:
    cleaned = strip_handle(handle)
    if backend == "fixtures":
        if not fixtures:
            return {"status": "error", "detail": "A fixtures path is required."}
        return read_fixture(Path(fixtures), cleaned, start, now, max_pages)
    if archive:
        return read_archive(Path(archive), cleaned, start, now)
    if not token:
        return {"status": "no_token"}
    return read_live(cleaned, token, start, now, max_pages)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read public posts for Roast My Feed")
    parser.add_argument("--handle", required=True)
    parser.add_argument("--backend", required=True, choices=["fixtures", "live"])
    parser.add_argument("--fixtures", default=None)
    parser.add_argument("--start", default=None)
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--now", default=None)
    parser.add_argument("--archive", default=None)
    return parser.parse_args(argv)


def emit(outcome: dict) -> int:
    status = outcome.get("status")
    if status == "ok":
        print(json.dumps(outcome["payload"], ensure_ascii=False))
        return 0
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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    now = args.now or utc_now_text()
    start = args.start or shift_days(now, -7)
    token = None
    if args.backend == "live" and not args.archive:
        token = os.environ.get("X_BEARER_TOKEN", "").strip()
        if not token:
            print(NO_TOKEN_MESSAGE)
            return 4
    outcome = read_posts(
        handle=args.handle,
        backend=args.backend,
        now=now,
        start=start,
        max_pages=args.max_pages,
        fixtures=args.fixtures,
        archive=args.archive,
        token=token,
    )
    return emit(outcome)


if __name__ == "__main__":
    sys.exit(main())
