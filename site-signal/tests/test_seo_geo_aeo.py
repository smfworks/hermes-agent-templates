"""Offline tests for seo_geo_aeo_scan.py (SPEC.md 7.1 step 8, Appendix A.3 rubric).

Pins the scoring math (each category starts at 100, each distinct failed check
counted once site-wide, critical 25 / serious 12 / moderate 6 / minor 2,
overall = 0.4*SEO + 0.3*GEO + 0.3*AEO, grades A>=90 B>=80 C>=70 D>=55 else F)
two ways: pure math on finish() with synthetic findings, and a full crawl of
the committed multi-page fixture served from a local http.server.

Also pins the Book/LearningResource article-schema credit (the Oct 31 scanner
fix): all six Article-family types satisfy `article-schema` on content pages.
"""

import json

import pytest

ARTICLE_TYPES = ["Article", "BlogPosting", "NewsArticle", "TechArticle", "Book", "LearningResource"]

SEO_WEIGHTS = {"critical": 25, "serious": 12, "moderate": 6, "minor": 2}


def _site():
    return {"titles": [], "descs": [], "types": set(), "words": 0, "qheads": 0, "lists": 0}


def _finish(seo_ns, issues):
    ns = seo_ns()
    ns["issues"] = list(issues)
    return ns["finish"]("https://fixture.example/", ["https://fixture.example/"], _site())


def _issue(category, impact, id_):
    return {"category": category, "impact": impact, "id": id_, "message": "", "fix": "", "page": "/"}


class _FakeResponse:
    def __init__(self, text):
        self.text = text


def _article_page(ld_type=None):
    if ld_type is None:
        block = ""
    else:
        ld = {"@type": ld_type,
              "author": {"@type": "Person", "name": "SMF Works",
                         "url": "https://fixture.example/about"},
              "dateModified": "2026-11-01"}
        block = '<script type="application/ld+json">' + json.dumps(ld) + "</script>"
    return (
        "<html><head><title>Learning resource fixture</title></head><body>"
        "<main><h1>Learning resource fixture</h1>" + block +
        "<p>The lead paragraph of this fixture page carries more than twenty words "
        "so the lead-summary check finds a definition-style opening here.</p>"
        "</main></body></html>"
    )


# --- pure rubric math ---


def test_category_weights_per_appendix_a3(seo_ns):
    rep = _finish(seo_ns, [_issue("SEO", "critical", "a"), _issue("GEO", "serious", "b"),
                           _issue("AEO", "moderate", "c"), _issue("SEO", "minor", "d")])
    assert rep["scores"]["SEO"] == 100 - (25 + 2)
    assert rep["scores"]["GEO"] == 100 - 12
    assert rep["scores"]["AEO"] == 100 - 6


def test_overall_is_04_03_03_rounded(seo_ns):
    rep = _finish(seo_ns, [_issue("SEO", "critical", "https"), _issue("GEO", "serious", "x")])
    # SEO 75, GEO 88, AEO 100 -> 0.4*75 + 0.3*88 + 0.3*100 = 86.4 -> 86
    assert rep["scores"]["overall"] == 86
    assert rep["grades"]["overall"] == "B"


def test_checks_are_counted_once_site_wide(seo_ns):
    # The same check failing on several pages is one deduction (id dedup).
    rep = _finish(seo_ns, [_issue("SEO", "serious", "viewport"), _issue("SEO", "serious", "viewport")])
    assert rep["scores"]["SEO"] == 88
    # A distinct check adds its own weight.
    rep = _finish(seo_ns, [_issue("SEO", "serious", "viewport"), _issue("SEO", "serious", "title-missing")])
    assert rep["scores"]["SEO"] == 76


@pytest.mark.parametrize(
    "impacts,expected_score,expected_grade",
    [
        ([], 100, "A"),
        ([("minor", 1)], 98, "A"),
        ([("moderate", 1)], 94, "A"),
        ([("moderate", 1), ("minor", 2), ("minor", 3)], 90, "A"),  # A boundary
        ([("serious", 1)], 88, "B"),
        ([("serious", 1), ("moderate", 2), ("minor", 3)], 80, "B"),  # B boundary
        ([("serious", 1), ("moderate", 2), ("minor", 3), ("minor", 4)], 78, "C"),
        ([("serious", 1), ("serious", 2)], 76, "C"),
        ([("critical", 1), ("serious", 2)], 63, "D"),
        ([("critical", 1), ("serious", 2), ("moderate", 3)], 57, "D"),
        ([("critical", 1), ("serious", 2), ("moderate", 3), ("minor", 4)], 55, "D"),  # D boundary
        ([("critical", 1), ("critical", 2)], 50, "F"),
    ],
)
def test_seo_grade_thresholds(seo_ns, impacts, expected_score, expected_grade):
    issues = [_issue("SEO", impact, f"id-{n}") for impact, n in impacts]
    rep = _finish(seo_ns, issues)
    assert rep["scores"]["SEO"] == expected_score
    assert rep["grades"]["SEO"] == expected_grade


