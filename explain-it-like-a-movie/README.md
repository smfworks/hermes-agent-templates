# Explain It Like a Movie

Explain It Like a Movie turns a link, PDF, or topic into a 60-second explainer that plays like a trailer: a hook, three beats, one takeaway, every fact sourced. You get the script and captions in a minute and the video shortly after.

SMF Works publishes this template under the MIT license.

## Install

From a checkout of this repository:

```bash
hermes profile install ./explain-it-like-a-movie --name movie-dev --alias
```

`movie-dev` is the development profile name. The distribution name is `explain-it-like-a-movie`. Hermes Agent 0.22.0 or newer.

## After install

Copy `templates/USER.md` and `templates/MEMORY.md` into the profile `memories/` directory. Keep non-secret preferences only. Never put a password, a code, or an API key in memory or in chat.

Movies live under the profile data directory `movies/<slug>/`. The report is a markdown file and an HTML file there. There is no hosted link.

The profile tools are file, memory, skills, clarify, todo, web, and terminal. Web fetches a URL. Terminal runs `scripts/render.py` and `pdftotext`. No browser. No delegation. No cron in v1.

The first conversation is the intro, then a script for the link, PDF, or topic they give. At most one clarifying question. After the first delivery, the profile offers a style lock once.

The shipped `config.yaml` starts a model with `grok-4.7` and `provider: xai-oauth`. After install, copy `.env.EXAMPLE` to the profile `.env` and replace the placeholder if you want the image API backend:

```bash
cp explain-it-like-a-movie/.env.EXAMPLE ~/.hermes/profiles/movie-dev/.env
chmod 0600 ~/.hermes/profiles/movie-dev/.env
# Open that file and set: XAI_API_KEY=<paste-key-here>
```

If `hermes auth status xai-oauth` is already logged in, the placeholder may stay empty and the first chat should start. The slides render works with no key. To point at a different provider instead:

```bash
hermes --profile movie-dev config set model.default <model>
hermes --profile movie-dev config set model.provider <provider>
```

Do not copy a host-local endpoint into this folder.

Render needs ffmpeg, Pillow, and espeak-ng or piper (`PIPER_MODEL` pointing at an onnx voice). Missing ffmpeg or TTS prints an install hint and leaves the script in place.

## Skills

- `movie-getting-started`
- `movie-script`
- `movie-produce`
- `movie-guardrails`

## Scripts

`--out` is the slug directory under `movies/`. These scripts do not call a model.

- `scripts/fetch_source.py` prints a JSON source record (url, fetch date, text) from HTML, text, or PDF.
- `scripts/script_build.py` drops unsourced facts and writes `script.json`.
- `scripts/report.py` overwrites `movie.md` and `movie.html` in place.
- `scripts/render.py` renders `movie.mp4`. Image API only when `XAI_API_KEY` is set; otherwise slides+TTS+ffmpeg. Never prints the key.
- `scripts/guard.py` answers a guardrail check.

## Tests

From this directory:

```bash
bash tests/smoke.sh
```

That runs the file-level contract tests. It does not call a model. If `grok` is missing, smoke prints that you should install Grok Build or use Cursor, Claude Code, or Codex, then continues. It does not switch to another build CLI.

The no-key render test needs ffmpeg, Pillow, and espeak-ng or piper (`PIPER_BIN` plus `PIPER_MODEL`).

Liam owns the live smoke and the red-team in SPEC §8. The file-level tests are not the live red-team.
