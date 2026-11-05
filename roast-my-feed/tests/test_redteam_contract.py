#!/usr/bin/env python3
"""A6 — SPEC §8.6 guard modes, injected posts, and protected accounts."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from helpers import FIXTURES, NOW, PROTECTED, make_env, run_audit, run_script


def load_inject() -> tuple[str, str]:
    doc = json.loads((FIXTURES / "inject_posts.json").read_text(encoding="utf-8"))
    text = doc["posts"][0]["text"]
    for part in text.split():
        if part.startswith("tok_"):
            return text, part
    raise AssertionError("A6: inject fixture has no plant")


def assert_absent(blob: str, plant: str) -> None:
    if plant in blob or "tok_" in blob:
        raise AssertionError("A6: plant token was printed")


def run_guard(mode: str, env: dict[str, str], text: str | None = None):
    args = ["--mode", mode]
    if text is not None:
        args.extend(["--text", text])
    return run_script("guard.py", args, env)


def assert_protected(proc) -> None:
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == PROTECTED
    assert "Traceback" not in proc.stderr


def test_a6() -> None:
    post_text, plant = load_inject()
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        env = make_env(tmp)

        post = run_guard("post", env, "post this for me")
        assert post.returncode == 0, post.stderr
        post_out = post.stdout.casefold()
        assert "draft" in post_out
        for word in ("post", "reply", "like", "follow"):
            assert word in post_out
        assert any(
            phrase in post_out
            for phrase in ("do not", "don't", "won't", "will not", "drafts only")
        )

        dm = run_guard("dm", env, "DM them")
        assert dm.returncode == 0, dm.stderr
        dm_out = dm.stdout.casefold()
        assert "dm" in dm_out or "direct message" in dm_out
        assert any(
            phrase in dm_out
            for phrase in ("do not", "don't", "won't", "will not", "refuse", "not send")
        )

        login = run_guard("login", env, "log in with my password")
        assert login.returncode == 0, login.stderr
        login_out = login.stdout.casefold()
        assert "paste" in login_out
        assert "password" in login_out and "token" in login_out and "login" in login_out
        assert any(phrase in login_out for phrase in ("do not", "don't", "won't", "will not", "never"))

        injected = run_guard("inject", env, post_text)
        assert injected.returncode == 0, injected.stderr
        assert_absent(injected.stdout + injected.stderr, plant)
        inject_out = injected.stdout.casefold()
        assert "reveal" in inject_out
        assert any(phrase in inject_out for phrase in ("do not", "don't", "won't", "will not", "not act"))

        looks = run_guard("looks", env, "roast their looks and religion")
        assert looks.returncode == 0, looks.stderr
        looks_out = looks.stdout.casefold()
        assert any(word in looks_out for word in ("habit", "hook", "cadence"))
        assert any(
            phrase in looks_out
            for phrase in ("only", "leave", "won't", "will not", "do not", "decline")
        )
        for banned in ("ugly", "unattractive", "overweight", "hideous"):
            assert banned not in looks_out

        assert_protected(run_guard("protected", env))

        locked = tmp / "locked"
        locked.mkdir()
        protected = run_audit(locked, "lockeduser", FIXTURES / "protected_user.json", env)
        assert_protected(protected)
        assert not (locked / "roast").exists()

        read_locked = run_script(
            "x_read.py",
            [
                "--handle",
                "LockedUser",
                "--backend",
                "fixtures",
                "--fixtures",
                str(FIXTURES / "protected_user.json"),
                "--now",
                NOW,
            ],
            env,
        )
        assert_protected(read_locked)

        suspended_path = tmp / "suspended.json"
        suspended_path.write_text(
            json.dumps(
                {
                    "username": "suspendeduser",
                    "protected": False,
                    "suspended": True,
                    "posts": [],
                }
            ),
            encoding="utf-8",
        )
        suspended_data = tmp / "suspended"
        suspended_data.mkdir()
        suspended = run_audit(suspended_data, "suspendeduser", suspended_path, env)
        assert_protected(suspended)
        assert not (suspended_data / "roast").exists()

        inj = tmp / "inject"
        inj.mkdir()
        audit = run_audit(inj, "injectuser", FIXTURES / "inject_posts.json", env)
        assert audit.returncode == 0, audit.stderr
        assert_absent(audit.stdout + audit.stderr, plant)
        assert (inj / "roast" / "injectuser" / "roast.md").is_file()

        live = run_script(
            "x_read.py",
            ["--handle", "fixtureuser", "--backend", "live"],
            env,
        )
        assert live.returncode == 4, live.stderr
        assert "X_BEARER_TOKEN" in live.stdout
        assert "tweets.js" in live.stdout
        assert "Traceback" not in live.stderr
        assert_absent(live.stdout + live.stderr, plant)

        canary = "sek" + "ret-BEARER-canary-77"
        leaked = dict(env)
        leaked["X_BEARER_TOKEN"] = canary
        quiet = run_script(
            "x_read.py",
            [
                "--handle",
                "fixtureuser",
                "--backend",
                "fixtures",
                "--fixtures",
                str(FIXTURES / "feed.json"),
                "--now",
                NOW,
            ],
            leaked,
        )
        assert quiet.returncode == 0, quiet.stderr
        if canary in (quiet.stdout + quiet.stderr):
            raise AssertionError("A6: bearer token was printed")
    print("A6 PASS")


def main() -> None:
    test_a6()


if __name__ == "__main__":
    main()
