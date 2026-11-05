---
name: movie-produce
description: >-
  Use after movie-script to render movie.mp4, update the report with the
  video path or a failure plus next step, and write poster.png.
---
# Explain It Like a Movie produce

Load `movie-guardrails` first.

Render with `scripts/render.py --script movies/<slug>/script.json --out movies/<slug>/`.

Backends, chosen by config or env, then auto-fallback:

- Imagine / image API: only when `XAI_API_KEY` is set. Mention provider usage cost when this backend is used. Never print the key.
- No-key fallback (must work on a fresh install): 1080x1920 slides (Pillow), TTS (piper or espeak-ng), ffmpeg concat, burned-in captions from the script lines, about 60 seconds, "Made with AI" end card.

Output: `movies/<slug>/movie.mp4`, `captions.srt`, `poster.png` (title frame).

QA: duration 45–75 s, 1080x1920, audio present, end card present.

If ffmpeg or TTS is missing, leave the script in place. Update the report with the failure and the next step (install ffmpeg and espeak-ng or piper). Do not pretend a video exists.

Then edit the same report in place: replace status with the video path, or the failure plus next step.

Avatar or likeness backends are deferred. Consent required.

## Hermes (this template)

Tool names only. The rules above do not change.

- Terminal runs `scripts/render.py`. No browser. No delegation.
- `report.py --status video --video <path>` or `--status failure --error ... --next ...`.
- Delivery is a local path, or a Telegram file send of that mp4. This profile does not post to X or TikTok.
- When the image API backend is selected, mention that it bills the provider. The slides path does not.
