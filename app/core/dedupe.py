"""Deterministic near-duplicate detection for generated flashcards.

Uses stdlib difflib (no embeddings, no model call) so it is cheap, fully
reproducible and independently testable. Compares a candidate question
against existing questions in the same deck.
"""
from difflib import SequenceMatcher


def _normalize(s: str) -> str:
    return " ".join(s.lower().split())


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def find_duplicate(candidate_question: str, existing_questions: list[str], threshold: float = 0.85) -> str | None:
    """Return the first existing question judged a near-duplicate of the
    candidate, or None if the candidate looks sufficiently novel."""
    for existing in existing_questions:
        if similarity(candidate_question, existing) >= threshold:
            return existing
    return None
