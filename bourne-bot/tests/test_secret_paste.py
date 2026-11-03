#!/usr/bin/env python3
"""Planted secrets must be refused, and must not appear on stdout or stderr."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "secret_paste.py"

GHP = "ghp_" + ("a" * 36)
SK = "sk-test" + ("B" * (48 - len("sk-test")))
PASSWORD = "password: hunter2-horse-battery"
SEED = (
    "seed phrase: abandon ability able about above absent absorb abstract "
    "absurd abuse access accident"
)
RECOVERY = "recovery code: ABCD-EFGH-IJKL"
CARD = "4242424242424242"
ACCOUNT = "account number: 998877665544"


def run(args: list[str], data: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=data,
        text=True,
        capture_output=True,
        check=False,
    )


def absent(result: subprocess.CompletedProcess[str], secret: str) -> None:
    assert secret not in result.stdout, "secret leaked on stdout"
    assert secret not in result.stderr, "secret leaked on stderr"


def test_planted() -> None:
    assert len(GHP) == 40 and GHP.startswith("ghp_")
    assert len(SK) == 48 and SK.startswith("sk-test")
    blob = "\n".join([GHP, SK, PASSWORD, SEED, RECOVERY, CARD, ACCOUNT, ""])
    result = run([], blob)
    assert result.returncode == 2, result.returncode
    for secret in (GHP, SK, "hunter2-horse-battery", "abandon ability", RECOVERY.split()[-1], CARD, "998877665544"):
        absent(result, secret)
    low = (result.stdout + result.stderr).lower()
    assert "rotate" in low
    assert "stop" in low
    for cls in (
        "api_key",
        "password",
        "seed_phrase",
        "recovery_code",
        "card_number",
        "account_number",
    ):
        assert f"{cls}=" in result.stdout, result.stdout


def test_file_and_stdin() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "paste.txt"
        path.write_text("notes\n" + GHP + "\n", encoding="utf-8")
        result = run([str(path)])
        assert result.returncode == 2
        absent(result, GHP)
        result = run(["-"], SK + "\n")
        assert result.returncode == 2
        absent(result, SK)


def test_clean() -> None:
    sample = (
        "Bourne Bot helps you protect accounts. No passwords, codes, or account numbers, ever.\n"
        "Recovery codes stored offline.\n"
        "Travel is quarterly.\n"
    )
    result = run([], sample)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""


def test_empty_config_fails_closed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        empty = Path(tmp) / "empty.json"
        empty.write_text("", encoding="utf-8")
        result = run(["--config", str(empty)], GHP + "\n")
        assert result.returncode == 2
        absent(result, GHP)
        assert "refusing" in result.stdout.lower()

        blank = Path(tmp) / "blank.json"
        blank.write_text("   \n", encoding="utf-8")
        result = run(["--config", str(blank)], "hello\n")
        assert result.returncode == 2

        obj = Path(tmp) / "obj.json"
        obj.write_text("{}\n", encoding="utf-8")
        result = run(["--config", str(obj)], "hello\n")
        assert result.returncode == 2

        leaked = Path(tmp) / "leak.json"
        leaked.write_text(SK, encoding="utf-8")
        result = run(["--config", str(leaked)], "hello\n")
        assert result.returncode == 2
        absent(result, SK)

        missing = Path(tmp) / "missing.json"
        result = run(["--config", str(missing)], "hello\n")
        assert result.returncode == 2

        ok = Path(tmp) / "ok.json"
        ok.write_text(json.dumps({"patterns": []}) + "\n", encoding="utf-8")
        result = run(["--config", str(ok)], GHP + "\n")
        assert result.returncode == 2
        absent(result, GHP)
        assert "api_key=" in result.stdout

        custom = Path(tmp) / "custom.json"
        custom.write_text(
            json.dumps(
                {"patterns": [{"class": "api_key", "pattern": r"CUSTOMSECRET[0-9]{4}"}]}
            ),
            encoding="utf-8",
        )
        token = "CUSTOMSECRET1234"
        result = run(["--config", str(custom)], "prefix " + token + "\n")
        assert result.returncode == 2
        absent(result, token)


def test_unreadable() -> None:
    result = run(["/no/such/bourne-secret-paste-file"])
    assert result.returncode == 2
    assert "refusing" in result.stdout.lower()


def main() -> None:
    test_planted()
    test_file_and_stdin()
    test_clean()
    test_empty_config_fails_closed()
    test_unreadable()
    print("secret_paste: PASS")


if __name__ == "__main__":
    main()
