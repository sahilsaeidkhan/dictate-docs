"""Core heuristic text engine.

Turns messy dictated text (the raw output of a dictation app like Wispr Flow)
into clean, structured prose. Handles:

- filler words/phrases: "um", "uh", "you know", "kind of", "basically", ...
- sentence-initial throat clearing: "so...", "well...", "okay so..."
- hedges: "I think", "I feel like", ...
- self-corrections: "X -- no wait, Y", "X, I mean Y", "X, actually Y",
  "let me rephrase ..."
- run-on sentences (dictation often has no punctuation at all)
- repeated words from stuttering: "the the parser"
- capitalization, spacing, sentence casing

Everything here is deterministic and offline. No ML models, no network.
"""

import re

# ---------------------------------------------------------------------------
# Filler words & phrases (removed wherever they appear as standalone fillers)
# ---------------------------------------------------------------------------

# Standalone interjections -- matched with word boundaries so they never hit
# inside real words (e.g. "um" will not match inside "album").
FILLER_WORDS = [
    "um", "uh", "uhm", "erm", "hmm", "ah", "oh",
]

# Multi-word filler phrases, longest first so alternation order is safe.
FILLER_PHRASES = [
    "you know what i mean",
    "you know",
    "kind of",
    "sort of",
    "stuff like that",
    "things like that",
    "and stuff",
    "or whatever",
    "or something",
    "at the end of the day",
    "like i said",
    "as i said",
    "needless to say",
    "to be honest",
    "in other words",
]

_FILLER_PHRASE_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(p) for p in FILLER_PHRASES) + r")\b",
    re.IGNORECASE,
)
_FILLER_WORD_RES = [
    re.compile(r"\b" + re.escape(w) + r"\b", re.IGNORECASE) for w in FILLER_WORDS
]

# "literally" is virtually always an intensifier in dictation, not literal.
_LITERAL_RE = re.compile(r"\bliterally\b[,\s]*", re.IGNORECASE)
# "like" used as an intensifier ("like really fast") -- real verb uses kept.
_LIKE_INTENSIFIER_RE = re.compile(
    r"\blike\s+(really|very|so|super|pretty|quite|just|totally|literally|"
    r"basically)\b", re.IGNORECASE
)
_LIKE_COMMA_RE = re.compile(r",\s*like\s*,", re.IGNORECASE)

# "and also" -> "and".
_AND_ALSO_RE = re.compile(r"\band also\b", re.IGNORECASE)

# "minus" in dev dictation almost always means "-".
# Only collapse before a single letter ("python minus m" -> "python -m");
# "five minus three" is left alone.
_MINUS_RE = re.compile(r" minus (?=[a-zA-Z]\b)", re.IGNORECASE)

# Canonical casing for tech terms people dictate lowercase.
_TECH_CASE = {
    "readme": "README", "api": "API", "apis": "APIs", "cli": "CLI",
    "llm": "LLM", "openai": "OpenAI", "github": "GitHub", "macos": "macOS",
    "ios": "iOS", "javascript": "JavaScript", "typescript": "TypeScript",
    "json": "JSON", "yaml": "YAML", "url": "URL", "http": "HTTP",
}
_TECH_CASE_RES = [(re.compile(r"\b" + k + r"\b", re.IGNORECASE), v)
                  for k, v in _TECH_CASE.items()]

# Wordy constructions -> tight equivalents.
_WORDY = [
    (re.compile(r"\bin order to\b", re.IGNORECASE), "to"),
    (re.compile(r"\bdue to the fact that\b", re.IGNORECASE), "because"),
]

