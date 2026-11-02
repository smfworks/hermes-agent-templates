"""Offline tests for rank.py (SPEC.md 5.3).

Pins the 5.3 ranking key exactly: ascending
(impact_rank, dimension_tie {a11y:0, ai_ready:1, seo:2, geo:3, aeo:4}, reach,
effort), the reach aggregation from axe node counts, effort from the 5.3
heuristic table, and effort overrides with a recorded reason. Also pins the
report.json shape, the history.jsonl append, and the missing-report warnings.

rank.py runs in-process with a patched argv; every invocation passes either
--ss-home (a temp dir) or --no-history so the real ~/SiteSignal is untouched.
"""

import json
import sys

import pytest


def _write_reports(run_dir, seo=None, ai=None, axe=None):
    run_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in (("seo.json", seo), ("ai.json", ai), ("axe.json", axe)):
        if payload is not None:
            (run_dir / name).write_text(json.dumps(payload, indent=2) + "\n")


def _viol(viol_id, impact, node_count):
    return {
        "id": viol_id, "impact": impact, "help": f"{viol_id} help",
        "description": f"Fix {viol_id}.",
        "nodes": [{"target": [f"#{viol_id}"], "html": f"<{viol_id}>", "failureSummary": "fix it"}],
        "nodeCount": node_count,
    }


def _axe_page(url, violations, counts):
    return {"url": url, "finalUrl": url, "counts": counts, "violations": violations, "links": []}


SEO_REPORT = {
    "url": "https://example.test/",
    "scores": {"SEO": 75, "GEO": 88, "AEO": 100, "overall": 86},
    "grades": {"SEO": "C", "GEO": "B", "AEO": "A", "overall": "B"},
    "issues": [
        {"category": "SEO", "impact": "serious", "id": "viewport", "message": "No viewport meta.", "fix": "Add viewport.", "page": "/"},
        {"category": "GEO", "impact": "serious", "id": "article-schema", "message": "Content page lacks Article JSON-LD.", "fix": "Add it.", "page": "/books/slug"},
        {"category": "AEO", "impact": "serious", "id": "no-qa-content", "message": "No question-style headings.", "fix": "Add Q&A.", "page": None},
        {"category": "SEO", "impact": "minor", "id": "twitter-card", "message": "No twitter:card.", "fix": "Add one.", "page": "/"},
        {"category": "SEO", "impact": "minor", "id": "zz-custom", "message": "Custom minor.", "fix": "Fix it.", "page": "/"},
        {"category": "GEO", "impact": "minor", "id": "website-schema", "message": "No WebSite schema.", "fix": "Add it.", "page": None},
    ],
}

AI_REPORT = {
    "url": "https://example.test/",
    "score": 65, "grade": "C",
    "issues": [
        {"impact": "critical", "id": "page-fetch", "message": "Page did not load.", "fix": "Serve 200."},
        {"impact": "serious", "id": "structured-data", "message": "No JSON-LD.", "fix": "Add schema."},
    ],
    "passes": [],
}

AXE_REPORT = [
    _axe_page("https://example.test/", [
        _viol("critical-rule", "critical", 1),
        _viol("serious-five", "serious", 5),
        _viol("serious-two", "serious", 2),
    ], {"critical": 1, "serious": 7, "moderate": 0, "minor": 0}),
]


def _run_rank(rank_ns, monkeypatch, run_dir, *extra_args):
    ns = rank_ns()
    monkeypatch.setattr(sys, "argv", ["rank.py", str(run_dir), *extra_args])
    ns["main"]()
    return json.loads((run_dir / "report.json").read_text())


def test_ranking_key_order(rank_ns, monkeypatch, tmp_path):
    run = tmp_path / "run"
    _write_reports(run, SEO_REPORT, AI_REPORT, AXE_REPORT)
    report = _run_rank(rank_ns, monkeypatch, run, "--no-history")

    # (impact_rank, dimension_tie, reach, effort) ascending — a11y first within
    # the same impact, then ai_ready, seo, geo, aeo; bigger axe reach first;
    # S before M before L on ties.
    assert [i["id"] for i in report["issues"]] == [
        "critical-rule",    # (0, a11y 0, reach -1, M)
        "page-fetch",       # (0, ai_ready 1, reach -1, M)
        "serious-five",     # (1, a11y 0, reach -5, M)
        "serious-two",      # (1, a11y 0, reach -2, M)
        "structured-data",  # (1, ai_ready 1, reach -1, M)
        "viewport",         # (1, seo 2, reach -1, S)
        "article-schema",   # (1, geo 3, reach -1, M)
        "no-qa-content",    # (1, aeo 4, reach -1, L)
        "twitter-card",     # (3, seo 2, reach -1, S)
        "zz-custom",        # (3, seo 2, reach -1, M fallback)
        "website-schema",   # (3, geo 3, reach -1, M)
    ]
    assert [i["dimension"] for i in report["issues"]] == [
        "a11y", "ai_ready", "a11y", "a11y", "ai_ready",
        "seo", "geo", "aeo", "seo", "seo", "geo"]
    assert [i["impact"] for i in report["issues"][:2]] == ["critical", "critical"]


def test_effort_from_the_53_heuristic_table(rank_ns, monkeypatch, tmp_path):
    run = tmp_path / "run"
    _write_reports(run, SEO_REPORT, AI_REPORT, AXE_REPORT)
    report = _run_rank(rank_ns, monkeypatch, run, "--no-history")
    effort = {i["id"]: i["effort"] for i in report["issues"]}
    assert effort == {
        "critical-rule": "M",   # unknown axe rule, no S prefix -> M
        "page-fetch": "M",
        "serious-five": "M",
        "serious-two": "M",
        "structured-data": "M",
        "viewport": "S",
        "article-schema": "M",
        "no-qa-content": "L",
        "twitter-card": "S",
        "zz-custom": "M",
        "website-schema": "M",
    }


