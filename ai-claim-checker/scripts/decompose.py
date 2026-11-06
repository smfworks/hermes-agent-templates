#!/usr/bin/env python3
"""Cap atomic claims at eight. Opinions stay in Not checkable."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

MAX_CLAIMS = 8


def rank_key(claim: dict) -> tuple:
    headline = 0 if claim.get("headline") else 1
    specific = 0 if (claim.get("settings") or claim.get("value")) else 1
    return (headline, specific, str(claim.get("id") or ""))


def decompose(payload: dict) -> dict:
    claims = [item for item in payload.get("claims") or [] if isinstance(item, dict)]
    not_checkable = list(payload.get("not_checkable") or [])
    ordered = sorted(claims, key=rank_key)
    selected = ordered[:MAX_CLAIMS]
    omitted = ordered[MAX_CLAIMS:]
    return {
        "claims": selected,
        "not_checkable": not_checkable,
        "omitted_count": len(omitted),
        "omitted_ids": [str(item.get("id") or "") for item in omitted],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cap claims at eight")
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = decompose(payload)
    Path(args.out).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"selected": len(result["claims"]), "omitted": result["omitted_count"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
