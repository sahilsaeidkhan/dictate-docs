"""CLI + pipeline + LLM-backend unit tests."""

import subprocess
import sys
from pathlib import Path

import pytest

from dictate_docs import llm, pipeline

PROJECT = Path(__file__).resolve().parent.parent
FIXTURES = PROJECT / "fixtures"


def _cli(*args, stdin=None):
    return subprocess.run(
        [sys.executable, "-m", "dictate_docs", *args],
        cwd=PROJECT, capture_output=True, text=True, input=stdin, timeout=30,
    )


def test_cli_commit_matches_expected():
    p = _cli("commit", "--diff", str(FIXTURES / "sample_diff.patch"),
             "--notes-file", str(FIXTURES / "dictated_notes.txt"))
    assert p.returncode == 0, p.stderr
    expected = (FIXTURES / "expected_commit.txt").read_text()
    assert p.stdout.strip() == expected.strip()


def test_cli_polish_matches_expected():
    p = _cli("polish", "--file", str(FIXTURES / "dictated_notes.txt"))
    assert p.returncode == 0, p.stderr
    expected = (FIXTURES / "expected_polish.txt").read_text()
    assert p.stdout.strip() == expected.strip()


def test_cli_readme_matches_expected():
    p = _cli("readme", "--notes-file", str(FIXTURES / "walkthrough.txt"))
    assert p.returncode == 0, p.stderr
    expected = (FIXTURES / "expected_readme.md").read_text()
    assert p.stdout.strip() == expected.strip()


def test_cli_notes_via_stdin():
    p = _cli("polish", stdin="um I shipped it")
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip() == "I shipped it."


def test_cli_commit_no_diff_no_repo_errors():
    p = _cli("commit", "--notes", "fixed a bug")
    # runs outside a git repo with no --diff -> clean error, exit 2
    assert p.returncode == 2


def test_pipeline_modes():
    for mode in ("commit", "readme", "polish"):
        r = pipeline.run(mode, "um I added tests", diff="")
        assert r["backend"] == "local"
        assert isinstance(r["output"], str) and r["output"]


def test_pipeline_unknown_mode():
    with pytest.raises(ValueError):
        pipeline.run("nope", "text")


def test_llm_defaults_to_local(monkeypatch):
    monkeypatch.delenv("DICTATE_DOCS_LLM", raising=False)
    monkeypatch.delenv("DICTATE_DOCS_API_KEY", raising=False)
    info = llm.backend_info()
    assert info["backend"] == "local"
    assert not llm.is_llm_configured()
    assert llm.complete("polish", "hello") is None


def test_llm_detects_configuration(monkeypatch):
    monkeypatch.setenv("DICTATE_DOCS_LLM", "openai")
    monkeypatch.setenv("DICTATE_DOCS_API_KEY", "sk-test-placeholder")
    assert llm.is_llm_configured()
    assert llm.backend_info()["backend"] == "llm:openai"
