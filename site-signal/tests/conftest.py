"""Shared offline test plumbing for the Site Signal scanner suites.

Everything here runs against a local `python -m http.server` fixture server
started on a free port and torn down after the test (SPEC.md 7.1 step 8:
pytest must be offline). Two kinds of fixture sites are served:

- tests/fixtures/site/  — the committed multi-page crawling fixture. Served
  from a temp copy; its sitemap.xml is rendered from sitemap.xml.in at server
  start with the live origin, because the sitemap URLs must carry the
  ephemeral port. robots.txt deliberately has no Sitemap line, so scanners
  fall back to /sitemap.xml on the current origin.
- composed single-page sites built from the flat fixtures (good.html,
  robots-block.txt) plus the site support files, used to isolate single
  AI-readiness deductions.

The scanners are executed in a fresh namespace per call (runpy) because both
scripts accumulate findings in module-level lists; a fresh namespace is the
same isolation a fresh subprocess would get, without the interpreter startup.

The polite fetcher's 1 req/s per-host delay is dropped for offline tests (it
exists to be polite to real sites, not to our own fixture server), and the
per-host state (page cap, robots cache) is cleared between scans so the 25
page cap cannot leak across ephemeral servers that reuse a port.
"""

import http.client
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
SITE_SRC = FIXTURES / "site"
AI_SCAN = REPO_ROOT / "skills/site-signal/site-signal-ai-readiness/scripts/ai_ready_scan.py"
SEO_SCAN = REPO_ROOT / "skills/site-signal/site-signal-seo-geo-aeo/scripts/seo_geo_aeo_scan.py"
AXE_SCAN = REPO_ROOT / "skills/site-signal/site-signal-axe-scan/scripts/axe_scan.js"
RANK = REPO_ROOT / "skills/site-signal/site-signal-report/scripts/rank.py"

sys.path.insert(0, str(REPO_ROOT))  # so tests can import lib.common.http

SITEMAP_TEMPLATE = (SITE_SRC / "sitemap.xml.in").read_text()
SUPPORT_FILES = ("robots.txt", "llms.txt", "llms-full.txt")


def support_files():
    """Support files every composed fixture site needs (copied from site/)."""
    return {name: (SITE_SRC / name).read_text() for name in SUPPORT_FILES}


def sitemap_render():
    """The site sitemap template, rendered against the live origin."""
    return {"sitemap.xml": SITEMAP_TEMPLATE}


def reset_http_state():
    """Clear per-host polite-fetcher state (page caps, robots caches)."""
    import lib.common.http as http_mod

    http_mod._hosts.clear()


def load_script(path):
    """Execute a scanner script in a fresh namespace that IS the module
    globals. (runpy.run_path returns a copy of the globals, which would leave
    the module's functions detached from any state a test assigns.)"""
    code = compile(path.read_text(), str(path), "exec")
    ns = {"__file__": str(path), "__name__": "site_signal_scan"}
    exec(code, ns)
    return ns


def run_ai_scan(url):
    """Run ai_ready_scan.py main() in a fresh namespace; returns its report."""
    reset_http_state()
    return load_script(AI_SCAN)["main"](url)


def run_seo_scan(url, pages=5):
    """Run seo_geo_aeo_scan.py main() in a fresh namespace; returns its report."""
    reset_http_state()
    return load_script(SEO_SCAN)["main"](url, pages)


@pytest.fixture(autouse=True)
def _offline_polite_fetcher(monkeypatch):
    """Drop the 1 req/s delay for offline tests and reset per-host state."""
    import lib.common.http as http_mod

    monkeypatch.setattr(http_mod, "MIN_INTERVAL_S", 0.0)
    http_mod._hosts.clear()
    yield
    http_mod._hosts.clear()


@pytest.fixture
def ai_scan():
    return run_ai_scan


@pytest.fixture
def seo_scan():
    return run_seo_scan


@pytest.fixture
def scanner_scripts():
    return {"ai": AI_SCAN, "seo": SEO_SCAN, "axe": AXE_SCAN, "rank": RANK,
            "repo_root": REPO_ROOT}


@pytest.fixture
def ai_ns():
    """Fresh ai_ready_scan.py namespace (module globals accumulate per scan)."""
    def _load():
        return load_script(AI_SCAN)
    return _load


@pytest.fixture
def seo_ns():
    """Fresh seo_geo_aeo_scan.py namespace."""
    def _load():
        return load_script(SEO_SCAN)
    return _load


@pytest.fixture
def rank_ns():
    """Fresh rank.py namespace (stateless; main() is only run under __main__)."""
    def _load():
        return load_script(RANK)
    return _load


@pytest.fixture
def site_support():
    return support_files()


@pytest.fixture
def sitemap_template():
    return SITEMAP_TEMPLATE


@pytest.fixture
def fixtures_dir():
    return FIXTURES


class FixtureServer:
    def __init__(self, base, root, proc):
        self.base = base
        self.root = root
        self.proc = proc

    def url(self, path="/"):
        return self.base + path


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_ready(port, timeout=10.0):
    """True once the server answers any status (404 counts as up)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
            conn.request("GET", "/")
            conn.getresponse().read()
            conn.close()
            return True
        except OSError:
            time.sleep(0.05)
    return False


@pytest.fixture
def serve_site(tmp_path):
    """Factory fixture: start a python -m http.server on a free port.

    serve_site(files={name: content}, copy_dir=Path|None, render={name: template})
    -> FixtureServer with .base and .url(path). All servers are torn down at
    test end. Rendered files are written after startup with {BASE_URL} replaced.
    """
    procs = []

    def start(files=None, copy_dir=None, render=None):
        root = tmp_path / f"site{len(procs)}"
        if copy_dir is not None:
            shutil.copytree(copy_dir, root)
        else:
            root.mkdir()
        for name, content in (files or {}).items():
            (root / name).write_text(content)
        port = _free_port()
        proc = subprocess.Popen(
            [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1",
             "--directory", str(root)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not _wait_ready(port):
            proc.terminate()
            proc.wait(timeout=5)
            raise RuntimeError(f"fixture http.server did not come up on port {port}")
        procs.append(proc)
        base = f"http://127.0.0.1:{port}"
        for name, template in (render or {}).items():
            (root / name).write_text(template.replace("{BASE_URL}", base))
        return FixtureServer(base, root, proc)

    yield start

    for proc in procs:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture
def fixture_site(serve_site):
    """The committed multi-page crawling fixture (tests/fixtures/site/)."""
    return serve_site(copy_dir=SITE_SRC, render=sitemap_render())
