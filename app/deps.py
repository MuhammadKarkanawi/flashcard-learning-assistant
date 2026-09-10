"""Shared FastAPI dependencies."""
from typing import Iterator

from sqlmodel import Session

from app.db import engine


def get_db_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