def test_issues_sorted_by_impact_then_category(seo_ns):
    rep = _finish(seo_ns, [_issue("SEO", "serious", "s-seo"), _issue("AEO", "serious", "s-aeo"),
                           _issue("GEO", "serious", "s-geo"), _issue("GEO", "minor", "m-geo")])
    assert [(i["category"], i["id"]) for i in rep["issues"]] == [
        ("AEO", "s-aeo"), ("GEO", "s-geo"), ("SEO", "s-seo"), ("GEO", "m-geo")]


# --- Book/LearningResource article-schema credit (Appendix A.3) ---


def _issue_ids(ns):
    return [i["id"] for i in ns["issues"]]


@pytest.mark.parametrize("ld_type", ARTICLE_TYPES)
def test_every_article_family_type_earns_the_credit(seo_ns, ld_type):
    ns = seo_ns()
    ns["analyze"]("https://fixture.example/books/slug", _FakeResponse(_article_page(ld_type)), _site())
    ids = _issue_ids(ns)
    assert "article-schema" not in ids
    # The synthetic block carries author and dateModified: no follow-up deductions.
    assert "article-author" not in ids
    assert "date-modified" not in ids


def test_content_page_without_article_schema_is_serious(seo_ns):
    ns = seo_ns()
    ns["analyze"]("https://fixture.example/books/slug", _FakeResponse(_article_page(None)), _site())
    schema = [i for i in ns["issues"] if i["id"] == "article-schema"]
    assert len(schema) == 1
    assert schema[0]["impact"] == "serious"
    assert schema[0]["category"] == "GEO"


def test_article_schema_without_author_or_date_deducts(seo_ns):
    ns = seo_ns()
    page = ('<html><head><title>t</title></head><body><main><h1>x</h1>'
            '<script type="application/ld+json">{"@type": "Book"}</script>'
            "<p>lead</p></main></body></html>")
    ns["analyze"]("https://fixture.example/books/slug", _FakeResponse(page), _site())
    ids = _issue_ids(ns)
    assert "article-author" in ids and "date-modified" in ids
    assert "article-schema" not in ids


def test_article_checks_skip_non_article_paths(seo_ns):
    ns = seo_ns()
    ns["analyze"]("https://fixture.example/about", _FakeResponse(_article_page(None)), _site())
    assert "article-schema" not in _issue_ids(ns)


# --- end to end: full crawl of the committed fixture site ---


def test_full_fixture_site_crawl_and_scores(fixture_site, seo_scan):
    rep = seo_scan(fixture_site.base, 5)

    # Home + /about + /faq + the two sitemap content pages.
    assert len(rep["pages"]) == 5

    # Exactly the designed deductions, each counted once site-wide. The http
    # fixture origin always costs the https critical (the real sites are
    # HTTPS); /books/plain.html deliberately lacks article schema, a byline,
    # statistics, and outbound citations.
    distinct = {(i["category"], i["id"]) for i in rep["issues"]}
    assert distinct == {
        ("SEO", "https"),
        ("GEO", "article-schema"),
        ("GEO", "visible-byline"),
        ("GEO", "facts-stats"),
        ("GEO", "outbound-citations"),
    }
    article = [i for i in rep["issues"] if i["id"] == "article-schema"][0]
    assert article["page"] == "/books/plain.html"

    assert rep["scores"] == {"SEO": 75, "GEO": 78, "AEO": 100, "overall": 83}
    assert rep["grades"] == {"SEO": "C", "GEO": "C", "AEO": "A", "overall": "B"}

    # The learning resource earned its credit, and entity/site/FAQ schema
    # registered site-wide.
    assert {"Organization", "WebSite", "FAQPage", "BreadcrumbList",
            "LearningResource"} <= set(rep["schema_types"])
