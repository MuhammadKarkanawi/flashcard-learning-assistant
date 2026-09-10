"""Deterministic, rule-based flashcard baseline (no model call at all).

Used as the "AI vs. deterministic baseline" comparison required by the
evaluation. Produces simple cloze-deletion cards by blanking out a salient
token (a number or a capitalized multi-word term) in a sentence. This is
intentionally mechanical: it never invents content, but it also cannot ask
genuinely conceptual questions the way the LLM-based pipeline can.
"""
import re
from dataclasses import dataclass


@dataclass
class BaselineCard:
    question: str
    answer: str


_NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)?\b")
_PROPER_NOUN_RE = re.compile(r"\b[A-Z][a-zA-Z]{3,}\b")


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]


def _pick_blank(sentence: str) -> tuple[str, str] | None:
    """Return (blank_target, replaced_sentence) or None if nothing salient found."""
    numbers = _NUMBER_RE.findall(sentence)
    if numbers:
        target = max(numbers, key=len)
        return target, sentence.replace(target, "____", 1)

    proper_nouns = [w for w in _PROPER_NOUN_RE.findall(sentence) if w.lower() not in {"the", "this", "that"}]
    if proper_nouns:
        target = max(proper_nouns, key=len)
        return target, sentence.replace(target, "____", 1)

    return None


def generate_baseline_cards(text: str, max_cards: int = 3) -> list[BaselineCard]:
    cards: list[BaselineCard] = []
    for sentence in _split_sentences(text):
        if len(cards) >= max_cards:
            break
        picked = _pick_blank(sentence)
        if picked is None:
            continue
        target, blanked = picked
        cards.append(BaselineCard(question=f"Fill in the blank: {blanked}", answer=target))
    return cards
