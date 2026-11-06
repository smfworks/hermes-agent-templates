#!/usr/bin/env python3
"""S1 — SPEC §8.1 onboarding contract. No model calls.

Missing scripts fail these checks. They are not skipped.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from helpers import (
    ASSUMPTION,
    DEMO,
    FIXTURES,
    FOOTER,
    INTEGRATIONS_SENTENCE,
    INTRO,
    NOW,
    TZ,
    assert_choice_cap,
    assert_hermes_not_called,
    assert_one_question,
    assert_plan_report,
    make_env,
    plan_cmd,
    read_json,
    read_state,
    run_script,
    seed_data,
)


def onboard(data: Path, env: dict, step: str, extra: list[str] | None = None):
    args = ["--data", str(data), "--step", step, "--now", NOW, "--tz", TZ]
    if extra:
        args.extend(extra)
    return run_script("onboard.py", args, env)


def test_s1_resume_skip_and_choices() -> None:
    with TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = seed_data(tmp)
        env = make_env(tmp)
        jobs = tmp / "jobs.json"
        jobs.write_text(json.dumps({"jobs": [{"name": "unrelated-job"}]}), encoding="utf-8")
        jobs_before = jobs.read_bytes()

        intro = onboard(data, env, "intro")
        assert intro.returncode == 0, intro.stderr
        assert intro.stdout.strip() == INTRO, intro.stdout
        assert "cron" not in intro.stdout.casefold()
        assert_one_question(intro.stdout)
        state = read_state(data)
        assert state["setup_step"] == "intro_done"
        assert state["sentinel"] == "keep-me"
        assert not (data / "trips").exists()

        again = onboard(data, env, "intro")
        assert again.returncode == 0, again.stderr
        assert "resume" in again.stdout.casefold()
        assert "cron" not in again.stdout.casefold()
        assert_one_question(again.stdout)

        dest = onboard(data, env, "dest", ["--value", "Lisbon"])
        assert dest.returncode == 0, dest.stderr
        assert_one_question(dest.stdout)
        assert_choice_cap(dest.stdout)
        state = read_state(data)
        assert state["dest"] == "Lisbon"
        assert state["sentinel"] == "keep-me"

        resumed = onboard(data, env, "intro")
        assert resumed.returncode == 0, resumed.stderr
        assert "resume" in resumed.stdout.casefold()
        assert_one_question(resumed.stdout)
        assert read_state(data)["dest"] == "Lisbon"

        dates = onboard(data, env, "dates", ["--value", "2026-12-10..2026-12-17"])
        assert dates.returncode == 0, dates.stderr
        assert_one_question(dates.stdout)
        assert read_state(data)["dates"] == {"start": "2026-12-10", "end": "2026-12-17"}

        party = onboard(data, env, "party", ["--value", "2+8+11"])
        assert party.returncode == 0, party.stderr
        assert_one_question(party.stdout)
        assert read_state(data)["party"] == {"adults": 2, "children": [8, 11]}

        home = onboard(data, env, "home", ["--value", "BOS,PVD"])
        assert home.returncode == 0, home.stderr
        assert read_state(data)["home"] == ["BOS", "PVD"]

        for field in ("cabin", "pace", "budget", "interests"):
            asked = onboard(data, env, field)
            assert asked.returncode in (0, 2), asked.stderr
            assert_one_question(asked.stdout)
            assert_choice_cap(asked.stdout)
            assert field not in read_state(data) or read_state(data).get(field) in (None, "", [])

        loyalty_skip = onboard(data, env, "loyalty", ["--skip"])
        assert loyalty_skip.returncode == 0, loyalty_skip.stderr
        state = read_state(data)
        assert "loyalty" in state["skipped"]
        assert state["loyalty"] == "skipped"

        later = onboard(data, env, "budget", ["--value", "later"])
        assert later.returncode == 0, later.stderr
        assert "budget" in read_state(data)["skipped"]

        threshold = onboard(data, env, "threshold", ["--skip"])
        assert threshold.returncode == 0, threshold.stderr
        stored = read_state(data)["threshold"]
        assert stored["mode"] == "default_usd"
        assert Decimal(str(stored["amount"])) == Decimal("25")
        assert Decimal(str(stored["percent"])) == Decimal("5")
        assert "threshold" in read_state(data)["skipped"]

        for value in ("my password is hunter2", "passport AE1239988", "4111111111111111"):
            refused = onboard(data, env, "loyalty", ["--value", value])
            assert refused.returncode == 2, refused.stderr
            blob = (data / "state.json").read_text(encoding="utf-8")
            for secret in ("hunter2", "AE1239988", "4111111111111111"):
                assert secret not in blob
                assert secret not in refused.stdout
                assert secret not in refused.stderr

        for extra in (["--skip"], ["--value", "gmail"]):
            step = onboard(data, env, "integrations", extra)
            assert step.returncode == 0, step.stderr
            assert INTEGRATIONS_SENTENCE in step.stdout

        watch = onboard(data, env, "watch", ["--value", "yes"])
        assert watch.returncode == 0, watch.stderr
        assert_one_question(watch.stdout)
        assert read_state(data)["watch_yes"] is True
        assert jobs.read_bytes() == jobs_before

        unknown = onboard(data, env, "no-such", ["--value", "x"])
        assert unknown.returncode == 2, unknown.stderr
        assert_hermes_not_called(tmp)


def test_s1_plan_without_optional_setup() -> None:
    with TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = seed_data(tmp)
        env = make_env(tmp)
        assert onboard(data, env, "intro").returncode == 0
        assert onboard(data, env, "dest", ["--value", "Lisbon"]).returncode == 0
        assert onboard(data, env, "dates", ["--value", "2026-12-10..2026-12-17"]).returncode == 0
        assert onboard(data, env, "party", ["--value", "2"]).returncode == 0
        state = read_state(data)
        assert "loyalty" not in state
        assert "integrations" not in state
        assert state.get("setup_complete") is not True

        result = run_script(
            "plan.py",
            plan_cmd(
                data,
                "lisbon",
                FIXTURES / "trip_lisbon.json",
                ["--home", "BOS", "--cabin", "economy", "--bags", "1"],
            ),
            env,
        )
        assert result.returncode == 0, result.stderr
        assert "trips/lisbon.md" in result.stdout.replace("\\", "/")
        assert_plan_report(
            data,
            "lisbon",
            read_json(FIXTURES / "trip_lisbon.json"),
            adults=2,
            children=[],
            bags=1,
            cabin="economy",
            rooms=1,
            origin="BOS",
            destination="Lisbon",
            start="2026-12-10",
            end="2026-12-17",
            watch_on=False,
        )
        report = (data / "trips" / "lisbon.md").read_text(encoding="utf-8")
        assert FOOTER in report
        assert DEMO in report
        assert_hermes_not_called(tmp)


def test_s1_unknown_headcount_and_assumption() -> None:
    with TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = seed_data(tmp)
        env = make_env(tmp)
        assert onboard(data, env, "dest", ["--value", "Lisbon"]).returncode == 0
        assert onboard(data, env, "dates", ["--value", "2026-12-10..2026-12-17"]).returncode == 0
        asked = run_script(
            "plan.py",
            plan_cmd(data, "lisbon", FIXTURES / "trip_lisbon.json", ["--home", "BOS"]),
            env,
        )
        assert asked.returncode == 2, asked.stderr
        folded = asked.stdout.casefold()
        assert "?" in asked.stdout
        assert any(word in folded for word in ("how many", "adults", "travelers", "travellers", "children"))
        assert "780.00" not in asked.stdout
        assert not (data / "trips" / "lisbon.md").exists()

    with TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = seed_data(tmp)
        env = make_env(tmp)
        assert onboard(data, env, "dest", ["--value", "Lisbon"]).returncode == 0
        assert onboard(data, env, "dates", ["--value", "2026-12-10..2026-12-17"]).returncode == 0
        assumed = run_script(
            "plan.py",
            plan_cmd(
                data,
                "lisbon",
                FIXTURES / "trip_lisbon.json",
                ["--home", "BOS", "--assume-one-adult"],
            ),
            env,
        )
        assert assumed.returncode == 0, assumed.stderr
        assert ASSUMPTION in assumed.stdout
        assert_plan_report(
            data,
            "lisbon",
            read_json(FIXTURES / "trip_lisbon.json"),
            adults=1,
            children=[],
            bags=0,
            cabin="economy",
            rooms=1,
            origin="BOS",
            destination="Lisbon",
            start="2026-12-10",
            end="2026-12-17",
            watch_on=False,
            assumption=ASSUMPTION,
        )
        assert "780.00" not in (data / "trips" / "lisbon.md").read_text(encoding="utf-8")
        assert_hermes_not_called(tmp)


def main() -> None:
    test_s1_resume_skip_and_choices()
    test_s1_plan_without_optional_setup()
    test_s1_unknown_headcount_and_assumption()
    print("test_onboard.py PASS")


if __name__ == "__main__":
    main()
