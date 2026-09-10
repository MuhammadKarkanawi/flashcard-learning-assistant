"""Server-rendered web UI.

Thin layer over the same domain functions used by the JSON API (see
app/api/*.py) so the UI and the API never diverge in behaviour. This is the
service's "own usable interface" required by the project spec: the full
core scenario (upload -> generate -> review -> study) can be completed here
without any external client.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, UploadFile, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.api import cards as cards_api
from app.api import decks as decks_api
from app.api import sources as sources_api
from app.deps import get_db_session
from app.models import CardStatus, Deck, Flashcard, SourceDocument
from app.schemas import DeckCreate, ReviewDecision, StudyAnswer

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory="app/web/templates")


@router.get("/", response_class=HTMLResponse)
def home(request: Request, session: Session = Depends(get_db_session)):
    decks = session.exec(select(Deck)).all()
    return templates.TemplateResponse(request, "decks.html", {"decks": decks})


@router.post("/decks", response_class=HTMLResponse)
def create_deck_form(name: str = Form(...), description: str = Form(""), session: Session = Depends(get_db_session)):
    deck = decks_api.create_deck(DeckCreate(name=name, description=description), session=session)
    return RedirectResponse(url=f"/decks/{deck.id}", status_code=303)


@router.get("/decks/{deck_id}", response_class=HTMLResponse)
def deck_detail(deck_id: int, request: Request, session: Session = Depends(get_db_session)):
    deck = session.get(Deck, deck_id)
    sources = session.exec(select(SourceDocument).where(SourceDocument.deck_id == deck_id)).all()
    candidates = session.exec(
        select(Flashcard).where(Flashcard.deck_id == deck_id).where(Flashcard.status == CardStatus.candidate)
    ).all()
    accepted = session.exec(
        select(Flashcard)
        .where(Flashcard.deck_id == deck_id)
        .where(Flashcard.status.in_([CardStatus.accepted, CardStatus.manual]))
    ).all()
    due_count = len(
        [c for c in accepted if c.due_at <= datetime.now(timezone.utc)]
    )
    return templates.TemplateResponse(
        request,
        "deck.html",
        {
            "deck": deck,
            "sources": sources,
            "candidates": candidates,
            "accepted": accepted,
            "due_count": due_count,
        },
    )


@router.post("/decks/{deck_id}/sources/upload")
async def upload_source_form(deck_id: int, file: UploadFile, session: Session = Depends(get_db_session)):
    await sources_api.upload_source(deck_id, file, session=session)
    return RedirectResponse(url=f"/decks/{deck_id}", status_code=303)


@router.post("/decks/{deck_id}/sources/{source_id}/generate")
def generate_form(deck_id: int, source_id: int, request: Request, session: Session = Depends(get_db_session)):
    sources_api.generate_from_source(deck_id, source_id, request, session=session)
    return RedirectResponse(url=f"/decks/{deck_id}", status_code=303)


@router.post("/cards/{card_id}/decision")
def decision_form(
    card_id: int,
    deck_id: int = Form(...),
    action: str = Form(...),
    question: str = Form(None),
    answer: str = Form(None),
    session: Session = Depends(get_db_session),
):
    cards_api.decide_candidate(
        card_id, ReviewDecision(action=action, question=question or None, answer=answer or None), session=session
    )
    return RedirectResponse(url=f"/decks/{deck_id}", status_code=303)


@router.get("/decks/{deck_id}/study", response_class=HTMLResponse)
def study(deck_id: int, request: Request, session: Session = Depends(get_db_session)):
    deck = session.get(Deck, deck_id)
    due = cards_api.list_due_cards(deck_id, session=session)
    current = due[0] if due else None
    return templates.TemplateResponse(
        request, "study.html", {"deck": deck, "current": current, "remaining": len(due)}
    )


@router.post("/decks/{deck_id}/study/{card_id}/answer")
def study_answer(deck_id: int, card_id: int, grade: int = Form(...), session: Session = Depends(get_db_session)):
    cards_api.answer_card(card_id, StudyAnswer(grade=grade), session=session)
    return RedirectResponse(url=f"/decks/{deck_id}/study", status_code=303)
