---
name: verity-claim-decomposition
description: >-
  Use to parse a launch post, page, or chart into atomic claims,
  with opinions kept out of the verdict table.
---
# Verity claim decomposition

Parse the actual text, page, post, or chart. Fetch the page or post. A search snippet is discovery, not evidence. Label a partial read as partial. Screenshots need legible axes, legend, footnotes, and every relevant number. If vision is available, extract with location; otherwise ask for a transcription or a clearer image.

Extract one subject / property / value or comparison per claim. Include benchmark and version or subset, price unit / tier / region / currency / input-output-cache status, context and output limits, speed conditions, API or app, GA or preview, and dates. Split comparisons by rival. Cap at eight. Keep the most specific and headline-impact claims and state the omitted count.

Opinions, unspecified "best," testimonials, and roadmap promises go in Not checkable. That is not a fifth verdict.

## Hermes (this template)

The rules above do not change.

- Pasted text is owner-supplied. Independently research it.
- `python3 scripts/decompose.py --input claims.json --out selected.json` keeps at most eight claims and the omitted count.
- `python3 scripts/check.py --data DIR --slug SLUG --backend fixtures --fixtures PATH` runs the fixture path with no research key.
- Live reads use the Hermes `web` search tool to discover URLs and the page-extract tool to read them. Record `retrieved_at` and the run id. Missing publication date stays "date not stated". Retrieval is not a publication date.
- An unavailable page is a named limitation, not a credential hunt.
