"""Single entry point used by the CLI and the web UI."""

from . import commit, engine, llm, readme_gen

MODES = ("commit", "readme", "polish")


def run(mode: str, text: str, diff: str | None = None,
        readme_text: str | None = None, project_name: str | None = None,
        backend: str = "auto") -> dict:
    """Process dictated text.

    backend: "auto" (LLM if configured, else local), "local", or "llm".
    Returns {"output", "backend", "backend_info"} -- backend is the engine
    that actually produced the output ("local" or "llm:<name>").
    """
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")

    info = llm.backend_info()
    want_llm = backend == "llm" or (backend == "auto" and info["backend"]
                                   != llm.LOCAL_BACKEND)
    output = None
    if want_llm:
        context = ""
        if mode == "commit" and diff:
            context = f"GIT DIFF:\n{diff}"
        elif mode == "readme" and readme_text:
            context = f"EXISTING README:\n{readme_text}"
        output = llm.complete(mode, text, context=context)

    if output is None:
        if mode == "commit":
            output = commit.build_commit_message(diff or "", text or "")
        elif mode == "readme":
            output = readme_gen.generate_readme(
                text or "", existing=readme_text,
                project_name=project_name)
        else:
            output = engine.polish_text(text or "")
        used = llm.LOCAL_BACKEND
    else:
        used = info["backend"]

    return {"output": output, "backend": used, "backend_info": info}
