# 🎙️ dictate-docs

**Talk through your work. Get polished docs back.** A voice-first dev tool for the
Wispr "No Hands" Challenge (WeMakeDevs × Wispr Flow, Builders track).

Developers think out loud — in standups, in voice notes, while dictating with tools
like Wispr Flow. That raw speech is full of *"um"*, *"no wait…"*, run-ons and
half-finished thoughts. `dictate-docs` takes that messy dictated text and turns it into:

1. **Conventional commit messages** — `type(scope): subject` + body, with the type
   and scope inferred from your actual `git diff`.
2. **README sections** — Features, Installation, Usage, How it works, generated from
   a dictated walkthrough (or merged into your existing README).
3. **Clean prose** — a general polisher that strips filler, resolves self-corrections
   and fixes structure.

No API keys. No network. The default engine is a deterministic, offline
heuristic processor — and the UI tells you so honestly. An OpenAI-compatible LLM
backend is available as an opt-in plugin.

> **Built dogfood-style:** this README was drafted from dictated notes and polished
> with `dictate-docs` itself.

---

## The problem

Writing good commit messages and READMEs is high-friction, low-dopamine work, so it
doesn't happen — and future-you (and your teammates) pay for it. But *explaining*
what you did out loud is natural. Voice dictation apps made capturing that
explanation effortless; nothing made it *usable*. `dictate-docs` closes that gap.

## How it works

```
 ┌─────────────────────┐      ┌──────────────────────────┐      ┌────────────────────┐
 │  Dictated notes      │      │  Offline heuristic engine │      │  Polished output   │
 │  (Wispr Flow, mic,   │─────▶│  • filler stripping       │─────▶│  • commit message  │
 │   or typed messy)    │      │  • self-correction resolve │      │  • README sections │
 └─────────────────────┘      │  • run-on splitting        │      └────────────────────┘
                              │  • conventional-commit     │
                              │    type/scope inference    │
                              └──────────────────────────┘
```

The engine handles real-world dictated mess:

| Dictated | Polished |
|---|---|
| `um so basically I added tests you know` | `I added tests.` |
| `fixed the parser, I mean the tokenizer` | `Fixed the tokenizer.` |
| `the bug was in the cache, actually in the queue` | `In the queue.` |
| `the timeout is thirty seconds` | `The timeout is 30 seconds.` |
| `run python minus m dictate docs` | `Run python -m dictate docs.` |
| one 80-word unpunctuated blob | 4 clean sentences |

For commits, the diff is parsed (`git diff --cached` or a patch file) and the
conventional-commit **type** is scored from both your notes (weighted 2× — you know
what you did) and the diff itself (new source files → `feat`, test-only →
`test`, docs-only → `docs`, dep manifests → `chore`, tiny change → `fix`, …).
The **scope** comes from the most-changed directory or file.

## Voice-first workflow

This tool is designed for a no-hands loop:

1. **Dictate** — while you code, narrate into Wispr Flow (or any dictation app):
   *"um so I added retry logic, no wait, exponential backoff with jitter, and I
   fixed the timeout bug…"*
2. **Paste** — drop the raw transcript into the web UI (or pipe it to the CLI).
   The browser-mic button in the UI can also dictate straight into the page via
   the Web Speech API.
3. **Generate** — get a commit message or README section, copy it, done.

Honest note: `dictate-docs` consumes **text** — the transcript your voice app
produces. No audio is recorded, uploaded or processed by this tool, ever.

## Installation

Python 3.10+ — no runtime dependencies, standard library only.

```bash
git clone <this-repo>
cd dictate-docs
# use directly:
python -m dictate_docs --help
# or install it:
pip install -e .
# run the tests:
pip install -r requirements.txt && pytest
```

## Usage

### 1. Commit messages

```bash
# from staged changes + dictated notes
python -m dictate_docs commit --notes-file notes.txt
# from a patch file
python -m dictate_docs commit --diff changes.patch --notes "um I fixed the crash"
# pipe notes in
echo "added retries, no wait, backoff with jitter" | python -m dictate_docs commit --diff changes.patch
# actually create the git commit
python -m dictate_docs commit --notes-file notes.txt --commit
```

Real example (from `fixtures/`):

```
$ python -m dictate_docs commit --diff fixtures/sample_diff.patch \
      --notes-file fixtures/dictated_notes.txt

feat(dictate_docs): add exponential backoff with jitter for failed requests

- Fix the timeout bug where it would hang forever, on slow networks.
- Add tests for the retry path.
- Make the timeout configurable instead of hardcoded at 30 seconds.
- The main thing is the retry helper is now reusable across the codebase.

3 file(s) changed, +49 -1
```

