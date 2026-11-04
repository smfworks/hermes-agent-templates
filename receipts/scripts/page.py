#!/usr/bin/env python3
"""Build money-back.md and money-back.html in place."""

from __future__ import annotations

import argparse
import html
import re
from datetime import date
from pathlib import Path

from mail_fetch import parse_now
from store import read_csv, read_jsonl

FOOTER = "Try Hermes: Receipts — The Money-Back Bot by SMF Works"
ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "report.html"

SCRUBBERS = [
    (re.compile(r"card ending \d{4}", re.I), "card ending [redacted]"),
    (re.compile(r"Account ID:\s*\S+", re.I), "Account ID: [redacted]"),
    (re.compile(r"https://\S+", re.I), "[link redacted]"),
    (re.compile(r"\d+\s+Main Street[^\n]*", re.I), "[address redacted]"),
    (re.compile(r"\bacc_[0-9A-Za-z]+\b"), "[redacted]"),
    (re.compile(r"\b4242\b"), "[redacted]"),
]


def scrub(text: str) -> str:
    for pattern, repl in SCRUBBERS:
        text = pattern.sub(repl, text)
    return text


def money(value: str) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def monthly_equiv(row: dict) -> tuple[float | None, str]:
    amt = money(row.get("amount", ""))
    if amt is None:
        return None, "unknown — open receipt"
    cadence = row.get("cadence", "monthly")
    if cadence == "annual":
        return amt / 12.0, f"{amt:.2f}/12"
    return amt, f"{amt:.2f}"


def order_candidates(rows: list[dict], findings: list[dict]) -> list[dict]:
    dup_services = {f["service"] for f in findings if f.get("type") == "duplicate"}
    price_services = {f["service"] for f in findings if f.get("type") == "price_increase"}
    trial_services = {
        f["service"] for f in findings if f.get("type") in {"trial_bill", "trial"}
    }
    lapsed_services = {f["service"] for f in findings if f.get("type") == "lapsed"}
    ranked: list[tuple[int, dict]] = []
    seen = set()

    def add(rank: int, service: str, reason: str, src: str) -> None:
        key = (service, reason)
        if key in seen:
            return
        seen.add(key)
        ranked.append((rank, {"service": service, "reason": reason, "source_date": src}))

    for finding in findings:
        src = (finding.get("evidence") or {}).get("date", "")
        if finding.get("type") == "duplicate":
            add(0, finding["service"], "duplicate plans", src)
        elif finding.get("type") == "price_increase":
            old = finding.get("old")
            new = finding.get("new")
            reason = f"price increase {old} → {new}" if old and new else "price increase"
            add(1, finding["service"], reason, src)
        elif finding.get("type") in {"trial_bill", "trial"}:
            add(2, finding["service"], "trial about to bill", src)
        elif finding.get("type") == "lapsed":
            add(3, finding["service"], "lapsed / unknown", src)
    ranked.sort(key=lambda item: (item[0], item[1]["service"]))
    return [item[1] for item in ranked[:3]]


def render_md(rows: list[dict], findings: list[dict], now: date) -> str:
    fixed = [r for r in rows if r.get("kind") != "usage"]
    usage = [r for r in rows if r.get("kind") == "usage"]
    burn_parts = []
    burn_total = 0.0
    for row in fixed:
        if row.get("status") == "unknown":
            continue
        amt, label = monthly_equiv(row)
        if amt is None:
            continue
        burn_total += amt
        extra = " (annual/12)" if row.get("cadence") == "annual" else ""
        burn_parts.append(f"- {row['service']} {row['plan']}: {label}{extra}")
    window = 5
    renewing = []
    trials = []
    for row in rows:
        nxt = row.get("next_renewal") or ""
        try:
            renew = date.fromisoformat(nxt)
        except ValueError:
            continue
        if 0 <= (renew - now).days <= window:
            if row.get("status") == "trial":
                trials.append(row)
            else:
                renewing.append(row)
    hikes = [f for f in findings if f.get("type") == "price_increase"]
    candidates = order_candidates(rows, findings)
    lines = [
        "# Money Back",
        "",
        f"## Monthly burn",
        f"**{burn_total:.2f} USD / month** (fixed monthly + annual/12 labeled)",
        *burn_parts,
        "",
        "## Usage-billed",
    ]
    if usage:
        for row in usage:
            top = row.get("notes") or "usage"
            amt = row.get("amount") or "unknown — open receipt"
            lines.append(f"- {row['service']}: {amt} {row.get('currency', '')} (top line item: {top})")
    else:
        lines.append("- none")
    lines += ["", "## Renewing this window"]
    if renewing:
        for row in renewing:
            amt = row.get("amount") or "unknown — open receipt"
            est = " estimate" if row.get("renewal_is_estimate") == "y" else ""
            lines.append(f"- {row['service']} {amt} on {row.get('next_renewal')}{est}")
    else:
        lines.append("- none")
    lines += ["", "## Trials about to bill"]
    if trials:
        for row in trials:
            amt = row.get("amount") or "unknown — open receipt"
            lines.append(f"- {row['service']} {amt} on {row.get('next_renewal')}")
    else:
        lines.append("- none")
    lines += ["", "## Price hikes"]
    if hikes:
        for finding in hikes:
            old = finding.get("old", "?")
            new = finding.get("new", "?")
            lines.append(f"- {finding['service']}: {old} → {new}")
    else:
        lines.append("- none")
    lines += ["", "## Top 3 cancel candidates"]
    if candidates:
        for idx, cand in enumerate(candidates, 1):
            lines.append(
                f"{idx}. {cand['service']} — {cand['reason']} — {cand['source_date']} — your call"
            )
    else:
        lines.append("- none")
    lines += ["", "## Subscriptions"]
    lines.append("| service | plan | amount | cadence | status | source |")
    lines.append("|---|---|---|---|---|---|")
    for row in rows:
        amt = row.get("amount") or "unknown — open receipt"
        if row.get("renewal_is_estimate") == "y":
            amt = f"{amt} (estimate {row.get('next_renewal')})"
        src = row.get("notes") or ""
        # source is sender + date, stored in evidence_quote's sibling — use last charge
        source = f"{row.get('last_charge', '')}"
        quote = row.get("evidence_quote", "")
        lines.append(
            f"| {row['service']} | {row['plan']} | {amt} | {row['cadence']} | {row['status']} | {quote} {source} |"
        )
    lines += ["", "## Verified savings", "- none until proof lands in saved_ledger", "", FOOTER, ""]
    return scrub("\n".join(lines))


def render_html(md: str, now: date) -> str:
    if TEMPLATE.is_file():
        seed = TEMPLATE.read_text(encoding="utf-8")
        body = html.escape(md).replace("\n", "<br>\n")
        return seed.replace("{{body}}", body).replace("{{now}}", now.isoformat())
    return (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<title>Money Back</title></head><body><article><pre>"
        + html.escape(md)
        + "</pre></article></body></html>\n"
    )


def run_page(data: Path, now: date) -> None:
    rows = read_csv(data / "subscriptions.csv")
    findings = read_jsonl(data / "findings.jsonl")
    md = render_md(rows, findings, now)
    html_doc = render_html(md, now)
    from store import atomic_write

    atomic_write(data / "money-back.md", md if md.endswith("\n") else md + "\n")
    atomic_write(data / "money-back.html", html_doc if html_doc.endswith("\n") else html_doc + "\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild the Money Back report.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--now")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_page(Path(args.data), parse_now(args.now))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
