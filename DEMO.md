# Demo video script — dictate-docs (2 minutes)

Target: show a *real* voice-first workflow end to end. Total ~120s.
Record terminal + browser side by side where noted.

## 0:00–0:15 — The problem (talking head or title cards)

> "I dictate my dev notes with Wispr Flow while I code. The transcripts are a
> mess — ums, self-corrections, no punctuation. Writing the actual commit
> message and README from that is friction. So I built dictate-docs: talk messy,
> get polished docs back. Offline, no API keys."

Show a snippet of REAL raw dictated text on screen (use
`fixtures/dictated_notes.txt`).

## 0:15–0:45 — CLI: messy notes → conventional commit (terminal)

Run live:

```bash
cat fixtures/dictated_notes.txt
python -m dictate_docs commit --diff fixtures/sample_diff.patch \
    --notes-file fixtures/dictated_notes.txt
```

Point at the output as it appears:

- header `feat(dictate_docs): add exponential backoff with jitter for failed requests`
- type+scope inferred from the diff, subject cleaned + imperative, body bullets
- diffstat line

Say: *"The type came from the diff — new source file — the notes said 'added',
the filler and the 'no wait' correction are gone."*

## 0:45–1:15 — Web UI: dictate → README (browser)

1. `python -m dictate_docs serve` → open `http://127.0.0.1:8765`.
2. Point at the header badge: **"● local offline engine"** — honest, no fake AI.
3. Click **Load sample** (README tab), hit **Generate**.
4. Scroll the output: Features / Installation / Usage / How it works.
5. Click **🎤 Dictate**, say one messy sentence, hit Generate again to show
   the mic path works (or note it uses the browser Web Speech API).

## 1:15–1:45 — Under the hood (terminal, fast)

```bash
pytest -q        # 43 passed
```

While it runs, say: *"Deterministic heuristic engine — filler stripping,
self-correction resolution, run-on splitting, conventional-commit inference —
plus a pluggable LLM backend via DICTATE_DOCS_LLM if you ever want one. Stdlib
only at runtime."*

Optionally flash `dictate_docs/engine.py` in an editor for 3 seconds.

## 1:45–2:00 — Close

> "dictate-docs: built for a voice-first workflow, documented with it. Link and
> repo in the description. Thanks!"

## B-roll / screenshot checklist (submission needs a usage screenshot)

- [ ] Terminal: commit command + output (the money shot)
- [ ] Browser: web UI with generated README + `● local offline engine` badge visible
- [ ] Browser: Insights/usage-card screenshot from the Wispr Flow app
      (the actual "No Hands" proof — dictated words, not typed)
