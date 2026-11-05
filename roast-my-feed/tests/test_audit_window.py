#!/usr/bin/env python3
"""A3 — SPEC §8.3 30-day rerun, 20-page cap, and user resolution."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from helpers import (
    FIXTURES,
    NOW,
    WINDOW_30,
    WINDOW_7,
    make_env,
    read_history,
    run_audit,
    run_script,
)

XREAD_KEYS = {
    "username",
    "protected",
    "suspended",
    "posts",
    "pages_read",
    "capped",
    "window_start",
    "window_end",
}


def x_read(env: dict[str, str], handle: str, fixture: Path, extra: list[str] | None = None):
    args = [
        "--handle",
        handle,
        "--backend",
        "fixtures",
        "--fixtures",
        str(fixture),
        "--now",
        NOW,
    ]
    if extra:
        args.extend(extra)
    return run_script("x_read.py", args, env)


def load_xread(proc) -> dict:
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert set(payload) == XREAD_KEYS, sorted(payload)
    return payload


def test_a3() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        env = make_env(tmp)

        flat = load_xread(x_read(env, "fixtureuser", FIXTURES / "feed.json"))
        ids = {post["id"] for post in flat["posts"]}
        assert flat["username"] == "fixtureuser"
        assert flat["protected"] is False and flat["suspended"] is False
        assert flat["pages_read"] == 1 and flat["capped"] is False
        assert flat["window_start"] == WINDOW_7
        assert flat["window_end"] == NOW
        assert len(flat["posts"]) == 45
        assert "best1" in ids and "emoji4" in ids and "edge_start" in ids and "edge_now" in ids
        assert "rt1" not in ids and "rt2" not in ids and "old1" not in ids and "future1" not in ids

        sparse_read = load_xread(x_read(env, "sparseuser", FIXTURES / "sparse_7d.json"))
        sparse_ids = {post["id"] for post in sparse_read["posts"]}
        assert len(sparse_read["posts"]) == 12
        assert sparse_read["capped"] is False
        assert sparse_read["window_start"] == WINDOW_7
        assert all(post_id.startswith("s7-") for post_id in sparse_ids)
        assert "tooold1" not in sparse_ids

        month = load_xread(
            x_read(
                env,
                "sparseuser",
                FIXTURES / "sparse_7d.json",
                ["--start", WINDOW_30],
            )
        )
        month_ids = {post["id"] for post in month["posts"]}
        assert len(month["posts"]) == 37
        assert month["window_start"] == WINDOW_30
        assert "tooold1" not in month_ids
        assert any(post_id.startswith("s30-") for post_id in month_ids)

        data = tmp / "sparse"
        data.mkdir()
        audit = run_audit(data, "sparseuser", FIXTURES / "sparse_7d.json", env)
        assert audit.returncode == 0, audit.stderr
        history = read_history(data)
        assert len(history) == 1
        assert history[0]["handle"] == "sparseuser"
        assert history[0]["posts_in_window"] == 37
        assert history[0]["window_start"] == WINDOW_30
        assert history[0]["window_end"] == NOW
        assert history[0]["at"] == NOW
        report = (data / "roast" / "sparseuser" / "roast.md").read_text(encoding="utf-8")
        assert WINDOW_30 in report and NOW in report

        capped = load_xread(x_read(env, "capuser", FIXTURES / "paged_cap.json"))
        assert capped["username"] == "capuser"
        assert capped["pages_read"] == 20 and capped["capped"] is True
        assert len(capped["posts"]) == 500
        assert capped["window_start"] == "2026-09-01T00:00:00Z"
        assert capped["window_end"] == NOW
        assert any(post["id"] == "oldest500" for post in capped["posts"])

        cap_data = tmp / "cap"
        cap_data.mkdir()
        cap_audit = run_audit(cap_data, "capuser", FIXTURES / "paged_cap.json", env)
        assert cap_audit.returncode == 0, cap_audit.stderr
        cap_history = read_history(cap_data)
        assert cap_history[0]["posts_in_window"] == 500
        assert cap_history[0]["window_start"] == "2026-09-01T00:00:00Z"
        assert cap_history[0]["window_end"] == NOW
        cap_md = (cap_data / "roast" / "capuser" / "roast.md").read_text(encoding="utf-8")
        cap_blob = cap_md + cap_audit.stdout
        assert "2026-09-01T00:00:00Z" in cap_blob
        assert NOW in cap_blob

        missing = tmp / "missing"
        missing.mkdir()
        not_found = run_audit(missing, "fixtureuser", FIXTURES / "not_found.json", env)
        assert not_found.returncode == 2, not_found.stderr
        assert "profile link" in not_found.stdout.casefold(), not_found.stdout
        assert "Traceback" not in not_found.stderr
        assert not (missing / "roast").exists()

        mismatch = tmp / "mismatch"
        mismatch.mkdir()
        other = run_audit(mismatch, "nobody", FIXTURES / "feed.json", env)
        assert other.returncode == 2
        assert "profile link" in other.stdout.casefold()

        read_missing = x_read(env, "fixtureuser", FIXTURES / "not_found.json")
        assert read_missing.returncode == 2
        assert "profile link" in read_missing.stdout.casefold()
        assert "Traceback" not in read_missing.stderr
    print("A3 PASS")


def main() -> None:
    test_a3()


if __name__ == "__main__":
    main()