# Sentence-initial throat clearing ("so, ...", "well ...", "okay so ...").
_LEAD_FILLER_RE = re.compile(
    r"^(?:so|well|okay|ok|right|anyway|like|actually|basically|frankly|now|"
    r"also)[,\s]+",
    re.IGNORECASE,
)
# Sentence-initial hedges ("I think this works" -> "This works").
_HEDGE_RE = re.compile(
    r"^(?:i think|i feel like|i believe|i suppose|i reckon|i guess)[,\s]+",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Self-corrections ("X -- no wait, Y"  =>  "Y")
# ---------------------------------------------------------------------------

# Strong correction markers: everything before the LAST marker is discarded.
_CORRECTION_MARKERS = [
    "no wait",
    "wait no",
    "i mean",
    "i meant",
    "rather than",
    "scratch that",
    "strike that",
    "correction",
    "let me rephrase",
    "let me redo that",
    "let me redo",
    "let me start over",
    "hold on",
]
_CORRECTION_RES = [
    re.compile(r"\b" + re.escape(m) + r"\b", re.IGNORECASE)
    for m in _CORRECTION_MARKERS
]

# "X, actually Y" / "X -- actually Y"  =>  "Y"  (but bare "actually" is filler).
_ACTUALLY_CORRECTION_RE = re.compile(
    r"^.*?[,\u2014\u2013-]\s*actually[,.]?\s+(?=\w)", re.IGNORECASE | re.DOTALL
)
_ACTUALLY_FILLER_RE = re.compile(r"\bactually\b[,\s]*", re.IGNORECASE)

# "X, instead Y"  =>  "Y"  (but "X instead of Y" is a real construction).
_INSTEAD_CORRECTION_RE = re.compile(
    r"^.*?[,\u2014\u2013-]\s*instead\s+(?!of\b)(?=\w)", re.IGNORECASE | re.DOTALL
)

# ---------------------------------------------------------------------------
# Run-on splitting (dictation often arrives as one giant unpunctuated blob)
# ---------------------------------------------------------------------------

_RUNON_MARKERS = [
    " and then ",
    " and also ",
    "; then ",
    " then ",
    ", next ",
    ", then ",
    ", finally ",
    ", also ",
    " plus ",
    " which means ",
    " because then ",
]
_RUNON_MIN_WORDS = 26   # only split sentences longer than this
_RUNON_MIN_PART = 5     # each resulting part must have at least this many words

# ---------------------------------------------------------------------------
# Spoken numbers ("thirty seconds" -> "30 seconds", "three point twelve" -> "3.12")
# ---------------------------------------------------------------------------

_NUM_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100,
}
_NUM_WORD_ALTS = "|".join(_NUM_WORDS)
# Only convert when followed by a unit noun (never "one of the ...").
_NUM_UNIT_ALTS = (
    "seconds?|minutes?|hours?|days?|weeks?|months?|requests?|tests?|"
    "files?|lines?|percent|retries|attempts|times|errors?|bugs?"
)
_POINT_RE = re.compile(
    r"\b(" + _NUM_WORD_ALTS + r")\s+point\s+(" + _NUM_WORD_ALTS + r")\b",
    re.IGNORECASE,
)
_NUM_UNIT_RE = re.compile(
    r"\b(" + _NUM_WORD_ALTS + r")\s+(" + _NUM_UNIT_ALTS + r")\b",
    re.IGNORECASE,
)


def _spoken_numbers(s: str) -> str:
    def point(m):
        return f"{_NUM_WORDS[m.group(1).lower()]}.{_NUM_WORDS[m.group(2).lower()]}"

    def unit(m):
        return f"{_NUM_WORDS[m.group(1).lower()]} {m.group(2)}"

    s = _POINT_RE.sub(point, s)
    s = _NUM_UNIT_RE.sub(unit, s)
    return s


# ---------------------------------------------------------------------------
# Compound splitting ("did X, and I also fixed Y" -> two sentences)
# ---------------------------------------------------------------------------

_COMPOUND_RE = re.compile(
    r",\s+and\s+(?=(?:i|we|you|it|this|that|they)\b)",
    re.IGNORECASE,
)
_COMPOUND_MIN_PART = 3


def _split_compound(sentence: str) -> list:
    """Split "did X, and I fixed Y"-style compounds into two sentences."""
    m = _COMPOUND_RE.search(sentence)
    if not m:
        return [sentence]
    a, b = sentence[:m.start()].strip(), sentence[m.end():].strip()
    if len(a.split()) >= _COMPOUND_MIN_PART and len(b.split()) >= _COMPOUND_MIN_PART:
        return [a, b]
    return [sentence]


