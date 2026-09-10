from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.scheduler import SchedulerState, review
from app.deps import get_db_session
from app.models import CardOrigin, CardStatus, Flashcard, ReviewEvent
from app.schemas import FlashcardRead, ManualCardCreate, ReviewDecision, StudyAnswer

router = APIRouter(tags=["cards"])


def _to_read(card: Flashcard) -> FlashcardRead:
    return FlashcardRead(
        id=card.id,
        deck_id=card.deck_id,
        question=card.question,
        answer=card.answer,
        status=card.status.value if hasattr(card.status, "value") else card.status,
        origin=card.origin.value if hasattr(card.origin, "value") else card.origin,
        source_excerpt=card.source_excerpt,
        due_at=card.due_at.isoformat(),
        repetitions=card.repetitions,
    )


@router.get("/decks/{deck_id}/cards", response_model=list[FlashcardRead])
def list_cards(deck_id: int, status: str | None = None, session: Session = Depends(get_db_session)):
    stmt = select(Flashcard).where(Flashcard.deck_id == deck_id)
    if status:
        stmt = stmt.where(Flashcard.status == status)
    cards = session.exec(stmt).all()
    return [_to_read(c) for c in cards]


@router.get("/decks/{deck_id}/due", response_model=list[FlashcardRead])
def list_due_cards(deck_id: int, session: Session = Depends(get_db_session)):
    now = datetime.now(timezone.utc)
    stmt = (
        select(Flashcard)
        .where(Flashcard.deck_id == deck_id)
        .where(Flashcard.status == CardStatus.accepted)
        .where(Flashcard.due_at <= now)
        .order_by(Flashcard.due_at)
    )
    cards = session.exec(stmt).all()
    return [_to_read(c) for c in cards]


@router.post("/cards/{card_id}/review-decision", response_model=FlashcardRead)
def decide_candidate(card_id: int, decision: ReviewDecision, session: Session = Depends(get_db_session)):
    card = session.get(Flashcard, card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="card not found")
    if card.status != CardStatus.candidate:
        raise HTTPException(status_code=409, detail=f"card is not a pending candidate (status={card.status})")

    if decision.action == "accept":
        card.status = CardStatus.accepted
    elif decision.action == "reject":
        card.status = CardStatus.rejected
    elif decision.action == "edit":
        if decision.question:
            card.question = decision.question
        if decision.answer:
            card.answer = decision.answer
        card.status = CardStatus.accepted

    card.updated_at = datetime.now(timezone.utc)
    session.add(card)
    session.commit()
    session.refresh(card)
    return _to_read(card)


@router.post("/decks/{deck_id}/cards", response_model=FlashcardRead, status_code=201)
def create_manual_card(deck_id: int, payload: ManualCardCreate, session: Session = Depends(get_db_session)):
    card = Flashcard(
        deck_id=deck_id,
        question=payload.question,
        answer=payload.answer,
        status=CardStatus.manual,
        origin=CardOrigin.manual,
    )
    session.add(card)
    session.commit()
    session.refresh(card)
    return _to_read(card)


@router.post("/cards/{card_id}/answer", response_model=FlashcardRead)
def answer_card(card_id: int, answer: StudyAnswer, session: Session = Depends(get_db_session)):
    card = session.get(Flashcard, card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="card not found")
    if card.status not in (CardStatus.accepted, CardStatus.manual):
        raise HTTPException(status_code=409, detail="only accepted/manual cards can be studied")

    state = SchedulerState(
        easiness_factor=card.easiness_factor,
        interval_days=card.interval_days,
        repetitions=card.repetitions,
    )
    result = review(state, answer.grade)

    event = ReviewEvent(
        card_id=card.id,
        grade=answer.grade,
        previous_interval_days=state.interval_days,
        new_interval_days=result.state.interval_days,
        previous_easiness_factor=state.easiness_factor,
        new_easiness_factor=result.state.easiness_factor,
    )
    session.add(event)

    card.easiness_factor = result.state.easiness_factor
    card.interval_days = result.state.interval_days
    card.repetitions = result.state.repetitions
    card.due_at = result.due_at
    card.last_reviewed_at = datetime.now(timezone.utc)
    card.updated_at = card.last_reviewed_at
    session.add(card)
    session.commit()
    session.refresh(card)
    return _to_read(card)
