# Flashcard Learning Assistant

A spaced-repetition flashcard app that turns your own study material (PDF or
text) into flashcards using a **locally hosted** LLM, with a mandatory human
review step before any AI-generated card enters your learning queue.

Built for the AISE project assignment: developed substantially with an AI
agent harness (see [`docs/ai-development-log.md`](docs/ai-development-log.md))
and integrates a meaningful, locally operated AI component (see below).

## 1. What this service does (in one sentence)

*"Generates and schedules spaced-repetition flashcards from a student's own
uploaded study material, using a locally hosted LLM to draft candidate cards
that the student reviews before they enter the learning queue."*

Non-AI application logic: deterministic text chunking, near-duplicate
detection, and a full SM-2 spaced-repetition scheduler — none of which call
the model. See [`docs/architecture.md`](docs/architecture.md) for the full
data-flow diagram.

## 2. Core user scenarios

1. Upload a PDF/text document into a deck → it is chunked automatically.
2. Click "Generate" on a source → the local LLM proposes flashcards grounded
   in that source; each is validated and deduplicated before being shown.
3. Review each AI-proposed candidate: accept, reject, or edit-and-accept.
4. Study due cards; grade your recall (0-5); the SM-2 scheduler reschedules
   the card automatically.

All four steps are reachable purely through this service's own web UI
(`http://localhost:8000/`) — no external client is required for the core
scenario.

## 3. Quickstart

### 3.1 Prerequisites (on your machine, not inside any sandbox)

- Docker (Desktop on macOS/Windows, or Docker Engine on Linux)
- A local, OpenAI-compatible inference server. Simplest option: **Ollama**.

```bash
# macOS: https://ollama.com/download, or:
brew install ollama
ollama serve &                 # starts the local server on :11434
ollama pull gemma3:4b         # ~small multimodal model, adjust to your hardware
```

Any OpenAI-compatible server works (llama.cpp server, LM Studio, ...) — just
point `MODEL_BASE_URL` at it (see Configuration below).

### 3.2 Run the service

```bash
docker compose up --build
```

Then open http://localhost:8000/ . The container reaches your host-run
Ollama via `host.docker.internal:11434` by default (already wired in
`docker-compose.yml`); override `MODEL_BASE_URL` if your server runs
elsewhere.

> **Verification note (transparency):** this container/compose setup was
> authored and statically reviewed inside an AI-agent sandbox that has no
> Docker daemon available to it (see
> [`docs/ai-development-log.md`](docs/ai-development-log.md), Episode 7), so
> `docker compose up --build` has not yet been executed end-to-end. Please
> run it once yourself before relying on it and file/fix anything that comes
> up — the Dockerfile and compose file are intentionally simple (single
> `python:3.11-slim` stage, standard `pip install -r requirements.txt`) to
> keep that risk low.

### 3.3 Seed a reproducible demo deck (optional)

```bash
docker compose exec flashcards python -m scripts.seed_demo
```

Creates one deck with an already-chunked source and one pre-accepted manual
card, so you can try the study session immediately, and click "Generate" on
the seeded source to see the live AI pipeline against your own model.

### 3.4 Run without Docker (local Python)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # edit MODEL_BASE_URL/MODEL_NAME if needed
uvicorn app.main:app --reload
```

## 4. Configuration

All settings are environment variables (see `.env.example`); nothing is
hard-coded. Key ones:

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | SQLite location | `sqlite:///./data/flashcards.db` |
| `MODEL_BASE_URL` | OpenAI-compatible base URL of your local inference server | `http://host.docker.internal:11434/v1` |
| `MODEL_NAME` | Model name/tag as known to that server | `gemma3:4b` |
| `MODEL_API_KEY` | Sent as a Bearer token; most local servers ignore it | `not-needed` |
| `MODEL_TIMEOUT_SECONDS` / `MODEL_MAX_RETRIES` | Inference call resilience | `30` / `1` |
| `MAX_CARDS_PER_CHUNK` | Cap on generated cards per source chunk | `3` |
| `CHUNK_MAX_CHARS` | Max characters per chunk fed to the model | `1200` |
| `DUPLICATE_SIMILARITY_THRESHOLD` | Near-duplicate rejection threshold (0-1) | `0.85` |

Swapping to a different compatible server or model requires **only**
changing `MODEL_BASE_URL`/`MODEL_NAME` — no code changes (see
`app/ai/client.py`).

## 5. AI agent harness & sandboxing used during development

This project was built with **Claude (Cowork / Claude Agent SDK)** as the AI
agent harness, operating through a sandboxed shell scoped to this project's
folder only (no access to the rest of the filesystem, no delete permission
by default, destructive git operations never used). Full details and
representative development episodes — including two that document a caught
and corrected mistake — are in
[`docs/ai-development-log.md`](docs/ai-development-log.md).

## 6. API documentation

Interactive OpenAPI docs: `GET /docs` (Swagger UI) or `GET /openapi.json`
once the service is running. Summary of endpoints:

