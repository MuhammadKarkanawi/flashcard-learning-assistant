from app.core.dedupe import find_duplicate, similarity


def test_identical_strings_have_similarity_one():
    assert similarity("What is TCP?", "What is TCP?") == 1.0


def test_case_and_whitespace_insensitive():
    assert similarity("What is TCP?", "what   is tcp?") > 0.95


def test_find_duplicate_detects_near_duplicate():
    existing = ["What is the capital of France?", "Define spaced repetition."]
    dup = find_duplicate("What is the capital city of France?", existing, threshold=0.8)
    assert dup == "What is the capital of France?"


def test_find_duplicate_returns_none_for_novel_question():
    existing = ["What is the capital of France?"]
    dup = find_duplicate("Explain the SM-2 algorithm.", existing, threshold=0.85)
    assert dup is None


def test_threshold_is_respected():
    existing = ["What causes rain?"]
    # loosely related but should not match at a strict threshold
    assert find_duplicate("What causes snow?", existing, threshold=0.95) is None
