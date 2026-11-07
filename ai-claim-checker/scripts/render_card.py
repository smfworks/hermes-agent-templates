#!/usr/bin/env python3
"""Render a local Markdown and static HTML claim card. Escape all source text."""

from __future__ import annotations

import csv
import html
import io
import re
from pathlib import Path

from store import (
    DATE_NOT_STATED,
    FIXTURE_BANNER,
    FOOTER,
    NONE_FOUND,
    VERDICTS,
    check_date,
    is_safe_http_url,
)

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "claim-card.html"
PLACEHOLDER_RE = re.compile(r"\{\{([a-z_]+)\}\}")


def html_text(text: str) -> str:
    return "<br>\n".join(html.escape(line) for line in str(text).split("\n"))


def safe_anchor(url: str, label: str | None = None) -> str:
    text = label or url
    escaped = html.escape(text)
    if is_safe_http_url(url):
        href = html.escape(url, quote=True)
        return f'<a href="{href}">{escaped}</a>'
    return escaped


def md_link(url: str, label: str | None = None) -> str:
    text = label or url
    if is_safe_http_url(url):
        return f"[{text}]({url})"
    return text


def three_lines(claims: list[dict]) -> list[str]:
    holds = [row for row in claims if row.get("verdict") == "supported"]
    vendor = [row for row in claims if row.get("verdict") == "vendor-only"]
    careful = [
        row
        for row in claims
        if row.get("verdict") in {"contradicted", "unverifiable"}
    ]
    line1 = (
        "What holds up: "
        + "; ".join(str(row.get("text") or row.get("id")) for row in holds)
        if holds
        else "What holds up: nothing independently confirmed this run."
    )
    line2 = (
        "What is vendor-only: "
        + "; ".join(str(row.get("text") or row.get("id")) for row in vendor)
        if vendor
        else "What is vendor-only: no vendor-only rows this run."
    )
    line3 = (
        "What to be careful repeating: "
        + "; ".join(str(row.get("text") or row.get("id")) for row in careful)
        if careful
        else "What to be careful repeating: no contradicted or unverifiable rows this run."
    )
    return [line1, line2, line3]


def change_mind(claims: list[dict]) -> str:
    lines = []
    for row in claims:
        verdict = row.get("verdict")
        if verdict == "supported":
            lines.append(
                f"{row.get('id')}: an independent read under mismatched settings, or a later independent disagreement."
            )
        elif verdict == "vendor-only":
            lines.append(
                f"{row.get('id')}: a named independent source read under comparable settings that agrees or disagrees."
            )
        elif verdict == "contradicted":
            lines.append(
                f"{row.get('id')}: an independent reproduction under the same settings that matches the claim."
            )
        else:
            lines.append(
                f"{row.get('id')}: the missing methodology, full table, or reachable independent write-up."
            )
    return "\n".join(lines) if lines else "A reachable primary source with stated settings."


def source_list_md(sources: list[dict]) -> str:
    lines = []
    for source in sources:
        pub = source.get("published_label") or source.get("published") or DATE_NOT_STATED
        retrieved = source.get("retrieved_at") or DATE_NOT_STATED
        url = source.get("url") or ""
        link = md_link(url) if url else ""
        lines.append(
            f"- {source.get('id')}: {source.get('title')} ({source.get('role')}). "
            f"Published {pub}. Retrieved {retrieved}. {link}"
        )
    return "\n".join(lines)


def source_list_html(sources: list[dict]) -> str:
    parts = []
    for source in sources:
        pub = source.get("published_label") or source.get("published") or DATE_NOT_STATED
        retrieved = source.get("retrieved_at") or DATE_NOT_STATED
        url = source.get("url") or ""
        title = html.escape(str(source.get("title") or source.get("id")))
        body = (
            f"{html.escape(str(source.get('id')))}: {title} "
            f"({html.escape(str(source.get('role')))}). "
            f"Published {html.escape(str(pub))}. Retrieved {html.escape(str(retrieved))}. "
            f"{safe_anchor(url) if url else ''}"
        )
        parts.append(body)
    return "<br>\n".join(parts)


def table_md(claims: list[dict], checked_on: str) -> str:
    header = (
        "| Claim | Verdict | Primary source | Independent evidence | Notes | Checked on |\n"
        "|---|---|---|---|---|---|"
    )
    rows = [header]
    for row in claims:
        verdict = row.get("verdict")
        if verdict not in VERDICTS:
            verdict = "unverifiable"
        claim_text = str(row.get("text") or "")
        if row.get("value") is not None:
            claim_text = f"{claim_text} ({row.get('value')})"
        if verdict == "contradicted" and row.get("contradicted_values"):
            both = row["contradicted_values"]
            claim_text = (
                f"{claim_text}; independent value {both.get('independent')}"
            )
        cells = [
            claim_text,
            verdict,
            str(row.get("primary_text") or NONE_FOUND),
            str(row.get("independent_text") or NONE_FOUND),
            str(row.get("notes") or ""),
            checked_on,
        ]
        escaped = [cell.replace("|", "\\|").replace("\n", " ") for cell in cells]
        rows.append("| " + " | ".join(escaped) + " |")
    return "\n".join(rows)