# Discourse markers that turn into bullet lists when 2+ sentences use them.
_ENUM_MARKERS = ("first", "second", "third", "next", "then", "finally", "also")

# ---------------------------------------------------------------------------
# Imperative conversion (for conventional-commit subjects)
# ---------------------------------------------------------------------------

# past-tense / third-person verb -> imperative base form
_IMPERATIVE_MAP = {
    "added": "add", "adds": "add",
    "fixed": "fix", "fixes": "fix",
    "updated": "update", "updates": "update",
    "removed": "remove", "removes": "remove",
    "refactored": "refactor", "refactors": "refactor",
    "implemented": "implement", "implements": "implement",
    "created": "create", "creates": "create",
    "changed": "change", "changes": "change",
    "improved": "improve", "improves": "improve",
    "bumped": "bump", "bumps": "bump",
    "renamed": "rename", "renames": "rename",
    "moved": "move", "moves": "move",
    "deleted": "delete", "deletes": "delete",
    "migrated": "migrate", "migrates": "migrate",
    "upgraded": "upgrade", "upgrades": "upgrade",
    "reverted": "revert", "reverts": "revert",
    "merged": "merge", "merges": "merge",
    "rewrote": "rewrite", "rewrites": "rewrite",
    "cleaned": "clean", "cleans": "clean",
    "simplified": "simplify", "simplifies": "simplify",
    "optimized": "optimize", "optimizes": "optimize",
    "documented": "document", "documents": "document",
    "tested": "test", "tests": "test",
    "handled": "handle", "handles": "handle",
    "resolved": "resolve", "resolves": "resolve",
    "prevented": "prevent", "prevents": "prevent",
    "allowed": "allow", "allows": "allow",
    "enabled": "enable", "enables": "enable",
    "disabled": "disable", "disables": "disable",
    "switched": "switch", "switches": "switch",
    "replaced": "replace", "replaces": "replace",
    "extracted": "extract", "extracts": "extract",
    "introduced": "introduce", "introduces": "introduce",
    "wired": "wire", "wires": "wire",
    "dropped": "drop", "drops": "drop",
    "sped": "speed",
    "made": "make", "makes": "make",
    "finished": "finish", "finishes": "finish",
}


# ---------------------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------------------

def _recover_verb(dropped: str, kept: str) -> str:
    """Prepend a lost verb after a self-correction cut.

    "fixed the parser, I mean the tokenizer" -> "fixed the tokenizer".
    Only when the dropped prefix is short and starts with a known
    past-tense verb; otherwise the kept fragment stands on its own.
    """
    if len(dropped.split()) > 4:
        return kept
    m = re.match(r"^(?:i|we|you\s+)?([a-z]+)\b", dropped.strip(),
                 re.IGNORECASE)
    if not m or m.group(1).lower() not in _IMPERATIVE_MAP:
        return kept
    first = kept.strip().split(" ", 1)[0].lower()
    if first in _KNOWN_BASE_VERBS:
        return kept  # the correction already has its own verb
    return f"{m.group(1).lower()} {kept.strip()}"


def _resolve_corrections(sentence: str) -> str:
    """Apply self-correction handling to a single sentence."""
    s = sentence
    # Strong markers: keep text after the LAST marker in the sentence.
    for rx in _CORRECTION_RES:
        matches = list(rx.finditer(s))
        if matches:
            m = matches[-1]
            after = s[m.end():].lstrip(" ,\u2014\u2013-:;")
            if after.strip():
                dropped = s[:m.start()].rstrip(" ,\u2014\u2013-:;")
                s = _recover_verb(dropped, after)
    # ", actually Y" / "-- actually Y"  ->  "Y"
    s = _ACTUALLY_CORRECTION_RE.sub("", s)
    # ", instead Y" (not "instead of")  ->  "Y"
    s = _INSTEAD_CORRECTION_RE.sub("", s)
    # "let me rephrase"-style markers already handled above via marker list;
    # drop any leading connector left behind by a cut.
    s = re.sub(r"^(?:and|but|so|well)\b[,\s]+", "", s, flags=re.IGNORECASE)
    return s


