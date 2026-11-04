#!/usr/bin/env python3
"""Read-only mail fetch. Fixtures, Gmail readonly, or IMAP readonly."""

from __future__ import annotations

import argparse
import imaplib
import json
import os
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path

GMAIL_QUERY = (
    'newer_than:60d (subject:(receipt OR invoice OR subscription OR renewal OR '
    '"renews" OR "trial" OR "price" OR "your plan") OR "auto-renew" OR '
    '"will renew" OR "free trial ends")'
)
CHARGE_RE = re.compile(
    r"(amount:\s*\$?\d|thanks for your payment|charged|payment date:)",
    re.I,
)
PROMO_LABEL_RE = re.compile(r"promotion", re.I)


def parse_now(value: str | None) -> date:
    if value:
        return date.fromisoformat(value)
    return datetime.now().date()


def parse_eml(raw: bytes, source_name: str) -> dict | None:
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    sender = str(msg.get("From", ""))
    subject = str(msg.get("Subject", ""))
    mid = str(msg.get("Message-ID", "")).strip() or source_name
    date_header = msg.get("Date")
    when: date | None = None
    if date_header:
        try:
            parsed = parsedate_to_datetime(str(date_header))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            when = parsed.date()
        except (TypeError, ValueError, OverflowError):
            when = None
    body = ""
    try:
        extracted = msg.get_body(preferencelist=("plain", "html"))
        if extracted is not None:
            body = extracted.get_content()
    except Exception:
        body = ""
    if not body:
        try:
            body = msg.get_payload(decode=True).decode("utf-8", "replace") if msg.get_payload(decode=True) else ""
        except Exception:
            body = str(msg.get_payload() or "")
    labels = str(msg.get("X-Gmail-Labels", ""))
    return {
        "id": mid,
        "message_id": mid,
        "sender": sender,
        "subject": subject,
        "date": when.isoformat() if when else "",
        "when": when,
        "body": body,
        "labels": labels,
        "source_name": source_name,
    }


def is_promo(message: dict) -> bool:
    labels = message.get("labels", "")
    subject = message.get("subject", "")
    if PROMO_LABEL_RE.search(labels) or PROMO_LABEL_RE.search(subject):
        return True
    body = message.get("body", "")
    if re.search(r"\bmarketing only\b", body, re.I):
        return True
    return False


def charge_happened(message: dict) -> bool:
    blob = f"{message.get('subject', '')}\n{message.get('body', '')}"
    if re.search(r"no charge happened", blob, re.I):
        return False
    return bool(CHARGE_RE.search(blob))


def keep_message(message: dict, since: date) -> bool:
    when = message.get("when")
    if when is not None and when < since:
        return False
    if is_promo(message) and not charge_happened(message):
        return False
    return True


def fetch_fixtures(inbox: Path, since: date) -> list[dict]:
    messages = []
    if not inbox.is_dir():
        return messages
    for path in sorted(inbox.glob("*.eml")):
        parsed = parse_eml(path.read_bytes(), path.name)
        if parsed:
            messages.append(parsed)
    return messages


def fetch_gmail(token_path: Path, since: date) -> list[dict]:
    if not token_path.is_file():
        raise SystemExit(f"Gmail token file missing: {token_path}")
    token = token_path.read_text(encoding="utf-8").strip()
    query = GMAIL_QUERY
    params = urllib.parse.urlencode({"q": query, "maxResults": "100"})
    url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages?{params}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            listing = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise SystemExit(f"Gmail list failed: {exc}") from exc
    messages = []
    for item in listing.get("messages") or []:
        mid = item.get("id")
        if not mid:
            continue
        get_url = (
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/"
            + urllib.parse.quote(mid)
            + "?format=raw"
        )
        get_req = urllib.request.Request(
            get_url, headers={"Authorization": f"Bearer {token}"}
        )
        try:
            with urllib.request.urlopen(get_req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError:
            continue
        raw_b64 = payload.get("raw")
        if not raw_b64:
            continue
        import base64

        raw = base64.urlsafe_b64decode(raw_b64 + "==")
        parsed = parse_eml(raw, mid)
        if parsed:
            messages.append(parsed)
    return messages


def fetch_imap(host: str, user: str, password: str, since: date) -> list[dict]:
    context = ssl.create_default_context()
    client = imaplib.IMAP4_SSL(host, ssl_context=context)
    try:
        client.login(user, password)
        # readonly=True sends a read-only select (no mailbox writes).
        typ, _ = client.select("INBOX", readonly=True)
        if typ != "OK":
            raise SystemExit("IMAP inbox could not be opened read-only")
        since_str = since.strftime("%d-%b-%Y")
        typ, data = client.search(None, "SINCE", since_str)
        if typ != "OK" or not data or not data[0]:
            return []
        messages = []
        for uid in data[0].split():
            typ, fetched = client.fetch(uid, "(RFC822)")
            if typ != "OK" or not fetched:
                continue
            raw = fetched[0][1]
            if isinstance(raw, bytes):
                parsed = parse_eml(raw, uid.decode("ascii", "replace"))
                if parsed:
                    messages.append(parsed)
        return messages
    finally:
        try:
            client.logout()
        except Exception:
            pass


def fetch(
    backend: str,
    inbox: Path | None,
    since: date,
    token_path: Path | None = None,
    imap_host: str | None = None,
    imap_user: str | None = None,
    imap_password: str | None = None,
) -> list[dict]:
    if backend == "fixtures":
        if inbox is None:
            return []
        return fetch_fixtures(inbox, since)
    if backend == "gmail":
        path = token_path or Path(os.environ.get("GMAIL_TOKEN_PATH", ""))
        return fetch_gmail(path, since)
    if backend == "imap":
        host = imap_host or os.environ.get("IMAP_HOST", "")
        user = imap_user or os.environ.get("IMAP_USER", "")
        password = imap_password or os.environ.get("IMAP_PASSWORD", "")
        if not host or not user or not password:
            raise SystemExit("IMAP host/user/password missing")
        return fetch_imap(host, user, password, since)
    raise SystemExit(f"unknown backend {backend}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only mail fetch for Receipts.")
    parser.add_argument("--backend", default="fixtures", choices=("fixtures", "gmail", "imap"))
    parser.add_argument("--inbox")
    parser.add_argument("--now")
    parser.add_argument("--token")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    now = parse_now(args.now)
    since = now - timedelta(days=60)
    inbox = Path(args.inbox) if args.inbox else None
    token = Path(args.token) if args.token else None
    messages = fetch(args.backend, inbox, since, token_path=token)
    public = []
    for message in messages:
        public.append(
            {
                "id": message["id"],
                "sender": message["sender"],
                "subject": message["subject"],
                "date": message["date"],
                "message_id": message["message_id"],
            }
        )
    print(json.dumps(public, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
