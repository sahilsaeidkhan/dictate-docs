"""Conventional-commit message generation from a diff + dictated notes."""

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import engine

# ---------------------------------------------------------------------------
# Diff parsing
# ---------------------------------------------------------------------------

@dataclass
class FileChange:
    path: str
    added: int = 0
    deleted: int = 0
    status: str = "modified"  # new | deleted | renamed | modified


@dataclass
class DiffStat:
    files: list = field(default_factory=list)

    @property
    def total_added(self):
        return sum(f.added for f in self.files)

    @property
    def total_deleted(self):
        return sum(f.deleted for f in self.files)

    @property
    def total_changed(self):
        return self.total_added + self.total_deleted


def parse_diff(text: str) -> DiffStat:
    """Parse unified diff output (e.g. `git diff`) into a DiffStat."""
    stat = DiffStat()
    current = None

    def push():
        nonlocal current
        if current is not None:
            stat.files.append(current)
            current = None

    for line in text.splitlines():
        if line.startswith("diff --git"):
            push()
            # diff --git a/path b/path
            parts = line.split(" ")
            b_path = parts[-1]
            path = b_path[2:] if b_path.startswith("b/") else b_path
            current = FileChange(path=path)
        elif line.startswith("new file mode"):
            if current:
                current.status = "new"
        elif line.startswith("deleted file mode"):
            if current:
                current.status = "deleted"
        elif line.startswith("rename from"):
            if current:
                current.status = "renamed"
        elif line.startswith("+++ b/"):
            if current and current.path in ("", "dev/null"):
                current.path = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            if current:
                current.added += 1
        elif line.startswith("-") and not line.startswith("---"):
            if current:
                current.deleted += 1
    push()
    return stat


def get_staged_diff() -> str | None:
    """Return `git diff --cached` output, or None if unavailable/empty."""
    try:
        out = subprocess.run(
            ["git", "diff", "--cached"],
            capture_output=True, text=True, timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    text = out.stdout.strip()
    return text or None


# ---------------------------------------------------------------------------
# Type & scope inference (Conventional Commits)
# ---------------------------------------------------------------------------

_SOURCE_EXTS = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java",
                ".rb", ".php", ".c", ".cpp", ".h", ".cs", ".kt", ".swift"}

_NOTE_SIGNALS = {
    "fix": [r"\bfix", r"\bbug", r"\bcrash", r"\bbroken", r"\bissue\b",
            r"\berror", r"\bpatch", r"\bhotfix", r"\bregress"],
    "feat": [r"\badd", r"\bnew\b", r"\bimplement", r"\bfeature",
             r"\bintroduc", r"\bsupport"],
    "refactor": [r"\brefactor", r"\bclean ?up", r"\bcleanup", r"\bsimplif",
                 r"\brestructur", r"\breorganiz", r"\brename", r"\bmove"],
    "test": [r"\btest", r"\bspec", r"\bcoverage"],
    "docs": [r"\bdoc", r"\breadme", r"\bcomment"],
    "perf": [r"\bperf", r"\bfaster", r"\bspeed", r"\boptimiz", r"\blaten",
             r"\bslow"],
    "style": [r"\bformat", r"\blint", r"\bstyle", r"\bwhitespace"],
    "chore": [r"\bbump", r"\bupgrad", r"\bdependen", r"\bconfig", r"\bci\b",
              r"\bbuild"],
}

# Tie-break order when scores are equal (most "meaningful" first).
_TYPE_PRIORITY = ["fix", "feat", "test", "docs", "perf", "refactor",
                  "style", "ci", "chore"]


def _is_test_path(p: str) -> bool:
    base = p.rsplit("/", 1)[-1]
    return (base.startswith("test_") or base.endswith("_test.py")
            or base.endswith(".spec.js") or base.endswith(".spec.ts")
            or "/tests/" in p or p.startswith("tests/"))


def _is_docs_path(p: str) -> bool:
    base = p.rsplit("/", 1)[-1]
    low = p.lower()
    return (low.endswith((".md", ".rst", ".txt"))
            or "/docs/" in low or low.startswith("docs/")
            or base.upper() in ("README", "README.md", "CHANGELOG", "CHANGELOG.md",
                                "LICENSE", "LICENSE.md"))


def _is_source_path(p: str) -> bool:
    return Path(p).suffix.lower() in _SOURCE_EXTS


def _is_config_path(p: str) -> bool:
    low = p.lower()
    base = low.rsplit("/", 1)[-1]
    return ("/.github/workflows/" in low or base == "dockerfile"
            or low.endswith((".yml", ".yaml", ".toml", ".cfg", ".ini"))
            or base in ("makefile", "docker-compose.yml", "docker-compose.yaml"))


def _is_dep_path(p: str) -> bool:
    base = p.lower().rsplit("/", 1)[-1]
    return base in ("requirements.txt", "package.json", "package-lock.json",
                    "yarn.lock", "poetry.lock", "pipfile", "cargo.toml",
                    "cargo.lock", "go.mod", "go.sum", "pyproject.toml",
                    "setup.py", "setup.cfg", "gemfile", "gemfile.lock")


