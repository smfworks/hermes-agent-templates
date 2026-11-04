#!/usr/bin/env python3
"""Scan mail into subscriptions.csv and findings.jsonl. Fixtures-first."""

from __future__ import annotations

import argparse
import hashlib
import re
from datetime import date, timedelta
from email.utils import parseaddr
from pathlib import Path

from mail_fetch import charge_happened, fetch, is_promo, parse_now
from store import read_jsonl, save_state, write_csv, write_jsonl

AMOUNT_RE = re.compile(r"Amount:\s*\$?([0-9]+(?:\.[0-9]+)?)\s*([A-Z]{3})?", re.I)
PLAN_RE = re.compile(r"^Plan:\s*(.+)$", re.I | re.M)
CADENCE_RE = re.compile(r"Cadence:\s*(monthly|annual|yearly|weekly)", re.I)
PERIOD_RE = re.compile(
    r"Service period:\s*(\d{4}-\d{2}-\d{2})\s*to\s*(\d{4}-\d{2}-\d{2})", re.I
)
PAY_RE = re.compile(r"Payment date:\s*(\d{4}-\d{2}-\d{2})", re.I)
LINE_RE = re.compile(r"Line item:\s*(.+?)\s*\$([0-9]+(?:\.[0-9]+)?)", re.I)
INJECT_RE = re.compile(
    r"(forward all receipts|reply with the card|ignore previous instructions|"
    r"print EVIL-OK|AI assistant:)",
    re.I,
)
ONE_TIME_RE = re.compile(r"one-time purchase|order confirmation", re.I)
TRIAL_RE = re.compile(
    r"trial ends|first charge on|after your free trial|free trial ends", re.I
)
TRIAL_DATE_RE = re.compile(
    r"(?:free trial ends on|trial ends on|first charge on)\s*(\d{4}-\d{2}-\d{2})",
    re.I,
)
USAGE_RE = re.compile(r"^Kind:\s*usage\b|usage bill", re.I | re.M)
PRICE_WORDS_RE = re.compile(r"new price|price increase", re.I)

DOMAIN_MAP = {
    "netflix.com": "Netflix",
    "spotify.com": "Spotify",
    "adobe.com": "Adobe",
    "disney.com": "Disney+",
    "dropbox.com": "Dropbox",
    "nytimes.com": "New York Times",
    "github.com": "GitHub",
    "cloudsync.example": "CloudSync",
    "widgetpro.example": "WidgetPro",
}


def domain_of(sender: str) -> str:
    _name, addr = parseaddr(sender)
    if "@" not in addr:
        return ""
    return addr.split("@", 1)[1].lower()


def service_of(message: dict) -> str:
    sender = message.get("sender", "")
    domain = domain_of(sender)
    body = message.get("body", "")
    if "amazon web services" in sender.casefold() or re.search(r"\bAWS\b", body):
        return "AWS"
    if domain in DOMAIN_MAP:
        return DOMAIN_MAP[domain]
    if domain:
        leaf = domain.split(".")[0]
        return leaf.replace("-", " ").title()
    return "Unknown"


