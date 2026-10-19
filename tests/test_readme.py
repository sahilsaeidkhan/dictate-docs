"""Unit tests for README generation."""

from pathlib import Path

from dictate_docs import readme_gen

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def test_name_detection_and_sections():
    notes = (FIXTURES / "walkthrough.txt").read_text()
    out = readme_gen.generate_readme(notes)
    assert out.startswith("# Dictate Docs")
    assert "## Features" in out
    assert "## Installation" in out
    assert "## Usage" in out
    assert "## How it works" in out


def test_tagline_not_duplicated_in_features():
    notes = (FIXTURES / "walkthrough.txt").read_text()
    out = readme_gen.generate_readme(notes)
    tagline = ("The project is called dictate docs, it's a voice first dev "
               "tool")
    assert out.count(tagline) == 1


def test_expected_fixture():
    notes = (FIXTURES / "walkthrough.txt").read_text()
    out = readme_gen.generate_readme(notes)
    expected = (FIXTURES / "expected_readme.md").read_text()
    assert out.strip() == expected.strip()


def test_merge_existing_readme():
    existing = ("# Old Name\n\nSome intro.\n\n## Features\n\n- old feature\n\n"
                "## License\n\nMIT\n")
    notes = ("the project is called new thing. it is a fast cli for notes. "
             "it installs with pip install newthing.")
    out = readme_gen.generate_readme(notes, existing=existing)
    assert "# Old Name" in out          # title preserved
    assert "## License" in out          # untouched section preserved
    assert "MIT" in out
    assert "- old feature" not in out   # regenerated Features replaced it
    assert "## Installation" in out     # new section appended


def test_empty_notes_gives_skeleton():
    out = readme_gen.generate_readme("", project_name="Demo")
    assert out.startswith("# Demo")
