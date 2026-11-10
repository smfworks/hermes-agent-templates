#!/usr/bin/env python3
"""Tag each item with exactly one evidence tag. Walk the rubric in order."""

from __future__ import annotations

DROP = "DROP"

# Weaker first. Unsure → pick the weaker tag and say unclear.
WEAKER = (
    "Rumor",
    "Vendor-claimed",
    "Announced",
    "Independently tested",
    "Shipped",
)


def has_primary(item: dict) -> bool:
    primary = item.get("primary") or {}
    url = str(primary.get("url") or "").strip()
    return bool(url) and not item.get("no_primary")


def tag_item(item: dict, rumor_opt_in: bool = False) -> dict:
    """Return a copy with tag set, or dropped=True."""
    out = dict(item)
    if item.get("election") or item.get("campaign") or item.get("investment"):
        out["dropped"] = True
        out["drop_reason"] = "banned category"
        out.pop("tag", None)
        return out
    if not has_primary(item):
        out["dropped"] = True
        out["drop_reason"] = "no primary source"
        out.pop("tag", None)
        return out

    tag = None
    note = ""

    if item.get("is_leak") or item.get("unconfirmed") or item.get("sources_say"):
        if not rumor_opt_in:
            out["dropped"] = True
            out["drop_reason"] = "rumor excluded"
            out.pop("tag", None)
            return out
        tag = "Rumor"
        note = "Labeled rumor. Owner opted in."
    elif item.get("kind") == "legal" or item.get("legal_status"):
        status = str(item.get("legal_status") or "")
        if status in {"final", "enacted", "completed"}:
            tag = "Shipped"
            if item.get("appealable"):
                note = "This court's ruling is final; an appeal path exists."
        elif status in {"pending", "proposed", "draft", "investigation"}:
            tag = "Announced"
        else:
            tag = "Announced"
            note = "unclear"
    elif item.get("is_benchmark") or item.get("kind") == "benchmark":
        third = item.get("third_party") or {}
        if third.get("name") and (third.get("reproduced") or third.get("disagrees")):
            tag = "Independently tested"
            if third.get("disagrees"):
                note = f"{third.get('name')} disagrees with the vendor number."
            else:
                note = f"Named third party: {third.get('name')}."
        else:
            tag = "Vendor-claimed"
            note = "Vendor says"
    else:
        if item.get("kind") == "pricing" and not item.get("pricing_page_shows"):
            tag = "Announced"
            note = "Pricing page does not show it yet."
        elif item.get("usable_now") and not item.get("coming_soon"):
            tag = "Shipped"
        elif item.get("coming_soon") or item.get("waitlist") or item.get("future"):
            tag = "Announced"
        elif item.get("usable_now") is False:
            tag = "Announced"
        else:
            tag = "Announced"
            note = "unclear"

    if item.get("ambiguous") and item.get("weaker_of"):
        a, b = item["weaker_of"]
        tag = a if WEAKER.index(a) <= WEAKER.index(b) else b
        note = (note + " unclear").strip()

    # Tie-breaker: shipped model whose headline is a benchmark → tag by the claim.
    if item.get("usable_now") and item.get("is_benchmark") and tag == "Shipped":
        third = item.get("third_party") or {}
        if third.get("name") and third.get("reproduced"):
            tag = "Independently tested"
        else:
            tag = "Vendor-claimed"
            note = "Vendor says"

    out["tag"] = tag
    out["dropped"] = False
    if note:
        out["tag_note"] = note
    if tag == "Vendor-claimed" and item.get("vendor_number") is not None:
        out["vendor_says"] = True
    return out


def tag_many(items: list[dict], rumor_opt_in: bool = False) -> list[dict]:
    return [tag_item(item, rumor_opt_in=rumor_opt_in) for item in items]
