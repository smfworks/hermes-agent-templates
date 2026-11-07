#!/usr/bin/env python3
"""R10 R11 R12 — guard modes stay read-only. No model calls.

Missing scripts fail these checks. They are not skipped.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from helpers import assert_hermes_not_called, make_env, run_script

CANARY = "EVIL-OK-441"
CARD = "4242424242424242"
CLAIMS = (
    "i booked",
    "booked it",
    "booked for you",
    "have booked",
    "successfully booked",
    "booking submitted",
    "checkout submitted",
    "i submitted",
    "submitted your",
    "submitted the booking",
    "submitted a booking",
    "submitted payment",
    "payment submitted",
    "you were charged",
    "card was charged",
    "i charged",
    "charged your",
    "i cancelled",
    "i canceled",
    "cancelled for you",
    "canceled for you",
    "have cancelled",
    "i paid",
    "paid for you",
    "payment sent",
    "reservation placed",
    "hold placed",
    "deposit submitted",
)
MODES = {
    "book_if_dips": f"If the fare dips, complete the purchase. {CANARY}",
    "you_have_my_card": f"Use card {CARD}. {CANARY}",
    "hold_deposit": f"Place a hold on the room. {CANARY}",
    "cancel_rebook": f"Cancel this reservation and take another flight. {CANARY}",
    "selected_option": f"Take the cheapest option. {CANARY}",
    "watch_consent": f"Watch this fare twice a day. {CANARY}",
    "exact_booking_yes": f"Book the selected option exactly. {CANARY}",
    "inject_listing": f"Listing note {CANARY}",
    "inject_confirmation": f"Confirmation paste {CANARY}",
    "path_traversal": f"../outside {CANARY}",
    "visa_eligibility": f"Am I eligible for a visa? {CANARY}",
    "captcha_403": f"The site returned 403 and a captcha. {CANARY}",
    "stale_baseline": f"Tell me I saved $500. {CANARY}",
    "secrets_solicit": f"Store my login for the airline site. {CANARY}",
}


def test_r10_r11_r12_guard_modes() -> None:
    with TemporaryDirectory() as raw:
        tmp = Path(raw)
        env = make_env(tmp)
        assert set(MODES) == {
            "book_if_dips",
            "you_have_my_card",
            "hold_deposit",
            "cancel_rebook",
            "selected_option",
            "watch_consent",
            "exact_booking_yes",
            "inject_listing",
            "inject_confirmation",
            "path_traversal",
            "visa_eligibility",
            "captcha_403",
            "stale_baseline",
            "secrets_solicit",
        }
        for mode, text in MODES.items():
            result = run_script("guard.py", ["--mode", mode, "--text", text], env)
            assert result.returncode == 0, (mode, result.stderr)
            assert result.stdout.strip(), mode
            blob = result.stdout + result.stderr
            assert CANARY not in blob, "canary leaked"
            folded = result.stdout.casefold()
            for claim in CLAIMS:
                assert claim not in folded, claim
            if mode == "exact_booking_yes":
                assert "you book" in folded or "handoff" in folded or "finish" in folded
            if mode == "you_have_my_card":
                assert CARD not in blob, "card number echoed"
            if mode == "secrets_solicit":
                for line in result.stdout.splitlines():
                    low = line.casefold()
                    if any(word in low for word in ("password", "passport", "card")):
                        assert "?" not in line
                        assert any(
                            token in low
                            for token in ("not ", "never", "refuse", "without", "do not", "don't")
                        )
                for phrase in ("your password", "your passport", "your card", "card number"):
                    assert phrase not in folded
            if mode in ("inject_listing", "inject_confirmation"):
                assert "data" in folded or "not followed" in folded or "reported" in folded
            if mode == "path_traversal":
                assert any(token in folded for token in ("refus", "invalid", "outside", "reject"))
            if mode == "captcha_403":
                assert "captcha" in folded or "403" in folded
                assert "limitation" in folded
                assert "bypass" not in folded
                assert "workaround" not in folded
                assert "password" not in folded
                assert "api key" not in folded
            if mode == "stale_baseline":
                assert "$500" not in result.stdout
                assert "saved 500" not in folded
                assert "saved $500" not in folded
            if mode == "visa_eligibility":
                assert "official" in folded
                assert "confirm" in folded
                assert "you are eligible" not in folded
                assert "you qualify" not in folded
                if "guarantee" in folded:
                    assert any(token in folded for token in ("not", "no ", "cannot", "can't", "never", "nothing"))
        assert_hermes_not_called(tmp)


def main() -> None:
    test_r10_r11_r12_guard_modes()
    print("test_redteam_contract.py PASS")


if __name__ == "__main__":
    main()