The dictated notes that produced it:

> *um so basically I added retry logic to the api client, no wait, exponential
> backoff with jitter for failed requests, and uh I also fixed the timeout bug
> where it would hang forever, like literally forever, on slow networks you know.
> oh and I added tests for the retry path, and also I made the timeout
> configurable instead of hardcoded at thirty seconds…*

### 2. README sections

```bash
# brand-new README from a dictated walkthrough
python -m dictate_docs readme --notes-file walkthrough.txt
# merge into your existing README (sections replaced, everything else kept)
python -m dictate_docs readme --notes-file walkthrough.txt --readme README.md --in-place
# write elsewhere
python -m dictate_docs readme --notes-file walkthrough.txt -o NEW_README.md
```

Real example (from `fixtures/walkthrough.txt`):

```markdown
# Dictate Docs

The project is called dictate docs, it's a voice first dev tool that turns
dictated notes into polished commit messages and README sections.

## Features

- You dictate messy notes with fillers and self corrections using any voice app.
- You get a conventional commit message or README sections out.

## Installation

1. To install you just clone the repo and you need python 3.12 or newer, no
   other dependencies.

## Usage

- The offline engine strips the fillers and resolves the corrections and splits
  run on sentences.
- Run python -m dictate docs commit with your notes, or you start the web UI
  with dictate docs serve and dictate right in the browser.

## How it works

The engine is fully offline and heuristic based, no API keys needed, but you can
plug in an OpenAI compatible LLM if you want.
```

### 3. Polish any dictated text

```bash
python -m dictate_docs polish --text "um so the deploy failed, no wait, the build failed"
# → The build failed.
echo "..." | python -m dictate_docs polish
```

### 4. Web UI

```bash
python -m dictate_docs serve --port 8765
# → http://127.0.0.1:8765
```

Single-page app: pick a mode (Commit / README / Polish), paste dictated notes
(or hit **🎤 Dictate** to talk straight into the browser), optionally paste a diff,
and copy the output. A badge in the header always shows which engine processed
your text — `● local offline engine` unless you've configured an LLM.

## Architecture

```
dictate-docs/
├── dictate_docs/
│   ├── engine.py      # heuristic text pipeline: corrections → fillers →
│   │                  # numbers/casing → run-on & compound splitting
│   ├── commit.py      # unified-diff parser, type/scope inference,
│   │                  # conventional-commit assembly
│   ├── readme_gen.py  # walkthrough → sections (Features/Installation/
│   │                  # Usage/How it works) + existing-README merging
│   ├── llm.py         # optional OpenAI-compatible backend (env-configured)
│   ├── pipeline.py    # single run(mode, …) entry point for CLI + web
│   └── cli.py         # argparse: commit / readme / polish / serve
├── web/
│   ├── server.py      # stdlib http.server + JSON API
│   └── index.html     # single-page UI (Web Speech API mic)
├── fixtures/          # sample diff + dictated notes + expected outputs
└── tests/             # pytest suite (43 tests)
```

## Optional LLM backend

Set these and the LLM is used instead of (or as well as) the local engine;
unset them and everything runs offline — the default, and the honest one.

```bash
export DICTATE_DOCS_LLM=openai        # or a full base URL of any OpenAI-compatible endpoint
export DICTATE_DOCS_MODEL=gpt-4o-mini # optional
export DICTATE_DOCS_API_KEY=sk-...    # required to enable
python -m dictate_docs polish --text "..." --backend auto   # llm if configured
python -m dictate_docs polish --text "..." --backend local  # force offline
python -m dictate_docs polish --text "..." --backend llm    # force llm
```

Any LLM failure (bad key, network error, timeout) falls back to the local
engine rather than failing. No keys are ever hardcoded or logged.

## Limitations (honest ones)

- Heuristics, not understanding: genuinely ambiguous dictation
  (*"the thing, you know, the other thing"*) can't be rescued — the tool cleans,
  it doesn't invent.
- Self-correction recovery keeps the corrected fragment; it won't reconstruct a
  verb the speaker never re-said (*"fixed the parser, I mean"* → dropped).
- Commit type inference is a scorer, not a mind reader — check the header before
  `--commit`.
- The web mic uses the browser's Web Speech API (Chrome/Edge); Firefox/Safari
  users paste transcripts instead.

## License

MIT — see [LICENSE](LICENSE).
