"""Unit tests for diff parsing and conventional-commit inference."""

from pathlib import Path

from dictate_docs import commit

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _diff(*files):
    """Build a tiny unified diff for the given (path, added, deleted, new)."""
    chunks = []
    for path, added, deleted, is_new in files:
        header = f"diff --git a/{path} b/{path}\n"
        if is_new:
            header += "new file mode 100644\n"
        header += f"--- {'/dev/null' if is_new else 'a/' + path}\n"
        header += f"+++ b/{path}\n"
        body = "".join(f"+line{i}\n" for i in range(added))
        body += "".join(f"-line{i}\n" for i in range(deleted))
        chunks.append(header + body)
    return "".join(chunks)


def test_parse_diff_counts():
    stat = commit.parse_diff(_diff(("a.py", 10, 2, False),
                                    ("b.py", 0, 0, True)))
    assert len(stat.files) == 2
    assert stat.files[0].added == 10
    assert stat.files[0].deleted == 2
    assert stat.files[1].status == "new"
    assert stat.total_added == 10


def test_infer_fix_from_notes_and_small_diff():
    stat = commit.parse_diff(_diff(("pkg/client.py", 3, 1, False)))
    ctype, scope, _ = commit.infer_type_and_scope(stat, "fixed the timeout bug")
    assert ctype == "fix"
    assert scope == "client"


def test_infer_feat_from_new_file():
    stat = commit.parse_diff(_diff(("pkg/retry.py", 40, 0, True)))
    ctype, scope, _ = commit.infer_type_and_scope(stat, "added retry helper")
    assert ctype == "feat"
    assert scope == "retry"


def test_infer_test_from_test_files():
    stat = commit.parse_diff(_diff(("tests/test_retry.py", 20, 0, True)))
    ctype, scope, _ = commit.infer_type_and_scope(stat, "added coverage")
    assert ctype == "test"
    assert scope == "retry"  # test_ prefix stripped


def test_infer_docs():
    stat = commit.parse_diff(_diff(("README.md", 30, 5, False)))
    ctype, _, _ = commit.infer_type_and_scope(stat, "updated the readme")
    assert ctype == "docs"


def test_infer_chore_deps():
    stat = commit.parse_diff(_diff(("requirements.txt", 2, 1, False)))
    ctype, _, _ = commit.infer_type_and_scope(stat, "bumped deps")
    assert ctype == "chore"


def test_scope_multi_file_most_changed_dir():
    stat = commit.parse_diff(_diff(("pkg/a.py", 50, 0, True),
                                    ("tests/test_a.py", 5, 0, True)))
    _, scope, _ = commit.infer_type_and_scope(stat, "added helper")
    assert scope == "pkg"


def test_full_message_on_fixture():
    diff = (FIXTURES / "sample_diff.patch").read_text()
    notes = (FIXTURES / "dictated_notes.txt").read_text()
    msg = commit.build_commit_message(diff, notes)
    expected = (FIXTURES / "expected_commit.txt").read_text().strip()
    assert msg.strip() == expected


def test_message_shape():
    msg = commit.build_commit_message(
        _diff(("pkg/x.py", 4, 1, False)), "um I fixed the crash")
    lines = msg.splitlines()
    assert lines[0] == "fix(x): fix the crash"
    assert len(lines[0]) <= 72
    assert "1 file(s) changed" in msg


def test_message_without_notes_synthesizes_from_diff():
    msg = commit.build_commit_message(
        _diff(("pkg/cache.py", 60, 0, True)), "")
    assert msg.splitlines()[0].startswith("feat(cache): add cache")
