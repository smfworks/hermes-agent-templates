# REVIEW — AI Daily Radar

Liam owns this checklist. It points at SPEC §8, items 1–12. Live smoke is his. He runs it on a fresh profile and keeps the evidence.

File-level tests (`bash tests/smoke.sh`) encode the same contract for CI. They are not the live red-team. A green smoke run does not close §8.

Record the profile, the date, the head SHA, and what he saw for each item.

## 1 — Fresh profile

SPEC §8.1. Intro line, one question per turn, answers persist, sample brief offered.

## 2 — Cap and style

SPEC §8.2. Twelve candidates → at most 7. One or two items → Quick. Empty → silent, run logged.

## 3 — Tagging

SPEC §8.3. Every rubric branch and tie-breaker. Exactly one tag.

## 4 — Dedup

SPEC §8.4. URL variants merge. Material updates get `Update:`. Ledger appends only after delivery.

## 5 — Shapes and Friday wrap

SPEC §8.5. Standard and Quick. Friday wrap files plus one headline sentence. HTML escaped.

## 6 — Feedback

SPEC §8.6. Thumbs change rank. Third down → only if major. Material updates still come through.

## 7 — Cron

SPEC §8.7. No yes → no job. Daily Brief and Tune-Up at owner timezone. Tune-Up silent unless first Monday.

## 8 — Live

SPEC §8.8. If a search backend is configured, one real brief. Otherwise record limited parity.

## 9–11 — Red-team

SPEC §8.9–8.11. Live, not only the file-level script.

## 12 — Static

SPEC §8.12. Exactly four skills. LICENSE is SMF Works. Employer-name grep is clean. Config starts grok-4.7 / xai-oauth / _config_version 52.

`python3 tests/test_static.py` is the file-level check for item 12.
