#!/usr/bin/env python3
"""S6 S9 — cron consent, the daily check cap, and stop. No model calls.

Missing scripts fail these checks. They are not skipped.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from helpers import (
    CRON_EXPR,
    FIXTURES,
    PRODUCT_KEY,
    WATCH_DETAILS,
    WATCH_LINK,
    WATCH_PARTY,
    WATCH_ROUTE,
    WATCH_SOURCE,
    assert_hermes_not_called,
    load_jobs,
    make_env,
    read_csv_rows,
    read_outbox,
    read_state,
    read_trip_state,
    run_script,
    schedule_expr,
    seed_data,
    seed_trip,
    watch_cmd,
    write_json,
)


def install(data: Path, env: dict, slug: str, jobs: Path, extra: list[str] | None = None, tz: str | None = None):
    args = ["--data", str(data), "--slug", slug, "--jobs", str(jobs)]
    if tz is not None:
        args.extend(["--tz", tz])
    if extra:
        args.extend(extra)
    return run_script("install_cron.py", args, env)


def fare_jobs(path: Path, slug: str) -> list[dict]:
    name = f"fare-hawk-watch-{slug}"
    return [job for job in load_jobs(path) if job.get("name") == name]


def seed_jobs(path: Path) -> None:
    write_json(path, {"jobs": [{"name": "unrelated-job", "schedule": "0 0 * * *", "timezone": "UTC"}]})


def drop_fixture(path: Path) -> None:
    write_json(
        path,
        {
            "route": WATCH_ROUTE,
            "party": WATCH_PARTY,
            "details": WATCH_DETAILS,
            "source": WATCH_SOURCE,
            "link": WATCH_LINK,
            "currency": "USD",
            "baseline": "1000.00",
            "cabin": "economy",
            "room": "standard",
            "product_key": PRODUCT_KEY,
            "departure": "2026-12-10",
            "observations": [
                {
                    "status": "ok",
                    "currency": "USD",
                    "cabin": "economy",
                    "room": "standard",
                    "product_key": PRODUCT_KEY,
                    "price": "949.00",
                    "seen_at": "2026-11-06T15:01:00Z",
                    "nonstop": False,
                    "new_nonstop": False,
                    "sellout": False,
                    "sellout_verified": False,
                    "fees_complete": True,
                    "notes": "",
                }
            ],
        },
    )


def test_s6_without_yes_and_no() -> None:
    with TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = seed_data(tmp)
        env = make_env(tmp)
        jobs = tmp / "jobs.json"
        seed_jobs(jobs)
        seed_trip(data, "lisbon", watch_yes=False)
        bare = install(data, env, "lisbon", jobs)
        assert bare.returncode == 0, bare.stderr
        assert fare_jobs(jobs, "lisbon") == []
        assert [job["name"] for job in load_jobs(jobs)] == ["unrelated-job"]
        assert read_trip_state(data, "lisbon")["watch_yes"] is False
        assert read_state(data)["sentinel"] == "keep-me"

        seed_trip(data, "lisbon", watch_yes=True)
        declined = install(data, env, "lisbon", jobs, ["--no"])
        assert declined.returncode == 0, declined.stderr
        assert fare_jobs(jobs, "lisbon") == []
        assert read_trip_state(data, "lisbon")["watch_yes"] is False
        assert read_state(data)["watch_yes"] is False
        assert read_state(data)["sentinel"] == "keep-me"
        assert read_trip_state(data, "lisbon")["owner_note"] == "keep-me"
        assert_hermes_not_called(tmp)


def test_s6_yes_is_idempotent() -> None:
    with TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = seed_data(tmp)
        env = make_env(tmp)
        jobs = tmp / "jobs.json"
        seed_jobs(jobs)
        seed_trip(data, "lisbon", watch_yes=False, owner_note="keep-me")
        first = install(data, env, "lisbon", jobs, ["--yes"])
        assert first.returncode == 0, first.stderr
        matched = fare_jobs(jobs, "lisbon")
        assert len(matched) == 1
        assert schedule_expr(matched[0]) == CRON_EXPR
        assert matched[0]["timezone"] == "America/New_York"
        assert "unrelated-job" in [job["name"] for job in load_jobs(jobs)]
        state = read_trip_state(data, "lisbon")
        assert state["watch_yes"] is True
        assert state["paused"] is False
        assert state["owner_note"] == "keep-me"
        assert read_state(data)["sentinel"] == "keep-me"

        second = install(data, env, "lisbon", jobs, ["--yes"])
        assert second.returncode == 0, second.stderr
        assert len(fare_jobs(jobs, "lisbon")) == 1
        assert len(load_jobs(jobs)) == 2

        lisbon_jobs = tmp / "lisbon-jobs.json"
        seed_jobs(lisbon_jobs)
        zoned = install(data, env, "lisbon", lisbon_jobs, ["--yes"], tz="Europe/Lisbon")
        assert zoned.returncode == 0, zoned.stderr
        zoned_job = fare_jobs(lisbon_jobs, "lisbon")
        assert len(zoned_job) == 1
        assert zoned_job[0]["timezone"] == "Europe/Lisbon"
        assert schedule_expr(zoned_job[0]) == CRON_EXPR
        assert_hermes_not_called(tmp)


def test_s6_four_check_cap() -> None:
    with TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = seed_data(tmp)
        env = make_env(tmp)
        jobs = tmp / "jobs.json"
        seed_jobs(jobs)
        seed_trip(data, "lisbon", watch_yes=False)
        agreed = install(data, env, "lisbon", jobs, ["--yes"])
        assert agreed.returncode == 0, agreed.stderr
        fixture = FIXTURES / "watch_exact_threshold.json"
        for _ in range(4):
            result = run_script("watch_prices.py", watch_cmd(data, "lisbon", fixture), env)
            assert result.returncode == 0, result.stderr
            assert "Fare Hawk:" not in result.stdout
        rows = read_csv_rows(data / "trips" / "lisbon-prices.csv")
        assert len(rows) == 4
        assert read_trip_state(data, "lisbon")["checks_by_local_date"]["2026-11-06"] == 4
        fifth = run_script("watch_prices.py", watch_cmd(data, "lisbon", fixture), env)
        assert fifth.returncode == 0, fifth.stderr
        assert "stale" in fifth.stdout.casefold()
        assert "Fare Hawk:" not in fifth.stdout
        assert len(read_csv_rows(data / "trips" / "lisbon-prices.csv")) == 4
        assert read_trip_state(data, "lisbon")["checks_by_local_date"]["2026-11-06"] == 4
        assert_hermes_not_called(tmp)


def test_s9_stop_booked_and_reenable() -> None:
    with TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = seed_data(tmp)
        env = make_env(tmp)
        jobs = tmp / "jobs.json"
        seed_jobs(jobs)
        seed_trip(data, "lisbon", watch_yes=False)
        assert install(data, env, "lisbon", jobs, ["--yes"]).returncode == 0
        stopped = install(data, env, "lisbon", jobs, ["--stop"])
        assert stopped.returncode == 0, stopped.stderr
        assert stopped.stdout.casefold().count("stopped") == 1
        assert fare_jobs(jobs, "lisbon") == []
        assert "unrelated-job" in [job["name"] for job in load_jobs(jobs)]
        assert read_trip_state(data, "lisbon")["watch_yes"] is False
        fixture = tmp / "drop.json"
        drop_fixture(fixture)
        silent = run_script("watch_prices.py", watch_cmd(data, "lisbon", fixture), env)
        assert silent.returncode == 0, silent.stderr
        assert "Fare Hawk:" not in silent.stdout
        assert read_outbox(data) == []
        assert not (data / "trips" / "lisbon-prices.csv").exists()

        assert install(data, env, "lisbon", jobs, ["--yes"]).returncode == 0
        assert len(fare_jobs(jobs, "lisbon")) == 1
        caught = run_script("watch_prices.py", watch_cmd(data, "lisbon", fixture), env)
        assert caught.returncode == 0, caught.stderr + caught.stdout
        assert "Fare Hawk:" in caught.stdout
        assert len(read_outbox(data)) == 1
        assert_hermes_not_called(tmp)

    with TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = seed_data(tmp)
        env = make_env(tmp)
        jobs = tmp / "jobs.json"
        seed_jobs(jobs)
        seed_trip(data, "lisbon", watch_yes=False)
        assert install(data, env, "lisbon", jobs, ["--yes"]).returncode == 0
        booked = install(data, env, "lisbon", jobs, ["--booked"])
        assert booked.returncode == 0, booked.stderr
        assert "?" in booked.stdout
        assert "stop" in booked.stdout.casefold()
        assert "stopped" not in booked.stdout.casefold()
        paused = fare_jobs(jobs, "lisbon")
        assert len(paused) == 1
        assert paused[0]["paused"] is True
        assert read_trip_state(data, "lisbon")["paused"] is True
        fixture = tmp / "drop.json"
        drop_fixture(fixture)
        held = run_script("watch_prices.py", watch_cmd(data, "lisbon", fixture), env)
        assert held.returncode == 0, held.stderr
        assert "Fare Hawk:" not in held.stdout
        assert not (data / "trips" / "lisbon-prices.csv").exists()
        assert read_outbox(data) == []

        ended = install(data, env, "lisbon", jobs, ["--booked-stop"])
        assert ended.returncode == 0, ended.stderr
        assert ended.stdout.casefold().count("stopped") == 1
        assert fare_jobs(jobs, "lisbon") == []
        assert read_trip_state(data, "lisbon")["watch_yes"] is False
        assert_hermes_not_called(tmp)


def main() -> None:
    test_s6_without_yes_and_no()
    test_s6_yes_is_idempotent()
    test_s6_four_check_cap()
    test_s9_stop_booked_and_reenable()
    print("test_cron.py PASS")


if __name__ == "__main__":
    main()
