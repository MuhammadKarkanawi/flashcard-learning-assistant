from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.deps import get_db_session
from app.models import Deck
from app.schemas import DeckCreate, DeckRead

router = APIRouter(prefix="/decks", tags=["decks"])


@router.post("", response_model=DeckRead, status_code=201)
def create_deck(payload: DeckCreate, session: Session = Depends(get_db_session)):
    deck = Deck(name=payload.name, description=payload.description)
    session.add(deck)
    session.commit()
    session.refresh(deck)
    return DeckRead(id=deck.id, name=deck.name, description=deck.description)


@router.get("", response_model=list[DeckRead])
def list_decks(session: Session = Depends(get_db_session)):
    decks = session.exec(select(Deck)).all()
    return [DeckRead(id=d.id, name=d.name, description=d.description) for d in decks]


@router.get("/{deck_id}", response_model=DeckRead)
def get_deck(deck_id: int, session: Session = Depends(get_db_session)):
    deck = session.get(Deck, deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail="deck not found")
    return DeckRead(id=deck.id, name=deck.name, description=deck.description)
