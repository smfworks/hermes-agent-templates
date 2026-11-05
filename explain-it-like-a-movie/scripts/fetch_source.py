#!/usr/bin/env python3
"""Read a URL save, HTML file, or PDF. Record url + fetch date. GET only."""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<script\b[^>]*>.*?</script>", " ", raw)
    raw = re.sub(r"(?is)<style\b[^>]*>.*?</style>", " ", raw)
    raw = re.sub(r"(?is)<br\s*/?>", "\n", raw)
    raw = re.sub(r"(?is)</p>", "\n", raw)
    raw = re.sub(r"(?is)</h[1-6]>", "\n", raw)
    raw = re.sub(r"(?is)<[^>]+>", " ", raw)
    raw = html_lib.unescape(raw)
    lines = [re.sub(r"\s+", " ", line).strip() for line in raw.splitlines()]
    return "\n".join(line for line in lines if line)


def write_simple_pdf(path: Path, text: str) -> None:
    """Tiny one-page PDF for fixtures. Helvetica, Latin-1."""
    safe = (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
        .encode("latin-1", "replace")
        .decode("latin-1")
    )
    stream = f"BT /F1 12 Tf 50 720 Td ({safe}) Tj ET\n".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{index} 0 obj\n".encode("ascii"))
        out.extend(body)
        out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode(
            "ascii"
        )
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(out))


def pdftotext_bin() -> str:
    from shutil import which

    found = which("pdftotext")
    if not found:
        raise SystemExit(
            "pdftotext is missing. Install poppler (poppler-utils or poppler). "
            "The script can still be written from other sources."
        )
    return found


def pdf_to_text(path: Path) -> str:
    result = subprocess.run(
        [pdftotext_bin(), "-layout", str(path), "-"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or "pdftotext failed")
    return result.stdout.strip()


def fetch_http(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise SystemExit(f"unsupported url scheme: {parsed.scheme}")
    req = Request(url, method="GET", headers={"User-Agent": "SMFWorks-Movie/1.0"})
    with urlopen(req, timeout=20) as resp:  # noqa: S310 — scheme checked above
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def load_text(args: argparse.Namespace) -> tuple[str, str]:
    if args.file:
        path = Path(args.file)
        raw = path.read_text(encoding="utf-8", errors="replace")
        if path.suffix.casefold() in {".html", ".htm"}:
            return html_to_text(raw), args.url or path.resolve().as_uri()
        return raw.strip(), args.url or path.resolve().as_uri()
    if args.pdf:
        path = Path(args.pdf)
        return pdf_to_text(path), args.url or path.resolve().as_uri()
    if args.url:
        raw = fetch_http(args.url)
        return html_to_text(raw), args.url
    raise SystemExit("pass --file, --pdf, or --url")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch a source and print a JSON record.")
    parser.add_argument("--file", help="Local HTML or text saved this run.")
    parser.add_argument("--pdf", help="Local PDF.")
    parser.add_argument("--url", help="Canonical URL recorded on the source.")
    parser.add_argument("--title", default="")
    parser.add_argument("--n", type=int, default=1)
    parser.add_argument("--now", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    text, url = load_text(args)
    if args.now:
        fetched = args.now
    else:
        fetched = datetime.now(timezone.utc).date().isoformat()
    record = {
        "n": args.n,
        "url": url,
        "title": args.title or url,
        "fetched": fetched,
        "text": text,
    }
    sys.stdout.write(json.dumps(record, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
