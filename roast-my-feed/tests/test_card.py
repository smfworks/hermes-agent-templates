#!/usr/bin/env python3
"""A5 — SPEC §8.5 share card PNG and text, with no bio or third-party fields."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from helpers import FIXTURES, FOOTER, make_env, run_audit, run_script

BIO = "BIOMARKER9"
DISPLAY = "Third Party Person"
FOLLOWERS = 424242


def test_a5() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = tmp / "data"
        data.mkdir()
        env = make_env(tmp)
        fixture = tmp / "feed-with-bio.json"
        doc = json.loads((FIXTURES / "feed.json").read_text(encoding="utf-8"))
        doc["description"] = BIO
        doc["followers_count"] = FOLLOWERS
        doc["name"] = DISPLAY
        fixture.write_text(json.dumps(doc), encoding="utf-8")

        audit = run_audit(data, "fixtureuser", fixture, env)
        assert audit.returncode == 0, audit.stderr
        roast = data / "roast" / "fixtureuser"
        md = (roast / "roast.md").read_text(encoding="utf-8")
        html = (roast / "roast.html").read_text(encoding="utf-8")
        assert_clean(md)
        assert_clean(html)
        assert_clean(audit.stdout)
        assert_clean(audit.stderr)

        card = run_script(
            "card.py",
            ["--data", str(data), "--handle", "fixtureuser"],
            env,
        )
        assert card.returncode == 0, card.stderr
        assert FOOTER in card.stdout
        low = card.stdout.casefold()
        assert "description" not in low
        assert "followers" not in low
        assert_clean(card.stdout)
        assert_clean(card.stderr)
        png_path = roast / "card.png"
        assert png_path.is_file()
        png = png_path.read_bytes()
        assert png.startswith(b"\x89PNG\r\n\x1a\n")
        assert BIO.encode() not in png
        assert str(FOLLOWERS).encode() not in png
        assert DISPLAY.encode() not in png
    print("A5 PASS")


def assert_clean(text: str) -> None:
    assert BIO not in text
    assert str(FOLLOWERS) not in text
    assert DISPLAY not in text


def main() -> None:
    test_a5()


if __name__ == "__main__":
    main()
