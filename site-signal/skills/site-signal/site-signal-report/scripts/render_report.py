#!/usr/bin/env python3
"""Render the Site Signal report (SPEC.md 5.3, 5.6).

Usage:
  python3 render_report.py RUN_DIR [--html] [--ss-home DIR]
  python3 render_report.py --all [--html] [--ss-home DIR]

RUN_DIR must contain report.json (run rank.py first). Writes report.md into the
run dir; --html adds a self-contained report.html (inline CSS only, yellow on
navy, no external assets). --all builds the multi-site scorecard
($SS_HOME/reports/scorecard.md, plus .html with --html) from the latest run of
every domain, with trend arrows from the previous run.

Also prints the chat summary (<=15 lines): score line, top fixes, one caveat
line, and the ship question.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
SCORE_LINE_ORDER = [("SEO", "SEO"), ("GEO", "GEO"), ("AEO", "AEO"), ("overall", "Overall")]

CAVEATS = [
    "Desktop viewport, sampled pages only.",
    "axe cannot test keyboard flow or screen-reader experience; a manual pass is still needed.",
    "Scores are Site Signal rubric scores, not a ranking or WCAG conformance claim.",
    "AI readiness reads raw server HTML (no JavaScript); one URL per run.",
]


def md_env():
    # Markdown holds raw selector/HTML snippets in backticks: no escaping.
    return Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=False,
                       keep_trailing_newline=True, trim_blocks=True, lstrip_blocks=True)


def html_env():
    # HTML report displays snippets as text: escape everything.
    return Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True,
                       keep_trailing_newline=True, trim_blocks=True, lstrip_blocks=True)


def et_now():
    return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M ET")


def fmt_delta(d):
    return f"{d:+d}"


def _change_parts(prev, cur_counts, cur_seo, cur_ai):
    """Human 'change since last scan' parts from a previous history line."""
    parts = []
    if cur_seo and prev.get("overall") is not None:
        d = cur_seo["scores"]["overall"] - prev["overall"]
        if d:
            parts.append(f"overall {fmt_delta(d)} {'↑' if d > 0 else '↓'}")
    if cur_ai and prev.get("ai_ready") is not None:
        d = cur_ai["score"] - prev["ai_ready"]
        if d:
            parts.append(f"AI readiness {fmt_delta(d)} {'↑' if d > 0 else '↓'}")
    prev_serious = (prev.get("axe") or {}).get("serious")
    if prev_serious is not None and cur_counts:
        d = cur_counts["serious"] - prev_serious
        if d:
            parts.append(f"serious a11y {fmt_delta(d)} {'↓' if d < 0 else '↑'}")
    return parts


def change_since_last(ss_home, domain, run_dir, cur_seo, cur_ai, cur_counts):
    """From history.jsonl: deltas vs the previous run of this domain.
    No prior run -> 'first scan' (never a made-up delta)."""
    hist = ss_home / "history.jsonl"
    if not hist.exists():
        return "first scan"
    prev = None
    for line in hist.read_text().splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("domain") == domain and Path(e.get("run", "")).resolve() != run_dir:
            prev = e  # keep the last non-current entry
    if prev is None:
        return "first scan"
    parts = _change_parts(prev, cur_counts, cur_seo, cur_ai)
    return ", ".join(parts) if parts else "no change"


def arrow(d):
    """Direction arrow matching the sign of d: +2 ↑, -2 ↓, 0 →."""
    if d == 0:
        return "→"
    return "↑" if d > 0 else "↓"


def build_context(report, ss_home, run_dir):
    seo = report.get("seo")
    ai = report.get("ai")
    counts = report.get("axe_counts") or {"critical": 0, "serious": 0, "moderate": 0, "minor": 0}
    fixes = []
    for n, i in enumerate(report.get("issues", []), 1):
        fixes.append({
            "n": n, "impact": i["impact"], "dimension": i["dimension"],
            "issue": f"`{i['id']}`: {i['message']}", "where": i.get("where", ""),
            "fix": i["fix"], "effort": i["effort"], "reach": -i.get("reach", -1),
            "evidence": i.get("evidence", []),
        })

    evidence = []
    for i in report.get("issues", []):
        if i["dimension"] == "a11y" and i.get("evidence"):
            for ev in i["evidence"][:2]:
                sel = " ".join(ev.get("target", []))
                snippet = (ev.get("html") or "").replace("\n", " ")
                evidence.append(f"axe `{i['id']}` ({i['impact']}, {-i['reach']} nodes): `{sel}` — sample `{snippet}`")
    passes = {p["id"]: p["message"] for p in (ai or {}).get("passes", [])}
    for pid in ("page-fetch", "robots-training-policy", "robots-search-bots", "ssr-content", "structured-data"):
        if pid in passes:
            evidence.append(f"{pid}: {passes[pid]}")
    if seo and seo.get("schema_types"):
        evidence.append("JSON-LD types found: " + ", ".join(seo["schema_types"]))

    passing = [f"{p['id']}: {p['message']}" for p in (ai or {}).get("passes", [])]
    if report.get("axe_pages"):
        passing.append(f"axe scanned {report['axe_pages']} page(s)")

    return {
        "domain": report.get("domain", "unknown"),
        "ts": et_now(),
        "seo": seo,
        "ai": ai,
        "axe_counts": counts,
        "axe_pages": report.get("axe_pages", 0),
        "change": change_since_last(ss_home, report.get("domain", "unknown"), run_dir, seo, ai, counts),
        "fixes": fixes,
        "evidence": evidence,
        "passing": passing,
        "caveats": CAVEATS,
        "shipped": report.get("shipped", []),
    }


def render_report(run_dir, ss_home, html=False):
    report_path = run_dir / "report.json"
    if not report_path.exists():
        sys.exit(f"error: {report_path} not found — run rank.py on this run dir first")
    report = json.loads(report_path.read_text())
    ctx = build_context(report, ss_home, run_dir)

    md = md_env().get_template("report.md.j2").render(**ctx)
    (run_dir / "report.md").write_text(md)
    if html:
        page = html_env().get_template("report.html.j2").render(**ctx)
        (run_dir / "report.html").write_text(page)
    return ctx


def collect_domains(ss_home):
    """[(domain, [reports oldest->newest])] from $SS_HOME/reports/<domain>/<run>/report.json."""
    out = []
    root = ss_home / "reports"
    if not root.is_dir():
        return out
    for dom_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        runs = []
        for run_dir in sorted(p for p in dom_dir.iterdir() if p.is_dir()):
            rp = run_dir / "report.json"
            if rp.exists():
                try:
                    runs.append(json.loads(rp.read_text()))
                except json.JSONDecodeError:
                    pass
        if runs:
            out.append((dom_dir.name, runs))
    return out


def scorecard_rows(ss_home):
    rows = []
    for domain, runs in collect_domains(ss_home):
        cur = runs[-1]
        prev = runs[-2] if len(runs) > 1 else None
        seo = cur.get("seo")
        counts = cur.get("axe_counts") or {}
        trend = "new"
        if prev:
            bits = []
            if prev.get("seo") and seo:
                d = seo["scores"]["overall"] - prev["seo"]["scores"]["overall"]
                bits.append(f"overall {fmt_delta(d)} {arrow(d)}")
            if prev.get("ai") and cur.get("ai"):
                d = cur["ai"]["score"] - prev["ai"]["score"]
                bits.append(f"ai {fmt_delta(d)} {arrow(d)}")
            if prev.get("axe_counts") and counts:
                d = counts.get("serious", 0) - prev["axe_counts"].get("serious", 0)
                bits.append(f"serious {fmt_delta(d)} {arrow(d)}")
            trend = " · ".join(bits) or "no change"
        grades = (seo or {}).get("grades", {})
        rows.append({
            "domain": domain,
            "run": cur.get("generated", ""),
            "seo": f"{seo['scores']['SEO']} ({grades.get('SEO', '')})" if seo else "—",
            "geo": f"{seo['scores']['GEO']} ({grades.get('GEO', '')})" if seo else "—",
            "aeo": f"{seo['scores']['AEO']} ({grades.get('AEO', '')})" if seo else "—",
            "overall": f"{seo['scores']['overall']} ({grades.get('overall', '')})" if seo else "—",
            "ai": f"{cur['ai']['score']}/100 ({cur['ai']['grade']})" if cur.get("ai") else "—",
            "axe": f"{counts.get('critical', 0)}/{counts.get('serious', 0)}/{counts.get('moderate', 0)}/{counts.get('minor', 0)}",
            "trend": trend,
        })
    return rows


def render_scorecard(ss_home, html=False):
    ctx = {"ts": et_now(), "rows": scorecard_rows(ss_home), "caveats": CAVEATS}
    out_md = ss_home / "reports" / "scorecard.md"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(md_env().get_template("scorecard.md.j2").render(**ctx))
    if html:
        (ss_home / "reports" / "scorecard.html").write_text(
            html_env().get_template("scorecard.html.j2").render(**ctx))
    return ctx


def chat_summary(ctx, report_path):
    lines = [f"Site Signal — {ctx['domain']} — {ctx['ts']}"]
    seo = ctx["seo"]
    if seo:
        s, g = seo["scores"], seo["grades"]
        lines.append(f"**SEO** {s['SEO']} ({g['SEO']}) · **GEO** {s['GEO']} ({g['GEO']}) · "
                     f"**AEO** {s['AEO']} ({g['AEO']}) · **Overall** {s['overall']} ({g['overall']})")
    if ctx["ai"]:
        lines.append(f"**AI readiness** {ctx['ai']['score']}/100 ({ctx['ai']['grade']}) · "
                     f"**axe** {ctx['axe_counts']['critical']} critical · {ctx['axe_counts']['serious']} serious · "
                     f"{ctx['axe_counts']['moderate']} moderate · {ctx['axe_counts']['minor']} minor nodes ({ctx['axe_pages']} pages)")
    lines.append(f"Change since last scan: {ctx['change']}")
    top = ctx["fixes"][:6]
    if top:
        lines.append("Fix first:")
        for f in top:
            lines.append(f"{f['n']}. [{f['impact']} {f['dimension']}] {f['issue']} — {f['where']} (effort {f['effort']})")
    lines.append("Caveat: " + " ".join(ctx["caveats"][:2]))
    lines.append(f"Report: {report_path}")
    lines.append("Ship these as PRs?")
    return lines[:15]


def main():
    ap = argparse.ArgumentParser(description="Render Site Signal report (SPEC.md 5.3/5.6)")
    ap.add_argument("run_dir", nargs="?", help="run directory containing report.json")
    ap.add_argument("--html", action="store_true", help="also write a self-contained HTML file")
    ap.add_argument("--all", action="store_true", help="build the multi-site scorecard")
    ap.add_argument("--ss-home", default="~/SiteSignal", help="Site Signal data dir (default ~/SiteSignal)")
    args = ap.parse_args()
    ss_home = Path(args.ss_home).expanduser()

    if args.all:
        ctx = render_scorecard(ss_home, html=args.html)
        print(f"scorecard: {ss_home / 'reports' / 'scorecard.md'} ({len(ctx['rows'])} sites)")
        return

    if not args.run_dir:
        sys.exit("error: need RUN_DIR (or --all)")
    run_dir = Path(args.run_dir).expanduser().resolve()
    ctx = render_report(run_dir, ss_home, html=args.html)
    for line in chat_summary(ctx, run_dir / "report.md"):
        print(line)


if __name__ == "__main__":
    main()
