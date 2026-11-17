"""Shared polite fetcher for Site Signal scanners (SPEC.md 3.3 rule 7, 5.2).

All scanner HTTP traffic goes through polite_get() so every run has the same
crawl etiquette:

- Identifies as the unified user agent "SMFWorks-SiteSignal/1.0 (+https://smfworks.com)".
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

import ipaddress
import threading
import time
import urllib.robotparser
from urllib.parse import urlparse

import requests

USER_AGENT = "SMFWorks-SiteSignal/1.0 (+https://smfworks.com)"
TIMEOUT_S = 20
MIN_INTERVAL_S = 1.0
MAX_PAGES_PER_HOST = 25
MAX_REDIRECTS = 3

# hsf_9334fec2d31ecd0391257355: sitemap/robots-derived URLs previously joined the
# fetch list with no origin restriction — a crafted sitemap.xml could pivot the
# scanner at internal targets. Default-deny scheme + host policy:
# - only http/https, public unicast hosts (no loopback/private/link-local/etc.);
# - redirects capped (requests allow_redirects=False + manual hop budget).
_denied_networks = [
    ipaddress.ip_network(n)
    for n in ("127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
              "169.254.0.0/16", "0.0.0.0/8", "100.64.0.0/10", "192.0.0.0/24",
              "192.0.2.0/24", "198.18.0.0/15", "198.51.100.0/24", "203.0.113.0/24",
              "224.0.0.0/4", "240.0.0.0/4", "::1/128", "fc00::/7", "fe80::/10",
              "ff00::/8")
]


def _host_allowed(netloc: str) -> bool:
    """Default-deny host policy: hostname must resolve to a public unicast address.
    Unresolvable hosts are refused (no DNS surprise). Called per fetch, not cached
    per-process, so DNS re-resolution still works within one run."""
    host = netloc.rsplit("@", 1)[-1].split(":", 1)[0].strip("[]").lower()
    if not host or host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
        return False
    try:
        infos = __import__("socket").getaddrinfo(host, None)
    except OSError:
        return False
    for info in infos:
        addr = ipaddress.ip_address(info[4][0])
        for net in _denied_networks:
            if addr in net:
                return False
    return True

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


def _url_allowed(url: str) -> bool:
    """hsf_9334fec2: origin policy for fetched URLs — http/https only, and the
    host must pass the default-deny network check (SSRF pivot defense for
    sitemap/robots-derived URLs)."""
    u = urlparse(url)
    if u.scheme not in ("http", "https"):
        return False
    return _host_allowed(u.netloc)


def polite_get(url, robots_exempt=False):
    """Polite GET: origin-checked, robots-respected, rate-limited, 20 s timeout,
    redirects capped at MAX_REDIRECTS. Returns a requests.Response, or None when
    the origin policy refuses the URL, robots disallows our UA, the per-host
    page cap is exhausted, a redirect hop is untrusted, or the request fails
    (same None contract as the original scanners' get() helpers)."""
    if not url.startswith("http"):
        url = "https://" + url
    parsed = urlparse(url)
    netloc = parsed.netloc
    # Origin policy first (hsf_9334fec2): refuse non-http(s) schemes and any
    # host that does not resolve public — before robots, throttle, or DNS-ttl'd
    # state is touched.
    if not _url_allowed(url):
        return None
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
    # Redirect handling: follow manually so every hop re-passes the origin
    # policy (a 302 to an internal host must not be silently followed).
    current, hops = url, 0
    while True:
        try:
            resp = requests.get(current, headers={"User-Agent": USER_AGENT},
                                timeout=TIMEOUT_S, allow_redirects=False)
        except requests.RequestException:
            return None
        if resp.is_redirect or resp.is_permanent_redirect:
            hops += 1
            if hops > MAX_REDIRECTS:
                return None
            loc = resp.headers.get("Location", "")
            if not loc:
                return None
            nxt = requests.compat.urljoin(current, loc)
            if not _url_allowed(nxt):
                return None
            current = nxt
            continue
        return resp