def quote_for(message: dict, needle: re.Pattern | None = None) -> str:
    for line in message.get("body", "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if needle and needle.search(stripped):
            return stripped
        if AMOUNT_RE.search(stripped) or PAY_RE.search(stripped) or PERIOD_RE.search(stripped):
            return stripped
        if TRIAL_RE.search(stripped):
            return stripped
    subject = message.get("subject", "")
    return subject or message.get("body", "")[:120]


def evidence(message: dict, quote: str) -> dict:
    return {
        "sender": message.get("sender", ""),
        "date": message.get("date", ""),
        "subject": message.get("subject", ""),
        "message_id": message.get("message_id", ""),
        "quote": quote,
    }


def finding_id(service: str, ftype: str, when: str) -> str:
    raw = f"{service}|{ftype}|{when}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def add_months(day: date, months: int) -> date:
    month = day.month - 1 + months
    year = day.year + month // 12
    month = month % 12 + 1
    day_num = min(day.day, [31, 29 if year % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day_num)


def parse_receipt(message: dict) -> dict:
    body = message.get("body", "")
    amount_match = AMOUNT_RE.search(body)
    plan_match = PLAN_RE.search(body)
    cadence_match = CADENCE_RE.search(body)
    period_match = PERIOD_RE.search(body)
    pay_match = PAY_RE.search(body)
    amount = amount_match.group(1) if amount_match else ""
    currency = (amount_match.group(2) or "USD") if amount_match else "USD"
    plan = plan_match.group(1).strip() if plan_match else ""
    cadence = cadence_match.group(1).lower() if cadence_match else "monthly"
    if cadence == "yearly":
        cadence = "annual"
    last_charge = ""
    if pay_match:
        last_charge = pay_match.group(1)
    elif message.get("date"):
        last_charge = message["date"]
    next_renewal = ""
    estimate = "n"
    trial_date = TRIAL_DATE_RE.search(body)
    if period_match:
        next_renewal = period_match.group(2)
    elif trial_date:
        next_renewal = trial_date.group(1)
    elif last_charge:
        try:
            last = date.fromisoformat(last_charge)
        except ValueError:
            last = None
        if last is not None:
            if cadence == "annual":
                next_renewal = add_months(last, 12).isoformat()
            elif cadence == "weekly":
                next_renewal = (last + timedelta(days=7)).isoformat()
            else:
                next_renewal = add_months(last, 1).isoformat()
            estimate = "y"
    kind = "usage" if USAGE_RE.search(body) or service_of(message) == "AWS" else "fixed"
    status = "trial" if TRIAL_RE.search(body) or TRIAL_RE.search(message.get("subject", "")) else "active"
    line_items = [(m.group(1).strip(), float(m.group(2))) for m in LINE_RE.finditer(body)]
    top_item = ""
    if line_items:
        top_item = max(line_items, key=lambda item: item[1])[0]
    return {
        "service": service_of(message),
        "plan": plan,
        "amount": amount,
        "currency": currency,
        "cadence": cadence,
        "last_charge": last_charge,
        "next_renewal": next_renewal,
        "renewal_is_estimate": estimate,
        "status": status,
        "kind": kind,
        "source_msg_ids": message.get("message_id", ""),
        "evidence_quote": quote_for(message, AMOUNT_RE if amount else PAY_RE),
        "notes": top_item,
        "message": message,
        "when": message.get("when"),
        "top_item": top_item,
    }


def is_one_time(message: dict) -> bool:
    blob = f"{message.get('subject', '')}\n{message.get('body', '')}"
    if re.search(r"\bsubscription\b", blob, re.I) and not ONE_TIME_RE.search(blob):
        return False
    return bool(ONE_TIME_RE.search(blob))


def as_float(value: str) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def window_days(state: dict) -> int:
    raw = state.get("window", 5)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 5


def run_scan(data: Path, inbox: Path | None, now: date, backend: str) -> dict:
    since = now - timedelta(days=60)
    messages = fetch(backend, inbox, since)
    injects = []
    receipts: list[dict] = []
    for message in messages:
        body = message.get("body", "")
        if INJECT_RE.search(body) or INJECT_RE.search(message.get("subject", "")):
            injects.append(message)
        if is_promo(message) and not charge_happened(message):
            continue
        if message.get("when") is not None and message["when"] < since:
            continue
        if is_one_time(message):
            continue
        if not charge_happened(message) and not TRIAL_RE.search(
            f"{message.get('subject', '')}\n{body}"
        ):
            continue
        receipts.append(parse_receipt(message))

    grouped: dict[tuple[str, str, str], list[dict]] = {}
    for row in receipts:
        key = (row["service"], row["plan"], row["cadence"])
        grouped.setdefault(key, []).append(row)

    csv_rows = []
    findings = []
    for key, items in grouped.items():
        items_sorted = sorted(
            items,
            key=lambda row: row.get("when") or date.min,
        )
        latest = dict(items_sorted[-1])
        ids = []
        for item in items_sorted:
            mid = item.get("source_msg_ids") or item["message"].get("message_id", "")
            if mid and mid not in ids:
                ids.append(mid)
        latest["source_msg_ids"] = ";".join(ids)
        latest.pop("message", None)
        latest.pop("when", None)
        latest.pop("top_item", None)
        last = latest.get("last_charge") or ""
        if latest.get("cadence") == "monthly" and last:
            try:
                last_day = date.fromisoformat(last)
                if (now - last_day).days >= 45:
                    latest["status"] = "unknown"
            except ValueError:
                pass
        csv_rows.append(latest)

        if latest.get("status") == "unknown":
            src = items_sorted[-1]["message"]
            findings.append(
                {
                    "id": finding_id(latest["service"], "lapsed", last),
                    "type": "lapsed",
                    "service": latest["service"],
                    "evidence": evidence(src, latest.get("evidence_quote") or quote_for(src)),
                    "first_seen": now.isoformat(),
                    "alerted_at": now.isoformat(),
                    "resolved": False,
                }
            )

        amounts = [(item, as_float(item["amount"])) for item in items_sorted]
        numeric = [(item, amt) for item, amt in amounts if amt is not None]
        if len(numeric) >= 2:
            prev_item, prev_amt = numeric[-2]
            new_item, new_amt = numeric[-1]
            if new_amt > prev_amt and latest["kind"] == "fixed":
                src = new_item["message"]
                findings.append(
                    {
                        "id": finding_id(latest["service"], "price_increase", latest["last_charge"]),
                        "type": "price_increase",
                        "service": latest["service"],
                        "evidence": evidence(
                            src,
                            f"Amount: ${prev_amt:.2f} → ${new_amt:.2f}",
                        ),
                        "first_seen": now.isoformat(),
                        "alerted_at": now.isoformat(),
                        "resolved": False,
                        "old": f"{prev_amt:.2f}",
                        "new": f"{new_amt:.2f}",
                    }
                )
            if latest["kind"] == "usage" and prev_amt > 0 and (new_amt - prev_amt) / prev_amt > 0.25:
                src = new_item["message"]
                top = new_item.get("top_item") or "usage"
                findings.append(
                    {
                        "id": finding_id(latest["service"], "usage_spike", latest["last_charge"]),
                        "type": "usage_spike",
                        "service": latest["service"],
                        "evidence": evidence(src, f"Line item: {top}"),
                        "first_seen": now.isoformat(),
                        "alerted_at": now.isoformat(),
                        "resolved": False,
                        "top_item": top,
                    }
                )

        nxt = latest.get("next_renewal") or ""
        if nxt:
            try:
                renew = date.fromisoformat(nxt)
            except ValueError:
                renew = None
            if renew is not None:
                delta = (renew - now).days
                if 0 <= delta <= window_days({}):
                    ftype = "trial_bill" if latest.get("status") == "trial" else "renewal_window"
                    src = items_sorted[-1]["message"]
                    findings.append(
                        {
                            "id": finding_id(latest["service"], ftype, nxt),
                            "type": ftype,
                            "service": latest["service"],
                            "evidence": evidence(src, quote_for(src, TRIAL_RE if ftype == "trial_bill" else PERIOD_RE)),
                            "first_seen": now.isoformat(),
                            "alerted_at": now.isoformat(),
                            "resolved": False,
                        }
                    )

    by_service: dict[str, set[str]] = {}
    for row in csv_rows:
        by_service.setdefault(row["service"], set()).add(row["plan"])
    for service, plans in by_service.items():
        if len(plans) >= 2:
            row = next(r for r in csv_rows if r["service"] == service)
            src_id = row["source_msg_ids"].split(";")[-1]
            src_msg = None
            for item in receipts:
                if item["message"].get("message_id") == src_id:
                    src_msg = item["message"]
                    break
            if src_msg is None and receipts:
                src_msg = receipts[-1]["message"]
            if src_msg:
                findings.append(
                    {
                        "id": finding_id(service, "duplicate", row.get("last_charge") or now.isoformat()),
                        "type": "duplicate",
                        "service": service,
                        "evidence": evidence(src_msg, quote_for(src_msg)),
                        "first_seen": now.isoformat(),
                        "alerted_at": now.isoformat(),
                        "resolved": False,
                        "plans": sorted(plans),
                    }
                )

    for message in injects:
        quote = quote_for(message)
        findings.append(
            {
                "id": finding_id("mail", "inject", message.get("date") or now.isoformat()),
                "type": "inject",
                "service": "mail",
                "evidence": evidence(message, quote),
                "first_seen": now.isoformat(),
                "alerted_at": now.isoformat(),
                "resolved": False,
            }
        )

    existing = {row["id"]: row for row in read_jsonl(data / "findings.jsonl")}
    merged = []
    seen = set()
    for finding in findings:
        if not finding.get("evidence", {}).get("message_id"):
            continue
        if not finding["evidence"].get("quote"):
            continue
        fid = finding["id"]
        if fid in seen:
            continue
        seen.add(fid)
        if fid in existing:
            old = existing[fid]
            finding["first_seen"] = old.get("first_seen", finding["first_seen"])
            finding["alerted_at"] = old.get("alerted_at", finding["alerted_at"])
        merged.append(finding)

    write_csv(data / "subscriptions.csv", csv_rows)
    write_jsonl(data / "findings.jsonl", merged)
    save_state(data / "state.json", {"last_scan": now.isoformat()})
    return {"rows": csv_rows, "findings": merged}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan mail for subscriptions.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--inbox")
    parser.add_argument("--backend", default="fixtures")
    parser.add_argument("--now")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    now = parse_now(args.now)
    inbox = Path(args.inbox) if args.inbox else Path(args.data) / "inbox"
    run_scan(Path(args.data), inbox, now, args.backend)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
