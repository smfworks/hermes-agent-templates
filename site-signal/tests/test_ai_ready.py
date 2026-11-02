"""Offline tests for ai_ready_scan.py (SPEC.md 7.1 step 8, Appendix A.2 rubric).

The deduction math and grade thresholds (A>=90, B>=75, C>=60, D>=40, else F;
critical 25 / serious 10 / moderate 5 / minor 2) are pinned two ways:

- pure math: finish() called with synthetic findings — no network, exact
  boundary scores for every grade;
- end to end: scans of fixture pages served from a local python -m http.server
  (started on a free port, torn down after), each page designed so the
  expected issue set is exact. The fixture pages document their intent
  inline; a healthy page failing here is a scanner regression.

The scanner is executed in a fresh namespace per scan (its findings
accumulate in module-level lists); the polite fetcher runs without the 1 req/s
delay against localhost (see conftest).
"""

import json
import subprocess
import sys

import pytest


# --- pure rubric math: score = 100 - sum(weights), grades on the A.2 ladder ---


def _finish(ai_ns, issues):
    ns = ai_ns()
    ns["issues"] = [dict(impact=impact, id=id_, message="", fix="") for impact, id_ in issues]
    return ns["finish"]("https://fixture.example/")


@pytest.mark.parametrize(
    "issues,expected_score,expected_grade",
    [
        ([], 100, "A"),
        ([("minor", "a")], 98, "A"),
        ([("moderate", "a")], 95, "A"),
        ([("serious", "a")], 90, "A"),  # A boundary: lowest score that stays A
        ([("serious", "a"), ("minor", "b")], 88, "B"),
        ([("critical", "a")], 75, "B"),  # B boundary
        ([("critical", "a"), ("minor", "b")], 73, "C"),
        ([("critical", "a"), ("moderate", "b")], 70, "C"),
        ([("critical", "a"), ("serious", "b")], 65, "C"),
        ([("critical", "a"), ("serious", "b"), ("moderate", "c")], 60, "C"),  # C boundary
        ([("critical", "a"), ("serious", "b"), ("moderate", "c"), ("minor", "d")], 58, "D"),
        ([("critical", "a"), ("critical", "b")], 50, "D"),
        ([("critical", "a"), ("critical", "b"), ("serious", "c")], 40, "D"),  # D boundary
        ([("critical", "a"), ("critical", "b"), ("serious", "c"), ("minor", "d")], 38, "F"),
        ([("critical", "a"), ("critical", "b"), ("critical", "c")], 25, "F"),
        ([("critical", str(i)) for i in range(6)], 0, "F"),  # clamped at 0, never negative
    ],
    ids=lambda v: v if isinstance(v, str) else None,
)
def test_score_and_grade_ladder(ai_ns, issues, expected_score, expected_grade):
    rep = _finish(ai_ns, issues)
    assert rep["score"] == expected_score
    assert rep["grade"] == expected_grade


def test_weights_per_appendix_a2(ai_ns):
    # critical 25 / serious 10 / moderate 5 / minor 2, every instance counted.
    rep = _finish(ai_ns, [("critical", "a"), ("serious", "b"), ("moderate", "c"), ("minor", "d")])
    assert rep["score"] == 100 - (25 + 10 + 5 + 2) == 58


def test_ai_findings_are_not_deduplicated(ai_ns):
    # Unlike the SEO scanner (one deduction per check id site-wide), the AI
    # scanner counts every finding instance.
    rep = _finish(ai_ns, [("serious", "same-id"), ("serious", "same-id")])
    assert rep["score"] == 80


def test_findings_sorted_by_impact(ai_ns):
    rep = _finish(ai_ns, [("minor", "z"), ("critical", "a"), ("moderate", "m")])
    assert [(i["impact"], i["id"]) for i in rep["issues"]] == [
        ("critical", "a"), ("moderate", "m"), ("minor", "z")]


# --- end to end against the local fixture server ---


def test_healthy_page_is_flawless(fixture_site, ai_scan):
    rep = ai_scan(fixture_site.url("/"))
    assert rep["score"] == 100
    assert rep["grade"] == "A"
    assert rep["issues"] == []
    passed = {p["id"] for p in rep["passes"]}
    # (The A.2b scanner records ok() entries for these checks only; checks
    # like meta-description or single-h1 are proven by the empty issues list.)
    assert {"page-fetch", "robots-txt", "robots-search-bots", "robots-training-policy",
            "sitemap", "llms-txt", "ssr-content", "title", "structured-data"} <= passed