def test_axe_reach_aggregates_nodes_across_pages(rank_ns, monkeypatch, tmp_path):
    axe = [
        _axe_page("https://example.test/a", [_viol("dup-rule", "serious", 3),
                                             _viol("mixed-rule", "serious", 1)],
                  {"critical": 0, "serious": 4, "moderate": 0, "minor": 0}),
        _axe_page("https://example.test/b", [_viol("dup-rule", "serious", 2),
                                             _viol("mixed-rule", "moderate", 4)],
                  {"critical": 0, "serious": 2, "moderate": 4, "minor": 0}),
    ]
    run = tmp_path / "run"
    _write_reports(run, None, None, axe)
    report = _run_rank(rank_ns, monkeypatch, run, "--no-history")

    by_id = {i["id"]: i for i in report["issues"]}
    dup = by_id["dup-rule"]
    assert dup["reach"] == -5 and dup["nodes"] == 5  # 3 + 2 across pages
    assert dup["where"] == "/a /b"
    # Most severe impact seen for the rule wins.
    mixed = by_id["mixed-rule"]
    assert mixed["impact"] == "serious" and mixed["reach"] == -5
    assert report["axe_counts"] == {"critical": 0, "serious": 6, "moderate": 4, "minor": 0}
    assert report["axe_pages"] == 2


def test_effort_overrides_with_reason(rank_ns, monkeypatch, tmp_path):
    run = tmp_path / "run"
    _write_reports(run, SEO_REPORT, AI_REPORT, AXE_REPORT)
    overrides = tmp_path / "overrides.json"
    overrides.write_text(json.dumps({
        # Object form: effort plus the recorded reason (SPEC 5.3).
        "seo/twitter-card": {"effort": "L", "reason": "bundled with the owner's template refactor"},
        # Plain-letter form stays supported.
        "geo/website-schema": "S",
    }))
    report = _run_rank(rank_ns, monkeypatch, run, "--no-history", "--overrides", str(overrides))

    minors = [i for i in report["issues"] if i["impact"] == "minor"]
    # twitter-card drops from S to L, behind zz-custom (M) in the same tie group.
    assert [i["id"] for i in minors] == ["zz-custom", "twitter-card", "website-schema"]
    by_id = {i["id"]: i for i in minors}
    assert by_id["twitter-card"]["effort"] == "L"
    assert by_id["twitter-card"]["effort_reason"] == "bundled with the owner's template refactor"
    assert by_id["zz-custom"].get("effort_reason") is None
    assert by_id["website-schema"]["effort"] == "S"
    assert "effort_reason" not in by_id["website-schema"]


def test_invalid_effort_override_is_rejected(rank_ns, monkeypatch, tmp_path):
    run = tmp_path / "run"
    _write_reports(run, SEO_REPORT, None, None)
    overrides = tmp_path / "overrides.json"
    overrides.write_text(json.dumps({"seo/viewport": "X"}))
    ns = rank_ns()
    monkeypatch.setattr(sys, "argv", ["rank.py", str(run), "--no-history",
                                      "--overrides", str(overrides)])
    with pytest.raises(SystemExit, match="seo/viewport"):
        ns["main"]()


def test_history_line_shape(rank_ns, monkeypatch, tmp_path):
    run = tmp_path / "run"
    ss_home = tmp_path / "ss-home"
    _write_reports(run, SEO_REPORT, AI_REPORT, AXE_REPORT)
    _run_rank(rank_ns, monkeypatch, run, "--ss-home", str(ss_home))

    lines = (ss_home / "history.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    line = json.loads(lines[0])
    assert line["domain"] == "example.test"
    assert line["seo"] == 75 and line["geo"] == 88 and line["aeo"] == 100
    assert line["overall"] == 86
    assert line["ai_ready"] == 65
    assert line["axe"] == {"critical": 1, "serious": 7, "moderate": 0, "minor": 0}
    assert line["run"] == str(run)
    assert "ts" in line


def test_no_history_flag_skips_the_append(rank_ns, monkeypatch, tmp_path):
    run = tmp_path / "run"
    ss_home = tmp_path / "ss-home"
    _write_reports(run, SEO_REPORT, None, None)
    _run_rank(rank_ns, monkeypatch, run, "--ss-home", str(ss_home), "--no-history")
    assert not (ss_home / "history.jsonl").exists()


def test_missing_reports_become_warnings(rank_ns, monkeypatch, tmp_path):
    run = tmp_path / "run"
    _write_reports(run, SEO_REPORT, None, None)
    report = _run_rank(rank_ns, monkeypatch, run, "--no-history")
    assert report["warnings"] == ["ai.json missing or unreadable",
                                  "axe.json missing or unreadable"]
    assert [i["id"] for i in report["issues"]] == [
        "viewport", "article-schema", "no-qa-content", "twitter-card", "zz-custom",
        "website-schema"]
    assert report["schema"] == "site-signal.report/1"
    assert report["sources"] == {"seo": "seo.json"}


def test_empty_run_dir_still_writes_report(rank_ns, monkeypatch, tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    report = _run_rank(rank_ns, monkeypatch, run, "--no-history")
    assert report["warnings"] == ["seo.json missing or unreadable",
                                  "ai.json missing or unreadable",
                                  "axe.json missing or unreadable"]
    assert report["issues"] == []
    assert report["domain"] == "unknown"