| Method & path | Purpose |
|---|---|
| `GET /health` | Liveness/readiness, checks DB connectivity |
| `POST /decks` | Create a deck |
| `GET /decks`, `GET /decks/{id}` | List/read decks |
| `POST /decks/{id}/sources` | Upload a PDF/text source (multipart) → chunked |
| `POST /decks/{id}/sources/{source_id}/generate` | Run AI generation over a source's chunks |
| `GET /decks/{id}/cards?status=` | List cards (candidate/accepted/rejected/manual) |
| `POST /cards/{id}/review-decision` | Accept/reject/edit a candidate |
| `POST /decks/{id}/cards` | Create a manual (non-AI) card |
| `GET /decks/{id}/due` | List cards due for study now |
| `POST /cards/{id}/answer` | Submit a 0-5 recall grade, apply SM-2 |

Error responses use standard HTTP status codes (404 unknown deck/card/source,
409 invalid state transition e.g. re-accepting a non-candidate, 422 invalid
input e.g. empty upload, unsupported encoding, out-of-range grade).

## 7. Tests

```bash
pip install -r requirements-dev.txt
pytest
```

48 tests covering: the SM-2 scheduler (incl. invalid input), chunking,
duplicate detection, the LLM client's error handling (mocked HTTP transport
— unavailable/timeout/malformed/4xx/5xx), the generation pipeline (mocked
LLM — valid/malformed/duplicate/oversized/empty output), and full API/UI
integration flows with a scripted fake LLM client (no real model access
required for the test suite to pass).

## 8. AI evaluation

```bash
python -m eval.run_eval
```

Runs 12 representative cases (`eval/cases.json`) — including ambiguous,
out-of-scope, unsafe (prompt-injection), and malformed/OCR-garbage inputs —
through the real generation pipeline against your configured local model,
**and** through a deterministic rule-based cloze-generation baseline
(`eval/baseline.py`) for comparison. Writes `eval/results/report.json` and
`report.md` with aggregated metrics: task-completion rate, structured-output
validity rate, inference error rate, latency, duplicate/invalid rejection
counts, a safety-flag check for prompt-injection leakage, and an explicitly
uncalibrated groundedness proxy (lexical overlap — documented in the report
itself as a heuristic, never presented as a probability).

The committed `eval/results/` reflects a run against an intentionally
unreachable model endpoint (this sandbox has no local inference server) and
therefore shows 100% inference errors — this is the harness correctly
surfacing total unavailability rather than masking it. **Re-run the command
above yourself** once Ollama (or your chosen server) is up, and commit the
refreshed report before submission.

## 9. Known limitations

### Privacy, security, and misuse

- All uploaded study material and generated flashcards stay in the local
  SQLite database; the only outbound network call the AI component makes is
  to the locally configured inference server (no cloud/third-party AI API
  is used for the assessed functionality).
- AI-generated candidates are visibly labelled (`origin: ai_generated`) and
  are never shown to the learner as accepted knowledge before a human
  explicitly reviews them — this is the main safeguard against the model's
  lack of real reasoning/accountability being mistaken for verified content.
- Potential misuse: a user could upload copyrighted material they don't have
  rights to, or paste adversarial "prompt injection" text as if it were
  study content (evaluated explicitly in `eval/cases.json`, case
  `prompt-injection`) to try to manipulate the model's output. The
  application does not attempt content moderation of uploaded material
  beyond the structural validation already described; this is documented
  here rather than silently assumed away.
- No authentication (per the assignment's scope rule for a single local
  user) means anyone with network access to the running instance can read
  or modify all decks/cards; do not expose this service on an untrusted
  network without adding authentication first.


- Docker build/run has not been independently verified (no Docker daemon in
  the authoring sandbox) — verify with `docker compose up --build` yourself.
- Groundedness is measured with a lexical-overlap heuristic, not a
  calibrated confidence score or human/LLM judge.
- Single local user, no authentication (per the assignment's scope rule —
  auth is not central to this use case).
- PDF text extraction (`pypdf`) is text-layer based; scanned/image-only PDFs
  without an OCR text layer will fail extraction with a 422 error.
- The rule-based baseline is intentionally simplistic (cloze deletion on
  numbers/proper nouns) — it exists as a comparison point, not a competing
  feature.

## 10. Project layout

```
app/
  core/        deterministic logic: chunking, scheduler (SM-2), dedupe
  ai/          local-model client, prompts, generation pipeline
  api/         REST routes (decks, sources, cards, health)
  web/         server-rendered UI (Jinja2 templates + routes)
  models.py    persistence (SQLModel)
  schemas.py   API/AI I/O validation (Pydantic)
  config.py    environment-variable settings
tests/         pytest suite (unit + API integration, mocked LLM)
eval/          evaluation cases, rule-based baseline, harness, results
scripts/       seed_demo.py (reproducible example data)
docs/          architecture.md, ai-development-log.md
```
