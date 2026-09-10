"""Flashcard generation pipeline: prompt -> local LLM -> validated,
deduplicated flashcard candidates.

This module is the boundary between the non-deterministic AI component and
the rest of the application. Every failure mode is captured as a typed
GenerationOutcome rather than raising into the API layer, so a single bad
chunk cannot take down a whole generation request.
"""
import json
import logging
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.ai.client import InferenceError, LocalLLMClient
from app.ai.prompts import SYSTEM_PROMPT, build_user_prompt
from app.core.dedupe import find_duplicate
from app.schemas import GeneratedCard, GeneratedCardsResponse

logger = logging.getLogger("aise.ai.generation")


@dataclass
class GenerationOutcome:
    chunk_index: int
    accepted: list[GeneratedCard] = field(default_factory=list)
    rejected_duplicates: int = 0
    rejected_invalid: int = 0
    error: str | None = None
    latency_seconds: float | None = None


def generate_cards_for_chunk(
    client: LocalLLMClient,
    chunk_index: int,
    chunk_text: str,
    existing_questions: list[str],
    *,
    max_cards: int,
    duplicate_threshold: float,
) -> GenerationOutcome:
    outcome = GenerationOutcome(chunk_index=chunk_index)

    try:
        result = client.chat(SYSTEM_PROMPT, build_user_prompt(chunk_text, max_cards))
    except InferenceError as exc:
        outcome.error = f"{type(exc).__name__}: {exc}"
        return outcome

    outcome.latency_seconds = result.latency_seconds

    try:
        raw = json.loads(_strip_code_fences(result.content))
        parsed = GeneratedCardsResponse.model_validate(raw)
    except (json.JSONDecodeError, ValidationError) as exc:
        outcome.error = f"invalid model output: {exc}"
        outcome.rejected_invalid += 1
        return outcome

    known_questions = list(existing_questions)
    for card in parsed.cards[:max_cards]:
        duplicate = find_duplicate(card.question, known_questions, threshold=duplicate_threshold)
        if duplicate is not None:
            outcome.rejected_duplicates += 1
            continue
        outcome.accepted.append(card)
        known_questions.append(card.question)

    return outcome


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text
