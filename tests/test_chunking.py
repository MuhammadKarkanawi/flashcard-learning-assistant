from app.core.chunking import chunk_text


def test_empty_text_yields_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_short_text_below_min_length_is_dropped():
    assert chunk_text("too short", max_chars=1000, min_chars=40) == []


def test_paragraphs_are_packed_up_to_max_chars():
    paragraphs = ["A" * 100, "B" * 100, "C" * 100]
    text = "\n\n".join(paragraphs)
    chunks = chunk_text(text, max_chars=250, min_chars=10)
    assert all(len(c.text) <= 250 for c in chunks)
    # all content preserved across chunks
    assert "".join(c.text.replace("\n\n", "") for c in chunks).count("A") == 100


def test_chunk_indices_are_sequential():
    text = "\n\n".join(["Para " + str(i) * 60 for i in range(5)])
    chunks = chunk_text(text, max_chars=80, min_chars=5)
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_oversized_single_paragraph_is_split_on_sentences():
    long_para = ("This is a sentence. " * 100).strip()
    chunks = chunk_text(long_para, max_chars=200, min_chars=5)
    assert len(chunks) > 1
    assert all(len(c.text) <= 200 for c in chunks)


def test_is_deterministic():
    text = "\n\n".join(["Paragraph number " + str(i) for i in range(20)])
    assert chunk_text(text, max_chars=100) == chunk_text(text, max_chars=100)
