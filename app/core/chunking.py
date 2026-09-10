"""Deterministic text chunking.

Splits a source document into bounded, paragraph-aware chunks that are used
as grounding context for flashcard generation. This is plain application
logic; it does not call any model.
"""
import re
from dataclasses import dataclass


@dataclass
class TextChunk:
    index: int
    text: str


def _split_paragraphs(text: str) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", text.strip())
    return [p.strip() for p in paragraphs if p.strip()]


def chunk_text(text: str, max_chars: int = 1200, min_chars: int = 40) -> list[TextChunk]:
    """Greedily pack paragraphs into chunks of at most `max_chars`.

    - Paragraphs longer than `max_chars` are hard-split on sentence boundaries.
    - Chunks shorter than `min_chars` are dropped (too little content to
      generate a meaningful, grounded flashcard from).
    - Deterministic: same input always yields the same chunks in the same order.
    """
    if not text or not text.strip():
        return []

    paragraphs = _split_paragraphs(text)
    chunks: list[str] = []
    current = ""

    def flush():
        nonlocal current
        if len(current.strip()) >= min_chars:
            chunks.append(current.strip())
        current = ""

    for para in paragraphs:
        candidate = f"{current}\n\n{para}".strip() if current else para
        if len(candidate) <= max_chars:
            current = candidate
            continue

        # current chunk is full; flush it before handling this paragraph
        flush()

        if len(para) <= max_chars:
            current = para
            continue

        # paragraph itself exceeds max_chars: split on sentence boundaries
        sentences = re.split(r"(?<=[.!?])\s+", para)
        buf = ""
        for sent in sentences:
            cand = f"{buf} {sent}".strip() if buf else sent
            if len(cand) <= max_chars:
                buf = cand
            else:
                if buf:
                    chunks.append(buf.strip())
                # a single sentence longer than max_chars: hard-cut it
                buf = sent[:max_chars] if len(sent) > max_chars else sent
        if buf:
            current = buf

    flush()

    return [TextChunk(index=i, text=t) for i, t in enumerate(chunks)]