def infer_type_and_scope(stat: DiffStat, notes: str) -> tuple:
    """Return (type, scope, evidence) from diff stats + dictated notes."""
    scores = {t: 0 for t in _TYPE_PRIORITY}
    evidence = []

    # --- notes evidence (weighted x2: the human knows what they did) ---
    low = notes.lower()
    for ctype, patterns in _NOTE_SIGNALS.items():
        for pat in patterns:
            if re.search(pat, low):
                scores[ctype] += 2
                evidence.append(f"notes suggest '{ctype}'")
                break

    # --- diff evidence ---
    paths = [f.path for f in stat.files]
    if paths:
        if all(_is_test_path(p) for p in paths):
            scores["test"] += 3
            evidence.append("all changed files are tests")
        if all(_is_docs_path(p) for p in paths):
            scores["docs"] += 3
            evidence.append("all changed files are docs")
        new_sources = [f for f in stat.files
                       if f.status == "new" and _is_source_path(f.path)]
        if new_sources:
            scores["feat"] += 2
            evidence.append(f"{len(new_sources)} new source file(s)")
        if any(_is_dep_path(p) for p in paths):
            scores["chore"] += 2
            evidence.append("dependency manifest changed")
        if all(_is_config_path(p) for p in paths):
            scores["ci"] += 3
            evidence.append("only CI/config files changed")
        if (stat.total_changed < 20
                and any(f.status == "modified" and _is_source_path(f.path)
                        for f in stat.files)):
            scores["fix"] += 1
            scores["refactor"] += 1
            evidence.append("small change to existing source")

    best = max(_TYPE_PRIORITY, key=lambda t: (scores[t],
                                              -_TYPE_PRIORITY.index(t)))
    if scores[best] == 0:
        best = "chore"
        evidence.append("no strong signal; defaulted to chore")

    scope = _infer_scope(stat)
    return best, scope, evidence


def _infer_scope(stat: DiffStat) -> str:
    """Derive a conventional-commit scope from changed paths."""
    paths = [f.path for f in stat.files if f.path]
    if not paths:
        return ""
    if len(paths) == 1:
        p = Path(paths[0])
        stem = p.stem
        if stem.startswith("test_"):
            stem = stem[len("test_"):]
        if stem in ("__init__", "index", "main"):
            return p.parent.name if str(p.parent) not in (".", "") else ""
        return stem
    # Multiple files: the directory with the most changed lines.
    counts = {}
    for f in stat.files:
        parent = str(Path(f.path).parent)
        if parent in (".", ""):
            continue
        counts[parent] = counts.get(parent, 0) + f.added + f.deleted
    if counts:
        return Path(max(counts, key=counts.get)).name
    return ""


# ---------------------------------------------------------------------------
# Message assembly
# ---------------------------------------------------------------------------

def _synthesize_subject(stat: DiffStat, ctype: str, scope: str) -> str:
    """Fallback subject when no dictated notes are available."""
    stems = []
    for f in stat.files:
        stem = Path(f.path).stem
        if stem not in stems:
            stems.append(stem)
    if ctype == "feat" and any(f.status == "new" for f in stat.files):
        core = "add " + ", ".join(stems[:3])
    elif any(f.status == "deleted" for f in stat.files):
        core = "remove " + ", ".join(stems[:3])
    elif scope:
        core = f"update {scope}"
    elif stems:
        core = "update " + ", ".join(stems[:3])
    else:
        core = "update code"
    return engine.fit_length(core)


def _body_sentence(s: str) -> str:
    """Make a body bullet read cleanly: drop first person, use imperative."""
    s = s.rstrip(".")
    s = re.sub(r"^(?:i|we)\s+", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^also\s+", "", s, flags=re.IGNORECASE)
    m = re.match(r"^([A-Za-z']+)(.*)$", s, re.DOTALL)
    if m:
        base = engine._IMPERATIVE_MAP.get(m.group(1).lower())
        if base:
            s = base + m.group(2)
    return engine._finish_sentence(s)


def build_commit_message(diff_text: str, notes_text: str = "") -> str:
    """Build a full conventional-commit message from diff + dictated notes."""
    stat = parse_diff(diff_text or "")
    sentences = engine.polish_sentences(notes_text or "")
    ctype, scope, _evidence = infer_type_and_scope(stat, notes_text or "")
    default_verb = engine._TYPE_VERBS.get(ctype)

    if sentences:
        subject = engine.to_imperative(sentences[0], default_verb=default_verb)
        subject = engine.fit_length(subject)
        body_lines = []
        for s in sentences[1:]:
            bullet = _body_sentence(s)
            if bullet.rstrip(".").lower() != subject.rstrip(".").lower():
                body_lines.append(f"- {bullet}")
    else:
        subject = _synthesize_subject(stat, ctype, scope)
        body_lines = []

    header = f"{ctype}({scope}): {subject}" if scope else f"{ctype}: {subject}"

    parts = [header]
    if body_lines:
        parts.append("\n".join(body_lines))
    if stat.files:
        parts.append(
            f"{len(stat.files)} file(s) changed, "
            f"+{stat.total_added} -{stat.total_deleted}"
        )
    return "\n\n".join(parts)
