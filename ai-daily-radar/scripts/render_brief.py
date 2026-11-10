#!/usr/bin/env python3
"""Render Standard, Quick, and Friday wrap as Markdown and escaped HTML."""

from __future__ import annotations

import html
import re
from pathlib import Path

from store import FOOTER, is_safe_http_url

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "brief.html"
WRAP_TEMPLATE = ROOT / "templates" / "wrap.html"
PLACEHOLDER_RE = re.compile(r"\{\{([a-z_]+)\}\}")


def html_text(text: str) -> str:
    return "<br>\n".join(html.escape(line) for line in str(text).split("\n"))


def safe_anchor(url: str, label: str | None = None) -> str:
    text = html.escape(label or url)
    if is_safe_http_url(url):
        href = html.escape(url, quote=True)
        return f'<a href="{href}">{text}</a>'
    return text


def md_link(url: str, label: str | None = None) -> str:
    text = label or url
    if is_safe_http_url(url):
        return f"[{text}]({url})"
    return text


def fill(template: str, fields: dict[str, str]) -> str:
    def swap(match: re.Match[str]) -> str:
        return fields.get(match.group(1), match.group(0))

    rendered = PLACEHOLDER_RE.sub(swap, template)
    rendered = re.sub(r"<script\b[^>]*>.*?</script>", "", rendered, flags=re.I | re.S)
    rendered = re.sub(r"<iframe\b[^>]*>.*?</iframe>", "", rendered, flags=re.I | re.S)
    rendered = re.sub(r"javascript:", "", rendered, flags=re.I)
    return rendered


def item_md_standard(item: dict) -> str:
    primary = item.get("primary") or {}
    secondary = item.get("secondary") or {}
    links = md_link(str(primary.get("url") or ""), str(primary.get("title") or "primary"))
    if secondary.get("url"):
        links += ", " + md_link(str(secondary.get("url")), str(secondary.get("title") or "secondary"))
    note = item.get("tag_note") or ""
    vendor_line = ""
    if item.get("tag") == "Vendor-claimed" and item.get("vendor_number") is not None:
        vendor_line = f" Vendor says {item.get('vendor_number')}."
    what = str(item.get("what_changed") or "") + vendor_line
    if note and "unclear" in str(note):
        what = what + " unclear."
    lines = [
        f"**{item.get('headline')}**",
        f"What changed: {what.strip()}",
        f"Why it matters to you: {item.get('why')}",
        f"Tag: [{item.get('tag')}]",
        f"Links: {links}",
    ]
    if item.get("tag_note") and "appeal" in str(item.get("tag_note")).casefold():
        lines.append(str(item["tag_note"]))
    return "\n".join(lines)


def item_md_quick(item: dict) -> str:
    primary = item.get("primary") or {}
    url = str(primary.get("url") or "")
    return f"[{item.get('tag')}] {item.get('headline')}. {item.get('why')} ({url})"


def build_markdown(payload: dict, style: str, date_line: str) -> str:
    items = payload.get("items") or []
    action = payload.get("try_this") or "Read the primary source for the top item. That's 10 minutes."
    banner = payload.get("banner") or ""
    lines = [f"# AI Daily Radar, {date_line}", ""]
    if banner:
        lines.extend([banner, ""])
    if style == "quick":
        for item in items:
            lines.append(item_md_quick(item))
        lines.extend(["", f"**Try this today:** {action}", "", FOOTER, ""])
        return "\n".join(lines)
    for index, item in enumerate(items, start=1):
        lines.append(f"{index}. {item_md_standard(item)}")
        lines.append("")
    lines.extend([f"**Try this today:** {action}", "", FOOTER, ""])
    return "\n".join(lines)


def build_html(payload: dict, style: str, date_line: str) -> str:
    template = TEMPLATE.read_text(encoding="utf-8")
    body = html_text(build_markdown(payload, style, date_line))
    return fill(template, {"title": html.escape(f"AI Daily Radar, {date_line}"), "body": body})


def build_wrap_markdown(payload: dict, week: str) -> str:
    lines_5 = payload.get("week_lines") or []
    ignore = payload.get("ignore") or {}
    archive = payload.get("archive") or []
    parts = [
        f"# Radar Friday wrap, {week}",
        "",
        "## The week in 5 lines",
        "",
    ]
    for line in lines_5[:5]:
        parts.append(f"- {line}")
    parts.extend(
        [
            "",
            "## One thing I'd ignore",
            "",
            f"{ignore.get('headline')}: {ignore.get('reason')}",
            "",
            "## Archive",
            "",
        ]
    )
    for item in archive:
        parts.append(f"- [{item.get('tag')}] {item.get('headline')}")
    parts.extend(["", FOOTER, ""])
    return "\n".join(parts)


def wrap_headline(payload: dict) -> str:
    return str(payload.get("wrap_headline") or "The week's biggest shift is in the local wrap.")


def build_wrap_html(payload: dict, week: str) -> str:
    template = WRAP_TEMPLATE.read_text(encoding="utf-8")
    body = html_text(build_wrap_markdown(payload, week))
    return fill(template, {"title": html.escape(f"Radar Friday wrap, {week}"), "body": body})
