# Architecture & Data Flow

## Responsibility

A single, independently deployable service: *"Generates and schedules
spaced-repetition flashcards from a student's own uploaded study material,
using a locally hosted LLM to draft candidate cards that the student
reviews before they enter the learning queue."*

## Component overview

```
                         ┌─────────────────────────────────────────┐
                         │              Flashcard Service           │
                         │                                          │
  Browser  ───HTTP───▶   │  Web UI (Jinja2, server-rendered)         │
 (own UI)                │        │  calls same functions as ↓      │
                         │        ▼                                 │
                         │  REST API (FastAPI, OpenAPI at /docs)     │
                         │        │                                 │
                         │  ┌─────┴──────────────────────────────┐  │
                         │  │ Application logic (non-AI)          │  │
                         │  │  - chunking (app/core/chunking.py)  │  │
                         │  │  - dedupe   (app/core/dedupe.py)    │  │
                         │  │  - SM-2 scheduler (app/core/        │  │
                         │  │    scheduler.py)                    │  │
                         │  └─────┬────────────────────┬─────────┘  │
                         │        │                    │            │
                         │        ▼                    ▼            │
                         │  ┌──────────┐      ┌───────────────────┐ │
                         │  │ SQLite   │      │ AI component      │ │
                         │  │ (own DB) │      │ app/ai/client.py   │─┼──▶ Local, OpenAI-
                         │  └──────────┘      │ app/ai/generation  │ │   compatible
                         │                    │ .py                │ │   inference server
                         │                    └───────────────────┘ │   (Ollama / llama.cpp
                         │                                          │    / LM Studio),
                         │  GET /health  (status endpoint)           │    e.g. Gemma 3n E4B
                         └─────────────────────────────────────────┘
```

There is only one service in this project (per the "one coherent vertical
slice" scope rule); the diagram's boxes are internal modules, not separate
deployable services. The **only** external dependency is the local
inference server, reached exclusively through the OpenAI-compatible
`/chat/completions` contract in `app/ai/client.py` — swapping Ollama for
llama.cpp server or LM Studio requires changing `MODEL_BASE_URL`/`MODEL_NAME`
only, never application code.

## Data flow: from upload to a scheduled review

1. **Upload** (`POST /decks/{id}/sources`): a PDF/text file is parsed
   (`pypdf` for PDFs) into raw text and stored as a `SourceDocument` row.
2. **Chunking** (`app/core/chunking.py`, pure/deterministic): the raw text
   is greedily packed into paragraph-aware chunks bounded by
   `CHUNK_MAX_CHARS`, stored as `Chunk` rows. No model call happens here.
3. **Generation** (`POST /decks/{id}/sources/{source_id}/generate`): for
   each `Chunk`, `app/ai/generation.py` builds a strict prompt (see
   `app/ai/prompts.py`), calls the local model via `LocalLLMClient`, then:
   - parses the response as JSON and validates it against the
     `GeneratedCardsResponse` Pydantic schema (rejects malformed output);
   - checks each candidate question against existing questions in the deck
     using `app/core/dedupe.py` (rejects near-duplicates);
   - persists survivors as `Flashcard` rows with `status=candidate`,
     `origin=ai_generated`, and the grounding `source_excerpt` retained for
     transparency.
4. **Human review** (web UI "candidates" section, or
   `POST /cards/{id}/review-decision`): each candidate is accepted,
   rejected, or accepted-with-edits. Only accepted cards become eligible for
   study. This is the mandatory human-in-the-loop gate before AI output is
   ever presented as a trusted flashcard.
5. **Study session** (`GET /decks/{id}/due`, web UI `/decks/{id}/study`):
   accepted cards whose `due_at` has passed are served for review.
6. **Grading** (`POST /cards/{id}/answer`): a 0-5 recall-quality grade is
   passed through the pure `app/core/scheduler.py` SM-2 implementation,
   which updates `easiness_factor`, `interval_days`, `repetitions`, and
   `due_at`; a `ReviewEvent` audit row is written alongside the mutated
   `Flashcard`.

## Persistence

Single SQLite database (file path configurable via `DATABASE_URL`), owned
exclusively by this service — no other component reads or writes it
directly. Tables: `deck`, `sourcedocument`, `chunk`, `flashcard`,
`revieweevent` (see `app/models.py`).

## Failure handling boundary

All interaction with the local model is funnelled through
`app/ai/client.py`, which converts every failure mode into one of three
typed exceptions (`InferenceUnavailableError`, `InferenceTimeoutError`,
`InvalidModelOutputError`). `app/ai/generation.py` catches all three per
chunk, so one bad/unreachable inference call degrades a single chunk's
result (recorded as an `error` string) rather than failing the whole
generation request or crashing the API.

## Configuration surface

Everything environment-specific is externally configurable (see
`app/config.py` / `.env.example`): database location, inference server URL
and model name, timeout/retry counts, and the generation/dedupe tuning
parameters (`MAX_CARDS_PER_CHUNK`, `CHUNK_MAX_CHARS`,
`DUPLICATE_SIMILARITY_THRESHOLD`).