def table_rows_html(claims: list[dict], checked_on: str) -> str:
    chunks = []
    for row in claims:
        verdict = row.get("verdict") if row.get("verdict") in VERDICTS else "unverifiable"
        claim_text = str(row.get("text") or "")
        if row.get("value") is not None:
            claim_text = f"{claim_text} ({row.get('value')})"
        if verdict == "contradicted" and row.get("contradicted_values"):
            both = row["contradicted_values"]
            claim_text = f"{claim_text}; independent value {both.get('independent')}"
        cells = [
            html_text(claim_text),
            html.escape(verdict),
            html_text(str(row.get("primary_text") or NONE_FOUND)),
            html_text(str(row.get("independent_text") or NONE_FOUND)),
            html_text(str(row.get("notes") or "")),
            html.escape(checked_on),
        ]
        tds = "".join(f"<td>{cell}</td>" for cell in cells)
        chunks.append(f"<tr>{tds}</tr>")
    return "\n".join(chunks)


def not_checkable_text(items: list) -> str:
    if not items:
        return "None."
    lines = []
    for item in items:
        if isinstance(item, dict):
            lines.append(str(item.get("text") or item))
        else:
            lines.append(str(item))
    return "\n".join(lines)


def build_markdown(payload: dict, checked_on: str, style: str) -> str:
    title = str(payload.get("title") or "AI claim check")
    lines = [
        f"# {title}",
        "",
        f"Checked on {checked_on} (America/New_York unless the owner timezone is stored).",
        f"Run {payload.get('run_id')}. Input: {payload.get('input_label') or 'pasted or fetched this run'}.",
    ]
    if payload.get("fixture"):
        lines.append(FIXTURE_BANNER)
    if payload.get("unreadable_input"):
        lines.append(f"Unreadable or omitted input: {payload['unreadable_input']}")
    if payload.get("owner_supplied"):
        lines.append("Pasted text is owner-supplied and was independently researched.")
    omitted = payload.get("omitted_count") or 0
    if omitted:
        lines.append(f"Omitted {omitted} less specific claims (cap eight).")
    lines.extend(["", table_md(payload.get("claims") or [], checked_on), ""])
    lines.extend(["## Not checkable", "", not_checkable_text(payload.get("not_checkable") or []), ""])
    bottom = three_lines(payload.get("claims") or [])
    lines.extend(["## Bottom line", "", *bottom, ""])
    lines.extend(["## What would change my mind", "", change_mind(payload.get("claims") or []), ""])
    lines.extend(["## Sources", "", source_list_md(payload.get("sources") or []), "", FOOTER, ""])
    if style == "brief":
        bullets = []
        for row in (payload.get("claims") or [])[:3]:
            bullets.append(
                f"- {row.get('verdict')}: {row.get('text')} "
                f"({row.get('primary_text')})"
            )
        return "\n".join(
            [
                f"# {title} (brief)",
                "",
                *bottom,
                "",
                *bullets,
                "",
                f"Checked on {checked_on}.",
                "",
                FOOTER,
                "",
            ]
        )
    return "\n".join(lines)


def build_html(payload: dict, checked_on: str) -> str:
    template = TEMPLATE.read_text(encoding="utf-8")
    title = str(payload.get("title") or "AI claim check")
    meta_bits = [
        f"Checked on {checked_on}",
        f"Run {payload.get('run_id')}",
    ]
    if payload.get("fixture"):
        meta_bits.append(FIXTURE_BANNER)
    if payload.get("owner_supplied"):
        meta_bits.append("Pasted text is owner-supplied.")
    fields = {
        "title": html.escape(title),
        "meta": html_text("\n".join(meta_bits)),
        "rows": table_rows_html(payload.get("claims") or [], checked_on),
        "not_checkable": html_text(not_checkable_text(payload.get("not_checkable") or [])),
        "bottom_line": html_text("\n".join(three_lines(payload.get("claims") or []))),
        "change_mind": html_text(change_mind(payload.get("claims") or [])),
        "sources": source_list_html(payload.get("sources") or []),
    }

    def swap(match: re.Match[str]) -> str:
        return fields.get(match.group(1), match.group(0))

    rendered = PLACEHOLDER_RE.sub(swap, template)
    # Never keep a source-supplied script tag or remote embed.
    rendered = re.sub(r"<script\b[^>]*>.*?</script>", "", rendered, flags=re.I | re.S)
    rendered = re.sub(r"<iframe\b[^>]*>.*?</iframe>", "", rendered, flags=re.I | re.S)
    rendered = re.sub(r"javascript:", "", rendered, flags=re.I)
    return rendered


def sources_csv(sources: list[dict]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["id", "title", "url", "role", "published", "retrieved_at", "excerpt"])
    for source in sources:
        writer.writerow(
            [
                source.get("id") or "",
                source.get("title") or "",
                source.get("url") or "",
                source.get("role") or "",
                source.get("published_label") or source.get("published") or DATE_NOT_STATED,
                source.get("retrieved_at") or "",
                source.get("excerpt") or "",
            ]
        )
    return buffer.getvalue()


def chat_summary(payload: dict, md_path: Path, html_path: Path, style: str) -> str:
    claims = payload.get("claims") or []
    bits = [f"{row.get('verdict')}: {row.get('text')}" for row in claims[:4]]
    paths = f"{md_path.as_posix()}\n{html_path.as_posix()}"
    return "\n".join([*bits, paths, FOOTER]) + "\n"
