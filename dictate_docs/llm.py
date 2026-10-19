"""Optional pluggable LLM backend.

Configuration is entirely via environment variables -- nothing is hardcoded:

    DICTATE_DOCS_LLM      "openai" for api.openai.com, or a full base URL of
                          any OpenAI-compatible endpoint (e.g. a local server).
    DICTATE_DOCS_MODEL    model name (default: gpt-4o-mini)
    DICTATE_DOCS_API_KEY  API key for the endpoint

If DICTATE_DOCS_LLM is unset or DICTATE_DOCS_API_KEY is missing, the local
offline heuristic engine is used and callers are told so honestly. Any
network/API failure also falls back to the local engine (complete() returns
None and the caller uses the local path).
"""

import json
import os
import urllib.request

LOCAL_BACKEND = "local"
ENGINE_VERSION = "heuristic-v1"

_SYSTEM_PROMPTS = {
    "commit": (
        "You turn a developer's dictated notes and a git diff into a single "
        "conventional-commit message: 'type(scope): subject' (imperative, "
        "<=72 chars), optional bullet body. Types: feat, fix, docs, style, "
        "refactor, perf, test, chore, ci. Output ONLY the commit message."
    ),
    "readme": (
        "You turn a developer's dictated walkthrough into polished README "
        "sections (Features, Installation, Usage, How it works) in markdown. "
        "Output ONLY the markdown."
    ),
    "polish": (
        "You clean up dictated text: remove filler words (um, uh, you know), "
        "resolve self-corrections keeping the corrected version, split "
        "run-on sentences, fix capitalization. Output ONLY the cleaned text."
    ),
}


def backend_info() -> dict:
    """Describe which backend would be used. No network calls."""
    llm = os.environ.get("DICTATE_DOCS_LLM", "").strip()
    key = os.environ.get("DICTATE_DOCS_API_KEY", "").strip()
    if llm and key:
        model = os.environ.get("DICTATE_DOCS_MODEL", "gpt-4o-mini").strip() \
            or "gpt-4o-mini"
        return {"backend": f"llm:{llm}", "model": model,
                "engine": ENGINE_VERSION}
    return {"backend": LOCAL_BACKEND, "model": ENGINE_VERSION,
            "engine": ENGINE_VERSION}


def is_llm_configured() -> bool:
    return backend_info()["backend"] != LOCAL_BACKEND


def _base_url() -> str:
    llm = os.environ.get("DICTATE_DOCS_LLM", "").strip().lower()
    if llm == "openai":
        return "https://api.openai.com/v1"
    return llm.rstrip("/")


def complete(mode: str, text: str, context: str = "") -> str | None:
    """Ask the LLM backend to process text. Returns None on any failure."""
    info = backend_info()
    if info["backend"] == LOCAL_BACKEND:
        return None
    system = _SYSTEM_PROMPTS.get(mode, _SYSTEM_PROMPTS["polish"])
    user = text if not context else f"{context}\n\n---\n\n{text}"
    payload = {
        "model": info["model"],
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
    }
    try:
        req = urllib.request.Request(
            _base_url() + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer "
                                 + os.environ.get("DICTATE_DOCS_API_KEY", ""),
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None
