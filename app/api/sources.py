import io
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pypdf import PdfReader
from sqlmodel import Session, select

from app.ai.generation import generate_cards_for_chunk
from app.config import get_settings
from app.core.chunking import chunk_text
from app.deps import get_db_session
from app.models import CardOrigin, CardStatus, Chunk, Deck, Flashcard, SourceDocument
from app.schemas import GenerateResponse, GenerationOutcome as GenerationOutcomeSchema, SourceUploadResult

logger = logging.getLogger("aise.api.sources")

router = APIRouter(prefix="/decks/{deck_id}/sources", tags=["sources"])


def _extract_text(filename: str, content_type: str, raw_bytes: bytes) -> str:
    if filename.lower().endswith(".pdf") or "pdf" in content_type:
        try:
            reader = PdfReader(io.BytesIO(raw_bytes))
            return "\n\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"could not parse PDF: {exc}") from exc
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail=f"unsupported/undecodable file: {exc}") from exc


@router.post("", response_model=SourceUploadResult, status_code=201)
async def upload_source(deck_id: int, file: UploadFile, session: Session = Depends(get_db_session)):
    deck = session.get(Deck, deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail="deck not found")

    settings = get_settings()
    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=422, detail="uploaded file is empty")

    text = _extract_text(file.filename or "upload.txt", file.content_type or "", raw_bytes)
    if not text.strip():
        raise HTTPException(status_code=422, detail="no extractable text content found in file")

    source = SourceDocument(
        deck_id=deck_id,
        filename=file.filename or "upload.txt",
        content_type=file.content_type or "text/plain",
        raw_text=text,
    )
    session.add(source)
    session.commit()
    session.refresh(source)

    chunks = chunk_text(text, max_chars=settings.chunk_max_chars)
    for c in chunks:
        session.add(Chunk(source_id=source.id, index=c.index, text=c.text))
    session.commit()

    return SourceUploadResult(source_id=source.id, filename=source.filename, chunk_count=len(chunks))


@router.post("/{source_id}/generate", response_model=GenerateResponse)
def generate_from_source(deck_id: int, source_id: int, request: Request, session: Session = Depends(get_db_session)):
    deck = session.get(Deck, deck_id)
    if deck is None:
        raise HTTPException(status_code=404, detail="deck not found")
    source = session.get(SourceDocument, source_id)
    if source is None or source.deck_id != deck_id:
        raise HTTPException(status_code=404, detail="source not found in this deck")

    settings = get_settings()
    client = request.app.state.llm_client

    chunks = session.exec(select(Chunk).where(Chunk.source_id == source_id).order_by(Chunk.index)).all()
    if not chunks:
        raise HTTPException(status_code=422, detail="source has no chunks; nothing to generate from")

    existing_questions = [
        c.question for c in session.exec(select(Flashcard).where(Flashcard.deck_id == deck_id)).all()
    ]

    outcomes: list[GenerationOutcomeSchema] = []
    total_created = 0
    for chunk in chunks:
        outcome = generate_cards_for_chunk(
            client,
            chunk.index,
            chunk.text,
            existing_questions,
            max_cards=settings.max_cards_per_chunk,
            duplicate_threshold=settings.duplicate_similarity_threshold,
        )
        for card in outcome.accepted:
            fc = Flashcard(
                deck_id=deck_id,
                chunk_id=chunk.id,
                question=card.question,
                answer=card.answer,
                source_excerpt=chunk.text[:400],
                status=CardStatus.candidate,
                origin=CardOrigin.ai_generated,
            )
            session.add(fc)
            existing_questions.append(card.question)
            total_created += 1

        outcomes.append(
            GenerationOutcomeSchema(
                chunk_index=outcome.chunk_index,
                accepted_candidates=len(outcome.accepted),
                rejected_duplicates=outcome.rejected_duplicates,
                rejected_invalid=outcome.rejected_invalid,
                error=outcome.error,
            )
        )

    session.commit()
    return GenerateResponse(source_id=source_id, outcomes=outcomes, total_candidates_created=total_created)