def _strip_fillers(sentence: str) -> str:
    """Remove filler words/phrases, hedges and throat-clearing."""
    s = sentence
    # Leading throat-clearing + hedges first (loop: "okay so well ..." stacks).
    while True:
        new = _LEAD_FILLER_RE.sub("", s)
        new = _HEDGE_RE.sub("", new)
        if new == s:
            break
        s = new
    # Multi-word filler phrases.
    s = _FILLER_PHRASE_RE.sub("", s)
    # Standalone interjections.
    for rx in _FILLER_WORD_RES:
        s = rx.sub("", s)
    # Intensifier "like" / bare "literally" / leftover "actually".
    s = _LIKE_INTENSIFIER_RE.sub(r"\1", s)
    s = _LIKE_COMMA_RE.sub(",", s)
    s = _LITERAL_RE.sub("", s)
    s = _ACTUALLY_FILLER_RE.sub("", s)
    # Repeated phrases left by filler removal: "forever, forever," -> "forever,".
    s = re.sub(r"\b(\w+(?:\s+\w+){0,2}),\s*\1(?=\s*[,.)!?]|$)", r"\1", s,
               flags=re.IGNORECASE)
    # "I also fixed" -> "I fixed" ("also" after a pronoun is filler).
    s = re.sub(r"\b(i|we|you)\s+also\b", r"\1", s, flags=re.IGNORECASE)
    # "and also" -> "and".
    s = _AND_ALSO_RE.sub("and", s)
    # Spoken "minus" -> "-" (single-letter flag only).
    s = _MINUS_RE.sub(" -", s)
    # Spoken numbers -> digits.
    s = _spoken_numbers(s)
    # Canonical tech-term casing.
    for rx, rep in _TECH_CASE_RES:
        s = rx.sub(rep, s)
    # Wordy constructions.
    for rx, rep in _WORDY:
        s = rx.sub(rep, s)
    # Stuttered repeats: "the the parser" -> "the parser".
    for _ in range(3):
        s = re.sub(r"\b(\w+)\s+\1\b", r"\1", s, flags=re.IGNORECASE)
    # Spacing / punctuation cleanup.
    s = re.sub(r"\s+([,.!?;:])", r"\1", s)
    s = re.sub(r",\s*,", ",", s)
    s = re.sub(r"^(?:and|but)\b[,\s]+", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip(" ,;:")
    # Lone "i" -> "I".
    s = re.sub(r"\bi\b", "I", s)
    return s


def _finish_sentence(s: str) -> str:
    """Capitalize first letter and ensure terminal punctuation."""
    s = s.strip(" ,;:")
    if not s:
        return ""
    s = s[0].upper() + s[1:]
    if s[-1] not in ".!?":
        s += "."
    return s


def split_sentences(text: str) -> list:
    """Split text into rough sentences on existing punctuation."""
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    # "new paragraph" as a spoken dictation command -> paragraph break.
    text = re.sub(r"([.!?])\s*\bnew paragraph\b\s*",
                  r"\1\n\n", text, flags=re.IGNORECASE)
    parts = re.split(r"(?<=[.!?\u2026])\s+|\n\n+", text)
    return [p.strip() for p in parts if p.strip()]


def _split_runon(sentence: str) -> list:
    """Split an over-long run-on sentence on discourse markers."""
    words = sentence.split()
    if len(words) <= _RUNON_MIN_WORDS:
        return [sentence]
    for marker in _RUNON_MARKERS:
        idx = sentence.lower().find(marker)
        if idx == -1:
            continue
        a, b = sentence[:idx].strip(), sentence[idx + len(marker):].strip()
        if len(a.split()) >= _RUNON_MIN_PART and len(b.split()) >= _RUNON_MIN_PART:
            return _split_runon(a) + _split_runon(b)
    return [sentence]


def polish_sentences(text: str) -> list:
    """Full pipeline: dictated text -> list of clean sentences."""
    out = []
    seen = set()
    for raw in split_sentences(text):
        s = _resolve_corrections(raw)
        s = _strip_fillers(s)
        if not s or len(s.split()) < 2:
            continue
        for part in _split_runon(s):
            for sub in _split_compound(part):
                sub = _strip_fillers(sub)
                finished = _finish_sentence(sub)
                if not finished or len(finished.split()) < 2:
                    continue
                # De-dupe repeated sentences (people repeat themselves dictating).
                key = finished.lower()
                if key in seen:
                    continue
                seen.add(key)
                out.append(finished)
    return out


def _to_bullets(sentences: list) -> list:
    """Convert enumerated discourse markers into a markdown bullet list."""
    marked = 0
    for s in sentences:
        first = s.split(" ", 1)[0].rstrip(",.").lower()
        if first in _ENUM_MARKERS:
            marked += 1
    if marked < 2:
        return sentences
    out = []
    for s in sentences:
        first, _, rest = s.partition(" ")
        if first.rstrip(",.").lower() in _ENUM_MARKERS and rest:
            out.append("- " + _finish_sentence(rest))
        else:
            out.append(s)
    return out


def polish_text(text: str, paragraphs: bool = True) -> str:
    """Dictated text -> clean markdown (paragraphs, bullets where natural)."""
    sentences = polish_sentences(text)
    if not sentences:
        return ""
    sentences = _to_bullets(sentences)
    if not paragraphs:
        return "\n".join(sentences)
    # Group into paragraphs of ~3 sentences; keep bullets on their own lines.
    chunks, buf = [], []
    for s in sentences:
        if s.startswith("- "):
            if buf:
                chunks.append(" ".join(buf))
                buf = []
            chunks.append(s)
        else:
            buf.append(s)
            if len(buf) >= 3:
                chunks.append(" ".join(buf))
                buf = []
    if buf:
        chunks.append(" ".join(buf))
    return "\n\n".join(chunks)


def to_imperative(sentence: str, default_verb: str | None = None) -> str:
    """Convert a sentence to imperative mood for commit subjects.

    "I added retry logic" -> "add retry logic"; "this fixes the crash"
    -> "fix the crash". When the sentence is a fragment with no leading
    verb ("exponential backoff ..."), `default_verb` ("add"/"fix"/...) is
    prepended so the subject stays a proper imperative.
    """
    s = sentence.strip().rstrip(".")
    s = re.sub(r"^(?:i|we)\s+", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^(?:this|it|that)\s+", "", s, flags=re.IGNORECASE)
    m = re.match(r"^([A-Za-z']+)(.*)$", s, re.DOTALL)
    if m:
        verb, rest = m.group(1), m.group(2)
        base = _IMPERATIVE_MAP.get(verb.lower())
        if base:
            return (base + rest).strip()
        if verb.lower() in _KNOWN_BASE_VERBS:
            return s
        if default_verb:
            return f"{default_verb} {s[0].lower() + s[1:]}".strip()
    return s


# Base-form verbs already in imperative mood (not in _IMPERATIVE_MAP keys).
_KNOWN_BASE_VERBS = set(_IMPERATIVE_MAP.values()) | {
    "support", "use", "keep", "ensure", "avoid", "require", "include",
    "exclude", "check", "verify", "send", "fetch", "load", "save", "parse",
    "render", "build", "run", "start", "stop", "show", "log", "handle",
    "retry",
}

# Canonical imperative verb per conventional-commit type (subject fallback).
_TYPE_VERBS = {
    "feat": "add", "fix": "fix", "docs": "document", "style": "format",
    "refactor": "refactor", "perf": "improve", "test": "add",
    "chore": "update", "ci": "configure",
}


def fit_length(s: str, limit: int = 72) -> str:
    """Truncate to `limit` chars at a word boundary (conventional commits)."""
    s = s.strip()
    if len(s) <= limit:
        return s
    cut = s[:limit].rsplit(" ", 1)[0]
    return cut if cut else s[:limit]
