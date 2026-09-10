from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlmodel import Session

from app.deps import get_db_session

router = APIRouter(tags=["health"])


@router.get("/health")
def health(session: Session = Depends(get_db_session)):
    try:
        session.exec(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:  # pragma: no cover - defensive
        db_status = f"error: {exc}"
    return {"status": "ok" if db_status == "ok" else "degraded", "database": db_status}
