"""Pydantic schemas: API I/O and validated structured LLM output.

Keeping the AI-facing schema separate from the persistence model (app.models)
lets us validate untrusted model output strictly before it ever becomes a
Flashcard row.
"""
from pydantic import BaseModel, Field, field_validator


class GeneratedCard(BaseModel):
    """One flashcard candidate as produced by the model. Strict validation:
    this is the boundary between untrusted model output and the application.
    """

    question: str = Field(min_length=8, max_length=500)
    answer: str = Field(min_length=1, max_length=1000)

    @field_validator("question", "answer")
    @classmethod
    def not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class GeneratedCardsResponse(BaseModel):
    cards: list[GeneratedCard] = Field(default_factory=list)


# ---- API request/response schemas ----


class DeckCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""


class DeckRead(BaseModel):
    id: int
    name: str
    description: str


class SourceUploadResult(BaseModel):
    source_id: int
    filename: str
    chunk_count: int


class GenerateRequest(BaseModel):
    source_id: int


class GenerationOutcome(BaseModel):
    chunk_index: int
    accepted_candidates: int
    rejected_duplicates: int
    rejected_invalid: int
    error: str | None = None


class GenerateResponse(BaseModel):
    source_id: int
    outcomes: list[GenerationOutcome]
    total_candidates_created: int


class FlashcardRead(BaseModel):
    id: int
    deck_id: int
    question: str
    answer: str
    status: str
    origin: str
    source_excerpt: str
    due_at: str
    repetitions: int


class ReviewDecision(BaseModel):
    action: str = Field(pattern="^(accept|reject|edit)$")
    question: str | None = None
    answer: str | None = None


class StudyAnswer(BaseModel):
    grade: int = Field(ge=0, le=5)


class ManualCardCreate(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    answer: str = Field(min_length=1, max_length=1000)
