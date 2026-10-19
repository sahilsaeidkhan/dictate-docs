"""Unit tests for the heuristic text engine."""

from dictate_docs import engine


def test_filler_stripping():
    out = engine.polish_sentences("um so basically I added tests you know")
    assert out == ["I added tests."]


def test_interjections_and_hedges():
    out = engine.polish_sentences("uh, I think this fixes the crash")
    assert out == ["This fixes the crash."]


def test_self_correction_no_wait():
    out = engine.polish_sentences(
        "I added a login endpoint, no wait, a signup endpoint")
    assert out == ["A signup endpoint."]


def test_self_correction_i_mean():
    out = engine.polish_sentences("fixed the parser, I mean the tokenizer")
    assert out == ["Fixed the tokenizer."]


def test_self_correction_actually():
    out = engine.polish_sentences(
        "the bug was in the cache, actually in the queue")
    assert out == ["In the queue."]


def test_self_correction_let_me_rephrase():
    out = engine.polish_sentences(
        "let me rephrase. The deploy failed on missing env vars.")
    assert out == ["The deploy failed on missing env vars."]


def test_runon_splitting():
    text = ("I refactored the auth module and then I updated the login page "
            "and then I fixed the redirect loop and then I added tests "
            "for the whole flow and then I deployed to staging")
    out = engine.polish_sentences(text)
    assert len(out) >= 3
    assert out[0] == "I refactored the auth module."


def test_compound_splitting():
    out = engine.polish_sentences(
        "I added retries, and I also fixed the timeout bug")
    assert out == ["I added retries.", "I fixed the timeout bug."]


def test_repeated_words_and_sentences():
    out = engine.polish_sentences(
        "the the parser is fast. The parser is fast.")
    assert out == ["The parser is fast."]


def test_spoken_numbers():
    out = engine.polish_sentences(
        "the timeout is thirty seconds and it needs python three point twelve")
    assert out == ["The timeout is 30 seconds and it needs python 3.12."]


def test_spoken_minus_flag():
    out = engine.polish_sentences("run python minus m dictate docs")
    assert out == ["Run python -m dictate docs."]


def test_tech_term_casing():
    out = engine.polish_sentences("updated the readme and the api client")
    assert out == ["Updated the README and the API client."]


def test_imperative_known_verb():
    assert engine.to_imperative("I added retry logic") == "add retry logic"
    assert engine.to_imperative("this fixes the crash") == "fix the crash"


def test_imperative_fragment_with_default_verb():
    out = engine.to_imperative("Exponential backoff with jitter",
                               default_verb="add")
    assert out == "add exponential backoff with jitter"


def test_imperative_already_imperative():
    assert engine.to_imperative("Add retry logic") == "Add retry logic"


def test_fit_length():
    long = "add " + "x" * 100
    out = engine.fit_length(long)
    assert len(out) <= 72
    assert not out.endswith(" ")


def test_empty_input():
    assert engine.polish_sentences("") == []
    assert engine.polish_text("   ") == ""


def test_enum_bullets():
    text = ("first I set up the repo. second I wrote the engine. "
            "third I added the web UI.")
    out = engine.polish_text(text)
    assert "- I set up the repo." in out
    assert "- I wrote the engine." in out


def test_like_intensifier():
    out = engine.polish_sentences("the cache is like really fast")
    assert out == ["The cache is really fast."]
