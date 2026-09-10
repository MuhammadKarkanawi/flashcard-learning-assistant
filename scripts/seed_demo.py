"""Seed a small, reproducible demo deck.

Run against a fresh database (see README) to get a deck with one uploaded
source (already chunked) and one pre-accepted manual flashcard, so a grader
can immediately try the study session, and separately click "Generate" on
the source to see the live AI pipeline against their own local model.

Usage:
    python -m scripts.seed_demo
"""
from app.core.chunking import chunk_text
from app.db import init_db, engine
from app.models import CardOrigin, CardStatus, Chunk, Deck, Flashcard, SourceDocument
from sqlmodel import Session

DEMO_TEXT = (
    "Mitochondria are membrane-bound organelles found in most eukaryotic cells. "
    "They generate most of the cell's supply of adenosine triphosphate (ATP), used "
    "as a source of chemical energy.\n\n"
    "The process by which mitochondria produce ATP is called oxidative "
    "phosphorylation. It relies on an electron transport chain embedded in the "
    "mitochondrion's inner membrane.\n\n"
    "Mitochondria contain their own small circular DNA genome, separate from the "
    "cell's nuclear DNA, which is evidence for their evolutionary origin as free-"
    "living bacteria that were engulfed by an ancestral eukaryotic cell."
)


def seed() -> None:
    init_db()
    with Session(engine) as session:
        deck = Deck(name="Cell Biology Demo", description="Reproducible demo deck for grading/demonstration")
        session.add(deck)
        session.commit()
        session.refresh(deck)

        source = SourceDocument(
            deck_id=deck.id,
            filename="mitochondria-demo.txt",
            content_type="text/plain",
            raw_text=DEMO_TEXT,
        )
        session.add(source)
        session.commit()
        session.refresh(source)

        chunks = chunk_text(DEMO_TEXT, max_chars=1200)
        for c in chunks:
            session.add(Chunk(source_id=source.id, index=c.index, text=c.text))
        session.commit()

        manual_card = Flashcard(
            deck_id=deck.id,
            question="What is the primary role of mitochondria in a eukaryotic cell?",
            answer="Producing most of the cell's ATP (chemical energy) via oxidative phosphorylation.",
            status=CardStatus.accepted,
            origin=CardOrigin.manual,
        )
        session.add(manual_card)
        session.commit()

        print(f"Seeded deck id={deck.id} ('{deck.name}') with source id={source.id} "
              f"({len(chunks)} chunks) and 1 pre-accepted manual card.")
        print(f"Open http://localhost:8000/decks/{deck.id} to try it, "
              f"or http://localhost:8000/decks/{deck.id}/study to study the seeded card.")


if __name__ == "__main__":
    seed()
