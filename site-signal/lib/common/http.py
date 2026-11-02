"""Shared polite fetcher for Site Signal scanners (SPEC.md 3.3 rule 7, 5.2).

All scanner HTTP traffic goes through polite_get() so every run has the same
crawl etiquette:

- Identifies as the unified user agent "SMFWorks-SiteSignal/1.0 (+https://smfworks.com)"
  (the scanners' per-skill UA strings were unified to this one; PREREQ-NOTES.md).
- Honors robots.txt for that UA. robots.txt itself is always fetched. A 200 is
  parsed for our UA (falling back to the * group); 404 allows all; 401/403
  disallow everything. An unreachable/5xx robots.txt cannot contain an explicit
  rule, so the fetch proceeds — the scanners score that condition themselves
  (AI-ready `robots-txt` critical per RFC 9309).
- Max 1 request/second per host (robots.txt fetches included).
- 20 s timeout, GET only, redirects followed (same as the original scanners).
- Max 25 pages per host per process (SPEC.md 3.3 rule 7 cap); further fetches
  return None.

Import from the scanners as:
    sys.path.insert(0, str(Path(__file__).resolve().parents[4]))  # profile root
    from lib.common.http import polite_get
"""

import threading
import time
import urllib.robotparser
from urllib.parse import urlparse

import requests

USER_AGENT = "SMFWorks-SiteSignal/1.0 (+https://smfworks.com)"
TIMEOUT_S = 20
MIN_INTERVAL_S = 1.0
MAX_PAGES_PER_HOST = 25

_lock = threading.Lock()
_hosts = {}  # netloc -> {"last": monotonic, "pages": int, "robots": parser|None, "robots_checked": bool}


def _state(netloc):
    with _lock:
        if netloc not in _hosts:
            _hosts[netloc] = {"last": 0.0, "pages": 0, "robots": None, "robots_checked": False}
        return _hosts[netloc]


def _throttle(netloc):
    st = _state(netloc)
    with _lock:
        wait = MIN_INTERVAL_S - (time.monotonic() - st["last"])
        if wait > 0:
            time.sleep(wait)
        st["last"] = time.monotonic()


def _load_robots(netloc, scheme="https"):
    """Fetch and parse robots.txt once per host for our UA (RFC 9309 posture)."""
    st = _state(netloc)
    if st["robots_checked"]:
        return
    st["robots_checked"] = True
    rp = urllib.robotparser.RobotFileParser()
    try:
        _throttle(netloc)
        r = requests.get(f"{scheme}://{netloc}/robots.txt", headers={"User-Agent": USER_AGENT},
                         timeout=TIMEOUT_S, allow_redirects=True)
    except requests.RequestException:
        st["robots"] = None  # no explicit rule obtainable; scanners score robots reachability
        return
    if r.status_code == 200 and "user-agent" in r.text.lower():
        rp.parse(r.text.splitlines())
        st["robots"] = rp
    elif 400 <= r.status_code < 500 and r.status_code != 404:
        # 401/403: site refuses crawlers without rules — treat as full disallow.
        rp.parse(["User-agent: *", "Disallow: /"])
        st["robots"] = rp
    else:
        # 404 or 5xx or non-robots body: no explicit rule; scanners score the condition.
        st["robots"] = None


def robots_allowed(url):
    """True when robots.txt permits our UA to fetch url (None robots = allowed)."""
    u = urlparse(url)
    _load_robots(u.netloc, u.scheme or "https")
    rp = _state(u.netloc)["robots"]
    return True if rp is None else rp.can_fetch(USER_AGENT, url)


def polite_get(url, robots_exempt=False):
    """Polite GET: robots-respected, rate-limited, 20 s timeout. Returns a
    requests.Response, or None when robots disallows our UA, the per-host page
    cap is exhausted, or the request fails (same None contract as the original
    scanners' get() helpers)."""
    if not url.startswith("http"):
        url = "https://" + url
    parsed = urlparse(url)
    netloc = parsed.netloc
    if not robots_exempt:
        _load_robots(netloc, parsed.scheme or "https")
        if not robots_allowed(url):
            return None
        st = _state(netloc)
        with _lock:
            if st["pages"] >= MAX_PAGES_PER_HOST:
                return None
            st["pages"] += 1
    _throttle(netloc)
    try:
        return requests.get(url, headers={"User-Agent": USER_AGENT},
                            timeout=TIMEOUT_S, allow_redirects=True)
    except requests.RequestException:
        return None
