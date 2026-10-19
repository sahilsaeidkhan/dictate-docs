"""README section generation from a dictated walkthrough."""

import re
from pathlib import Path

from . import engine

# Keywords that route a polished sentence into a README section.
_SECTION_KEYWORDS = {
    "installation": [
        "install", "setup", "set up", "prerequisite", "requirement",
        "dependency", "dependencies", "clone", "pip install", "npm install",
    ],
    "usage": [
        "usage", "use it", "run ", "running", "command", "example",
        "try it", "start the", "launch",
    ],
    "how": [
        "how it works", "under the hood", "architecture", "pipeline",
        "engine", "internally", "design",
    ],
}

_NAME_PATTERNS = [
    re.compile(r"\bproject\s+(?:is\s+)?called\s+"
               r"([a-z][\w.-]*(?:\s+[a-z][\w.-]*){0,3})", re.IGNORECASE),
    re.compile(r"\bcalled\s+([a-z][\w.-]*(?:\s+[a-z][\w.-]*){0,3})",
               re.IGNORECASE),
    re.compile(r"\bnamed\s+([a-z][\w.-]*(?:\s+[a-z][\w.-]*){0,3})",
               re.IGNORECASE),
]

_COMMAND_RE = re.compile(
    r"^\s*(?:\$\s*)?(pip|pip3|python|python3|npm|npx|node|git|docker|"
    r"uvicorn|make|cd|poetry|cargo|go)\b"
)


def _detect_name(notes: str, existing: str | None,
                 fallback: str | None) -> str:
    for pat in _NAME_PATTERNS:
        m = pat.search(notes)
        if m:
            raw = m.group(1).strip().rstrip(".")
            return " ".join(w.capitalize() for w in raw.split())
    if existing:
        m = re.search(r"^#\s+(.+)$", existing, re.MULTILINE)
        if m:
            return m.group(1).strip()
    return fallback or "My Project"


def _classify(sentence: str) -> str:
    low = sentence.lower()
    for section, keywords in _SECTION_KEYWORDS.items():
        if any(k in low for k in keywords):
            return section
    return "features"


def _is_command(sentence: str) -> bool:
    s = sentence.strip().strip("`")
    return bool(_COMMAND_RE.match(s)) or (
        "`" in sentence and len(sentence.split()) <= 8
    )


def _clean_command(sentence: str) -> str:
    s = sentence.strip().rstrip(".")
    s = re.sub(r"^run\s+", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^type\s+", "", s, flags=re.IGNORECASE)
    return s.strip("` ").strip()


_ENUM_STRIP_RE = re.compile(
    r"^(?:first|second|third|next|then|finally|also)[,\s]+", re.IGNORECASE
)


def _bullet(s: str) -> str:
    s = _ENUM_STRIP_RE.sub("", s)
    s = re.sub(r"^usage is (?:you )?run\s+", "Run ", s, flags=re.IGNORECASE)
    return "- " + engine._finish_sentence(s)


def generate_readme(notes: str, existing: str | None = None,
                    project_name: str | None = None) -> str:
    """Build (or update) a README from dictated walkthrough notes."""
    sentences = engine.polish_sentences(notes or "")
    name = _detect_name(notes or "", existing, project_name)

    # Tagline: first sentence that describes the project, else first sentence.
    tagline, tagline_idx = "", -1
    if sentences:
        tagline, tagline_idx = sentences[0], 0
        for i, s in enumerate(sentences):
            low = s.lower()
            if name.lower().split()[0] in low or any(
                    w in low for w in ("tool", "app", "project", "CLI",
                                       "library", "turns", "lets", "helps")):
                tagline, tagline_idx = s, i
                break

    buckets = {"features": [], "installation": [], "usage": [], "how": []}
    for i, s in enumerate(sentences):
        if i == tagline_idx:
            continue  # tagline already shown under the title
        buckets[_classify(s)].append(s)

    sections = []
    if buckets["features"]:
        bullets = "\n".join(_bullet(s) for s in buckets["features"])
        sections.append(("Features", bullets))
    if buckets["installation"]:
        steps, cmds = [], []
        for s in buckets["installation"]:
            if _is_command(s):
                cmds.append(_clean_command(s))
            else:
                steps.append(s)
        body = ""
        if steps:
            body += "\n".join(
                f"{i}. {engine._finish_sentence(_ENUM_STRIP_RE.sub('', s))}"
                for i, s in enumerate(steps, 1))
        if cmds:
            if body:
                body += "\n\n"
            body += "```bash\n" + "\n".join(cmds) + "\n```"
        sections.append(("Installation", body))
    if buckets["usage"]:
        cmds = [_clean_command(s) for s in buckets["usage"]
                if _is_command(s)]
        rest = [s for s in buckets["usage"] if not _is_command(s)]
        body = ""
        if cmds:
            body += "```bash\n" + "\n".join(cmds) + "\n```"
        if rest:
            if body:
                body += "\n\n"
            body += "\n".join(_bullet(s) for s in rest)
        sections.append(("Usage", body))
    if buckets["how"]:
        sections.append(("How it works", "\n\n".join(buckets["how"])))

    if existing:
        return _merge_existing(existing, name, tagline, sections)
    header = f"# {name}\n\n{tagline}\n" if tagline else f"# {name}\n"
    body = "\n\n".join(f"## {title}\n\n{content}"
                       for title, content in sections)
    return (header + ("\n" + body if body else "")).rstrip() + "\n"


def _merge_existing(existing: str, name: str, tagline: str,
                    sections: list) -> str:
    """Merge generated sections into an existing README, preserving the rest."""
    new_by_title = {t.lower(): (t, c) for t, c in sections}
    lines = existing.splitlines()
    out, i = [], 0
    # Keep everything up to the first ## section (title + intro).
    while i < len(lines):
        if lines[i].startswith("## "):
            break
        out.append(lines[i])
        i += 1
    replaced = set()
    # Walk existing sections: replace ones we regenerated, keep the rest.
    while i < len(lines):
        line = lines[i]
        if line.startswith("## "):
            title = line[3:].strip()
            key = title.lower()
            # Collect existing section body.
            j = i + 1
            while j < len(lines) and not lines[j].startswith("## "):
                j += 1
            if key in new_by_title:
                t, c = new_by_title[key]
                out.append(f"## {t}")
                out.append("")
                out.append(c)
                replaced.add(key)
            else:
                out.extend(lines[i:j])
            i = j
        else:
            out.append(line)
            i += 1
    # Append regenerated sections that did not exist yet.
    for key, (t, c) in new_by_title.items():
        if key not in replaced:
            if out and out[-1].strip():
                out.append("")
            out.append(f"## {t}")
            out.append("")
            out.append(c)
    return "\n".join(out).rstrip() + "\n"
