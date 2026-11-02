#!/usr/bin/env python3
"""Merge seo.json + ai.json + axe.json into report.json (SPEC.md 5.3).

Usage: python3 rank.py RUN_DIR [--ss-home DIR] [--overrides FILE] [--no-history]

Ranking key (ascending), exactly as SPEC.md 5.3:

    impact_rank   = {critical:0, serious:1, moderate:2, minor:3}[impact]
    dimension_tie = {a11y:0, ai_ready:1, seo:2, geo:3, aeo:4}
    reach         = -(axe node count | pages affected | 1)
    effort        = {S:0, M:1, L:2}
    key           = (impact_rank, dimension_tie, reach, effort)

Reach: axe issues use the rule's total violation node count across scanned
pages; seo/geo/aeo/ai_ready issues affect the sampled page set as a unit
(the scanners dedupe each check site-wide), so they get 1. Effort uses the
5.3 heuristic table below; the agent may override per issue with an overrides
JSON file mapping "dimension/id" to "S"|"M"|"L", either as a plain letter or
as {"effort": "...", "reason": "..."} — the reason is copied onto the ranked
issue as effort_reason (SPEC.md 5.3: "agent may override with a reason").

Also appends one line to $SS_HOME/history.jsonl:
    {ts, domain, seo, geo, aeo, overall, ai_ready, axe:{critical,serious,moderate,minor}, run}
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

IMPACT_RANK = {"critical": 0, "serious": 1, "moderate": 2, "minor": 3}
DIMENSION_TIE = {"a11y": 0, "ai_ready": 1, "seo": 2, "geo": 3, "aeo": 4}
EFFORT_RANK = {"S": 0, "M": 1, "L": 2}

# SPEC.md 5.3 effort heuristic.
#   S = metadata, attribute, token, or label change in 1-2 files
#       (canonical, og tags, aria-label, color token, heading level).
#   M = new route or file (sitemap, robots, llms.txt, JSON-LD component,
#       breadcrumbs).
#   L = template/content-structure changes across many pages (lead summaries,
#       Q&A blocks, related-posts module).
EFFORT_BY_ID = {
    # S
    "title": "S", "title-missing": "S", "title-length": "S",
    "meta-description": "S", "meta-description-missing": "S", "meta-description-length": "S",
    "canonical": "S", "canonical-missing": "S", "html-lang": "S", "twitter-card": "S",
    "open-graph": "S", "viewport": "S", "meta-robots": "S", "x-robots-tag": "S",
    "single-h1": "S", "h1-missing": "S", "h1-multiple": "S", "heading-order": "S",
    "img-alt": "S", "crawlable-links": "S", "broken-key-page": "S",
    # M
    "sitemap": "M", "sitemap-lastmod": "M", "robots": "M", "robots-txt": "M",
    "robots-ai-policy": "M", "robots-search-bots": "M", "robots-block": "M",
    "llms-txt": "M", "llms-txt-format": "M", "llms-full": "M",
    "structured-data": "M", "jsonld-invalid": "M", "jsonld-entity": "M",
    "article-schema": "M", "article-author": "M", "date-modified": "M",
    "entity-schema": "M", "website-schema": "M", "sameas": "M", "breadcrumbs": "M",
    "faq-schema": "M", "no-faq": "M", "feed": "M",
    "https": "M", "bot-challenge": "M", "page-fetch": "M", "response-time": "M",
    "about-page": "M",
    # L
    "ssr-content": "L", "thin-content": "L", "lead-summary": "L",
    "question-headings": "L", "answer-paragraphs": "L", "no-qa-content": "L",
    "structure": "L", "internal-links": "L", "facts-stats": "L",
    "outbound-citations": "L", "duplicate-title": "L", "duplicate-description": "L",
    "visible-byline": "L",
}
# Attribute/label/token-level axe rules (S per the heuristic); everything else M.
AXE_S_PREFIXES = ("aria-", "label", "image-alt", "button-name", "link-name",
                  "input-", "html-has-lang", "html-lang-valid", "heading-order",
                  "page-has-heading-one", "color-contrast", "duplicate-id")


def effort_for(dimension, issue_id, overrides):
    key = f"{dimension}/{issue_id}"
    if key in overrides:
        value = overrides[key]
        letter = value.get("effort") if isinstance(value, dict) else value
        if letter not in EFFORT_RANK:
            raise SystemExit(f"invalid effort override for {key}: {letter!r} (use S, M or L)")
        return letter
    if issue_id in EFFORT_BY_ID:
        return EFFORT_BY_ID[issue_id]
    if any(issue_id.startswith(p) for p in AXE_S_PREFIXES):
        return "S"
    return "M"


def path_of(url):
    return urlparse(url).path or "/"


def from_seo(seo):
    dim = {"SEO": "seo", "GEO": "geo", "AEO": "aeo"}
    return [
        {
            "impact": i["impact"], "dimension": dim[i["category"]], "id": i["id"],
            "message": i["message"], "fix": i["fix"],
            "where": i.get("page") or "(site-wide)",
            "reach": -1,  # each check is deduped site-wide: one sampled page affected
            "source": "seo", "evidence": [],
        }
        for i in seo.get("issues", [])
    ]


def from_ai(ai):
    where = path_of(ai.get("url", "")) or "/"
    return [
        {
            "impact": i["impact"], "dimension": "ai_ready", "id": i["id"],
            "message": i["message"], "fix": i["fix"], "where": where,
            "reach": -1,  # single-URL scan: one page affected
            "source": "ai", "evidence": [],
        }
        for i in ai.get("issues", [])
    ]


def from_axe(axe):
    agg = {}
    for page in axe:
        if not isinstance(page, dict) or page.get("error"):
            continue
        for v in page.get("violations", []):
            a = agg.setdefault(
                v["id"],
                {"id": v["id"], "impact": v["impact"], "help": v["help"],
                 "description": v.get("description", ""), "nodes": 0, "pages": [],
                 "evidence": []},
            )
            if IMPACT_RANK[v["impact"]] < IMPACT_RANK[a["impact"]]:
                a["impact"] = v["impact"]  # most severe seen for this rule
            a["nodes"] += v.get("nodeCount", len(v.get("nodes", [])))
            if page["url"] not in a["pages"]:
                a["pages"].append(page["url"])
            for n in v.get("nodes", []):
                if len(a["evidence"]) < 3:
                    a["evidence"].append(n)
    out = []
    for a in agg.values():
        pages = a["pages"]
        where = " ".join(path_of(p) for p in pages[:3])
        if len(pages) > 3:
            where += f" +{len(pages) - 3} more pages"
        out.append({
            "impact": a["impact"], "dimension": "a11y", "id": a["id"],
            "message": a["help"],
            "fix": a["description"] or "Fix the accessibility rule; see evidence.",
            "where": where, "reach": -a["nodes"], "nodes": a["nodes"],
            "source": "axe", "evidence": a["evidence"],
        })
    return out


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def domain_of(*reports):
    for rep in reports:
        url = (rep or {}).get("url")
        if url:
            return urlparse(url).netloc or url
    return "unknown"


def axe_counts(axe):
    counts = {"critical": 0, "serious": 0, "moderate": 0, "minor": 0}
    pages = 0
    for page in axe or []:
        if not isinstance(page, dict) or page.get("error"):
            continue
        pages += 1
        for k in counts:
            counts[k] += page.get("counts", {}).get(k, 0)
    return counts, pages


def append_history(ss_home, domain, seo, ai, counts, run_dir):
    line = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "domain": domain,
        "seo": seo["scores"]["SEO"] if seo else None,
        "geo": seo["scores"]["GEO"] if seo else None,
        "aeo": seo["scores"]["AEO"] if seo else None,
        "overall": seo["scores"]["overall"] if seo else None,
        "ai_ready": ai["score"] if ai else None,
        "axe": counts,
        "run": str(run_dir),
    }
    ss_home.mkdir(parents=True, exist_ok=True)
    with open(ss_home / "history.jsonl", "a") as f:
        f.write(json.dumps(line) + "\n")


def main():
    ap = argparse.ArgumentParser(description="Rank merged Site Signal findings (SPEC.md 5.3)")
    ap.add_argument("run_dir", help="run directory containing seo.json, ai.json, axe.json")
    ap.add_argument("--ss-home", default="~/SiteSignal", help="Site Signal data dir (default ~/SiteSignal)")
    ap.add_argument("--overrides", help="JSON file mapping 'dimension/id' to effort S|M|L")
    ap.add_argument("--no-history", action="store_true", help="skip the history.jsonl append")
    args = ap.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    overrides = {}
    if args.overrides:
        with open(args.overrides) as f:
            overrides = json.load(f)

    seo = load_json(run_dir / "seo.json")
    ai = load_json(run_dir / "ai.json")
    axe = load_json(run_dir / "axe.json")

    warnings = []
    if seo is None: warnings.append("seo.json missing or unreadable")
    if ai is None: warnings.append("ai.json missing or unreadable")
    if axe is None: warnings.append("axe.json missing or unreadable")

    issues = []
    if seo: issues += from_seo(seo)
    if ai: issues += from_ai(ai)
    if axe: issues += from_axe(axe)
    for i in issues:
        i["effort"] = effort_for(i["dimension"], i["id"], overrides)
        override = overrides.get(f"{i['dimension']}/{i['id']}")
        if isinstance(override, dict) and override.get("reason"):
            i["effort_reason"] = override["reason"]

    # SPEC.md 5.3 ranking key, ascending.
    issues.sort(key=lambda x: (IMPACT_RANK[x["impact"]], DIMENSION_TIE[x["dimension"]],
                               x["reach"], EFFORT_RANK[x["effort"]]))

    counts, pages_scanned = axe_counts(axe)
    domain = domain_of(seo, ai, {"url": (axe[0].get("url") if axe and isinstance(axe[0], dict) else None)})

    report = {
        "schema": "site-signal.report/1",
        "domain": domain,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources": {n: n + ".json" for n, r in (("seo", seo), ("ai", ai), ("axe", axe)) if r is not None},
        "warnings": warnings,
        "seo": seo,
        "ai": ai,
        "axe": axe,
        "axe_counts": counts,
        "axe_pages": pages_scanned,
        "issues": issues,
        "shipped": [],
    }
    out = run_dir / "report.json"
    with open(out, "w") as f:
        json.dump(report, f, indent=2)
        f.write("\n")

    if not args.no_history:
        ss_home = Path(args.ss_home).expanduser()
        try:
            append_history(ss_home, domain, seo, ai, counts, run_dir)
        except OSError as e:
            print(f"warning: could not append history: {e}", file=sys.stderr)

    seo_s = seo["scores"] if seo else {}
    print(f"ranked {len(issues)} issues for {domain} -> {out}")
    if seo_s:
        print(f"  SEO {seo_s['SEO']} ({seo['grades']['SEO']})  GEO {seo_s['GEO']} ({seo['grades']['GEO']})  "
              f"AEO {seo_s['AEO']} ({seo['grades']['AEO']})  overall {seo_s['overall']} ({seo['grades']['overall']})")
    if ai:
        print(f"  AI readiness {ai['score']}/100 ({ai['grade']})")
    print(f"  axe nodes: {counts['critical']} critical / {counts['serious']} serious / "
          f"{counts['moderate']} moderate / {counts['minor']} minor ({pages_scanned} pages)")
    for i in issues[:5]:
        print(f"  {IMPACT_RANK[i['impact']]}.{DIMENSION_TIE[i['dimension']]} [{i['impact']} {i['dimension']}] "
              f"{i['id']} reach={-i['reach']} effort={i['effort']}: {i['message'][:80]}")


if __name__ == "__main__":
    main()
