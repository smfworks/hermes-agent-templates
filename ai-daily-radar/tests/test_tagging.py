#!/usr/bin/env python3
"""A3 — tagging rubric branches and tie-breakers."""

from __future__ import annotations

from helpers import candidate
from tagging import tag_item


def test_tagging() -> None:
    dropped = tag_item(candidate("n1", no_primary=True, primary={"url": "", "title": ""}))
    assert dropped["dropped"] and dropped.get("drop_reason") == "no primary source"

    leak = tag_item(candidate("n2", is_leak=True))
    assert leak["dropped"]
    rumor = tag_item(candidate("n2", is_leak=True), rumor_opt_in=True)
    assert rumor["tag"] == "Rumor" and not rumor["dropped"]

    ruling = tag_item(
        candidate("n3", kind="legal", legal_status="final", appealable=True, headline="Court rules on training data")
    )
    assert ruling["tag"] == "Shipped"
    assert "appeal" in (ruling.get("tag_note") or "").casefold()

    proposed = tag_item(candidate("n4", kind="legal", legal_status="proposed"))
    assert proposed["tag"] == "Announced"

    vendor = tag_item(
        candidate(
            "n5",
            is_benchmark=True,
            vendor_number="90.2",
            headline="Model X hits 90",
        )
    )
    assert vendor["tag"] == "Vendor-claimed"
    assert vendor.get("vendor_says") is True

    independent = tag_item(
        candidate(
            "n6",
            is_benchmark=True,
            vendor_number="90.2",
            third_party={"name": "EvalCorp", "reproduced": True},
        )
    )
    assert independent["tag"] == "Independently tested"
    assert "EvalCorp" in (independent.get("tag_note") or "")

    disagree = tag_item(
        candidate(
            "n7",
            is_benchmark=True,
            third_party={"name": "EvalCorp", "disagrees": True},
        )
    )
    assert disagree["tag"] == "Independently tested"
    assert "disagree" in (disagree.get("tag_note") or "").casefold()

    price = tag_item(candidate("n8", kind="pricing", pricing_page_shows=False, usable_now=False))
    assert price["tag"] != "Shipped"

    coming = tag_item(candidate("n9", usable_now=False, coming_soon=True))
    assert coming["tag"] == "Announced"

    shipped = tag_item(candidate("n10", usable_now=True))
    assert shipped["tag"] == "Shipped"

    unclear = tag_item(
        candidate("n11", ambiguous=True, weaker_of=["Shipped", "Announced"], usable_now=True)
    )
    assert unclear["tag"] == "Announced"
    assert "unclear" in (unclear.get("tag_note") or "")

    election = tag_item(candidate("n12", election=True))
    assert election["dropped"]
    print("A3 PASS")


if __name__ == "__main__":
    test_tagging()
