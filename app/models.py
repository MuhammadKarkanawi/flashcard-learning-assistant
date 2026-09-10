"""Persistent domain model.

Responsibility of this service: manage decks of flashcards generated (with
review) from uploaded source material, and schedule spaced-repetition
learning sessions for them.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CardStatus(str, Enum):
    candidate = "candidate"   # proposed by the AI component, not yet reviewed
    accepted = "accepted"     # reviewed and accepted into the active deck
    rejected = "rejected"     # reviewed and rejected, kept for audit/history
    manual = "manual"         # created directly by the user, no AI involved


class CardOrigin(str, Enum):
    ai_generated = "ai_generated"
    manual = "manual"
    baseline_rule = "baseline_rule"  # used by the evaluation baseline generator


class Deck(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class SourceDocument(SQLModel, table=True):
    """A document (e.g. lecture PDF) uploaded as learning material for a deck."""

    id: Optional[int] = Field(default=None, primary_key=True)
    deck_id: int = Field(foreign_key="deck.id", index=True)
    filename: str
    content_type: str = "text/plain"
    raw_text: str
    created_at: datetime = Field(default_factory=utcnow)


class Chunk(SQLModel, table=True):
    """A deterministic, size-bounded slice of a SourceDocument used as the
    grounding excerpt for one generation request."""

    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="sourcedocument.id", index=True)
    index: int
    text: str


class Flashcard(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    deck_id: int = Field(foreign_key="deck.id", index=True)
    chunk_id: Optional[int] = Field(default=None, foreign_key="chunk.id")

    question: str
    answer: str
    source_excerpt: str = ""  # for transparency: what the AI grounded this card in

    status: CardStatus = Field(default=CardStatus.candidate, index=True)
    origin: CardOrigin = Field(default=CardOrigin.manual)

    # SM-2 spaced-repetition scheduler state
    easiness_factor: float = 2.5
    interval_days: int = 0
    repetitions: int = 0
    due_at: datetime = Field(default_factory=utcnow, index=True)
    last_reviewed_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ReviewEvent(SQLModel, table=True):
    """Audit trail of study-session answers, independent of current card state."""

    id: Optional[int] = Field(default=None, primary_key=True)
    card_id: int = Field(foreign_key="flashcard.id", index=True)
    grade: int  # 0-5, SM-2 quality of recall
    previous_interval_days: int
    new_interval_days: int
    previous_easiness_factor: float
    new_easiness_factor: float
    reviewed_at: datetime = Field(default_factory=utcnow)