def test_missing_jsonld_is_the_only_deduction_and_pins_A_boundary(fixture_site, ai_scan):
    rep = ai_scan(fixture_site.url("/no-schema.html"))
    assert rep["score"] == 90  # 100 - 10 serious: lowest A
    assert rep["grade"] == "A"
    assert [(i["impact"], i["id"]) for i in rep["issues"]] == [("serious", "structured-data")]
    # No cascade: the entity check only runs when a block parses at all.
    assert "jsonld-entity" not in [i["id"] for i in rep["issues"]]


def test_thin_page_pins_B_boundary(fixture_site, ai_scan):
    rep = ai_scan(fixture_site.url("/thin.html"))
    assert rep["score"] == 75  # 100 - 25 critical: lowest B
    assert rep["grade"] == "B"
    assert [(i["impact"], i["id"]) for i in rep["issues"]] == [("critical", "ssr-content")]


def test_missing_robots_txt_is_one_moderate(serve_site, ai_scan, site_support,
                                            sitemap_template, fixtures_dir):
    # good.html plus sitemap/llms support but deliberately no robots.txt.
    support = {k: v for k, v in site_support.items() if k != "robots.txt"}
    site = serve_site(files={"good.html": (fixtures_dir / "good.html").read_text(),
                             **support},
                      render={"sitemap.xml": sitemap_template})
    rep = ai_scan(site.url("/good.html"))
    assert rep["score"] == 95
    assert rep["grade"] == "A"
    assert [(i["impact"], i["id"]) for i in rep["issues"]] == [("moderate", "robots-txt")]
    # Support files must not add deductions of their own.
    assert "sitemap" not in [i["id"] for i in rep["issues"]]
    assert "llms-txt" not in [i["id"] for i in rep["issues"]]


def test_blocking_robots_scores_per_appendix(serve_site, ai_scan, fixtures_dir):
    """F4 (Paula review): a Disallow:/ site is still fetched and scored per A.2b.

    The spec's get() has no robots gate: the page is scanned, the parsed
    Disallow drives the `robots-search-bots` critical, and every other check
    runs on the real page. The polite fetcher still honors robots for all
    OTHER fetches; the page and robots.txt fetches are exempt call sites.
    """
    site = serve_site(files={"good.html": (fixtures_dir / "good.html").read_text(),
                             "robots.txt": (fixtures_dir / "robots-block.txt").read_text()})
    rep = ai_scan(site.url("/good.html"))
    # 100 - 25 (robots-search-bots) - 10 (sitemap) - 5 (llms-txt) - 2 (robots-ai-policy)
    assert rep["score"] == 58
    assert rep["grade"] == "D"
    ids = [(i["impact"], i["id"]) for i in rep["issues"]]
    assert ("critical", "robots-search-bots") in ids
    # The page itself was scanned, so content checks ran:
    assert "page-fetch" not in [i["id"] for i in rep["issues"]]
    assert ("serious", "sitemap") in ids
    assert ("moderate", "llms-txt") in ids
    assert ("minor", "robots-ai-policy") in ids


def test_cli_writes_the_json_report(serve_site, site_support, sitemap_template,
                                    scanner_scripts, tmp_path):
    """End-to-end through the shipped CLI: summary on stdout, --json on disk.

    This one runs the scanner as a real subprocess, so the polite fetcher's
    1 req/s applies inside it; the scan makes ~6 requests to localhost.
    """
    base = serve_site(files={"good.html": (scanner_scripts["repo_root"] / "tests/fixtures/good.html").read_text(),
                             **site_support},
                      render={"sitemap.xml": sitemap_template})
    out = tmp_path / "ai.json"
    proc = subprocess.run(
        [sys.executable, str(scanner_scripts["ai"]), base.url("/good.html"), "--json", str(out)],
        capture_output=True, text=True, timeout=180)
    assert proc.returncode == 0, proc.stderr
    assert "AI-readiness:" in proc.stdout and "100/100 (A)" in proc.stdout
    rep = json.loads(out.read_text())
    assert rep["score"] == 100
    assert rep["grade"] == "A"
    assert rep["issues"] == []
