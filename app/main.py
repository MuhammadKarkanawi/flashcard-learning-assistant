"""FastAPI application entrypoint.

Service responsibility: manage flashcard decks generated (with human review)
from uploaded study material, and run SM-2 spaced-repetition learning
sessions for them.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.ai.client import LocalLLMClient
from app.api import cards, decks, health, sources
from app.config import get_settings
from app.db import init_db
from app.web.routes import router as web_router

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    settings = get_settings()
    app.state.llm_client = LocalLLMClient(settings)
    app.state.settings = settings
    yield
    app.state.llm_client.close()


app = FastAPI(
    title="AISE Flashcard Learning Assistant",
    description=(
        "Generates spaced-repetition flashcards from uploaded study material "
        "using a locally hosted LLM, with human review and SM-2 scheduling."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(decks.router)
app.include_router(sources.router)
app.include_router(cards.router)
app.include_router(web_router)

app.mount("/static", StaticFiles(directory="app/web/static"), name="static")
