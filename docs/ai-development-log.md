# AI Development Log

Agent harness used: **Claude (Cowork / Claude Agent SDK)**, operating through
the desktop app's remote-device bridge. Sandboxing model: the agent's shell
(`device_bash`) runs inside an isolated, ephemeral per-session Linux VM; the
only part of the real filesystem exposed to it is the single folder the user
explicitly granted (`~/PycharmProjects`, requested and approved once at the
start of the session). No other folders, credentials, or files on the host
were reachable. The VM has no delete permission on mounted files by default
(a separate, explicit user approval is required to enable `rm`), and network
egress inside that VM follows the session's own policy, separate from the
host machine's network. Destructive git operations were never used.

Below are representative episodes from building this project, in
chronological order. Two are deliberately included because something went
wrong first (see "Rejected candidate: query-param bug" and "Modified: eval
scoring bug"), per the requirement to document at least one unsuccessful or
unsuitable agent contribution.

---

## Episode 1 — Project scaffold and configuration

**Task given:** Set up the initial project layout (FastAPI package structure,
`requirements.txt`, `.gitignore`, `.env.example`) for a Python/FastAPI service.

**Proposed contribution:** Full directory tree plus dependency pins and a
`pydantic-settings`-based `Settings` class reading all AI/DB configuration
from environment variables.

**Permissions/tools used:** `device_bash` inside `~/PycharmProjects` only.

**Verification:** `python3 -c "import ast; ast.parse(...)"` syntax checks on
every generated file; directory listing to confirm structure.

**Outcome:** Accepted as-is.

**Observed:** Fast for boilerplate; no risk since no logic was involved yet.

---

## Episode 2 — SM-2 scheduler (core deterministic logic)

**Task given:** Implement the SM-2 spaced-repetition algorithm as a pure,
side-effect-free function, independent of the database and the AI component.

**Proposed contribution:** `app/core/scheduler.py` plus 7 unit tests covering
first/second/third review, failed recall, easiness-factor floor, due-date
computation, and invalid-grade rejection.

**Permissions/tools used:** `device_bash`; installed `pytest` via `pip
install --user` inside the sandboxed VM (not on the real host).

**Verification:** `pytest` run inside the sandbox — all 7 passed on first try.

**Outcome:** Accepted as-is.

**Observed benefit:** Because the scheduler is pure and has no AI dependency,
it was trivial to fully unit test without any model access — this is exactly
the kind of "deterministic core logic" the project brief asks to keep
separate from the AI component.

---

## Episode 3 — LLM client and generation pipeline, with a self-corrected test

**Task given:** Build the local-model client (OpenAI-compatible HTTP calls)
and the generation pipeline that turns raw model output into validated,
deduplicated flashcard candidates, with typed error handling for
unavailable/timeout/malformed-output cases.

**Proposed contribution:** `app/ai/client.py`, `app/ai/generation.py`, and a
test suite including one test, `test_more_cards_than_max_are_truncated`, that
generated 5 near-identical placeholder questions ("Question number 0/1/2...
is here?") to check truncation to `max_cards`.

**Verification:** Running the suite immediately failed that one test: the
near-duplicate detector correctly flagged the placeholder questions as
duplicates of each other (they differ by a single digit), so only 1 of the
2 truncated cards survived instead of the 2 expected — a bug in the *test*,
not the dedupe logic.

**What was accepted/modified/rejected:** The test was rejected and rewritten
with five genuinely distinct topics; the dedupe/generation code itself was
kept unchanged, since it had behaved correctly.

**Observed risk:** A quick, semantically-lazy test fixture can silently
encode a wrong assumption. Catching this required actually reading the
failure output rather than assuming a red test meant the *implementation*
was wrong.

---

## Episode 4 — Rejected/corrected: query-parameter bug in the manual-card endpoint

**Task given:** Add an endpoint to manually create a flashcard (not
AI-generated).

**Proposed contribution (first attempt):** `def create_manual_card(deck_id:
int, question: str, answer: str, ...)` — passing `question`/`answer` as
plain `str` function parameters.

**Why this was unsuitable:** In FastAPI, plain scalar parameters without a
Pydantic body model or `Body(...)` annotation are interpreted as **query
parameters**, not JSON body fields. A client POSTing `{"question": "...",
"answer": "..."}` as JSON would have gotten a 422 error, and the route would
only have worked with `?question=...&answer=...` in the URL — wrong and
easy to miss until integration-tested.

**Detection:** Caught before it was ever exercised, while re-reading the
route signature against how the rest of the API passes structured input
(everything else uses typed Pydantic request models).

**Correction:** Introduced `ManualCardCreate` in `app/schemas.py` and changed
the route to accept it as a JSON body, matching every other POST endpoint.
Confirmed via `tests/test_api.py::test_manual_card_creation_and_answer`.

**Outcome:** Modified before acceptance; the corrected version is what
shipped.

---

## Episode 5 — API/UI integration, and a sandbox-specific storage bug

**Task given:** Wire up the REST API and a server-rendered web UI reusing the
same domain functions, then verify end-to-end with `pytest` and a live
`uvicorn` smoke test.

**Proposed contribution:** `app/main.py`, `app/api/*.py`, `app/web/*`.

**Verification:** Full `pytest` run failed with `sqlite3.OperationalError:
disk I/O error` during table creation — but only during the live-server
smoke test, not the (in-memory) unit tests.

**Diagnosis:** The default `DATABASE_URL` pointed at a relative
`./data/flashcards.db` path, which — only inside this sandbox — resolves
onto the mounted, cross-VM project folder. SQLite's file locking does not
work reliably on that kind of mount, which is a known class of issue for
SQLite over network/FUSE-style filesystems in general, not a bug in the
application itself.

**What was accepted/modified/rejected:** The application code was not
changed (a normal Docker container filesystem does not have this problem).
For local *development testing inside this sandbox only*, `DATABASE_URL`
was pointed at `/tmp` instead. This distinction is called out explicitly so
it doesn't get mistaken for a real defect in the shipped default.

**Observed risk:** An environment-specific quirk of the sandbox could easily
have been misdiagnosed as an application bug; tracing the actual SQL
statement in the traceback was necessary to tell them apart.

---

## Episode 6 — Modified: evaluation task-completion metric was misleading

**Task given:** Build the AI evaluation harness (`eval/run_eval.py`) with an
aggregated `task_completion_rate` metric.

**Proposed contribution (first version):** For non-"expect empty" cases,
`behaved_as_expected = accepted_count >= 1 OR error is not None` — i.e. an
inference failure counted the same as a genuine success.

**Why this was unsuitable:** Running the harness against a deliberately
unreachable model endpoint produced `task_completion_rate: 1.0` even though
*every single case* failed with a connection error — the metric would have
hidden total inference outages instead of surfacing them.

**Detection:** Noticed by inspecting the printed summary against the known
test condition (no reachable model) and finding the numbers didn't match
reality.

**Correction:** Any case with a non-null `error` is now unconditionally
`behaved_as_expected = False`; `inference_error_rate` reports outages
separately so the two failure modes (infrastructure vs. wrong output)
can't mask each other. Re-ran: `task_completion_rate` correctly dropped to
`0.0` under the same unreachable-endpoint condition.

**Outcome:** Modified before being considered part of the deliverable.

---

## Episode 7 — Containerisation: proposed but not independently verified

**Task given:** Add a `Dockerfile` and `docker-compose.yml`, with the app
container reaching a host-run Ollama instance via `host.docker.internal`.

**Proposed contribution:** Standard multi-stage-free Python slim image,
healthcheck hitting `/health`, and a compose file with all settings
configurable via environment variables.

**Permissions/tools used:** `device_bash` only — this sandbox's Linux VM has
no `docker` binary and cannot run one (nested containers are out of scope
for the sandbox), so `docker build`/`docker compose up` could not be
executed here.

**Verification performed:** Static review only (Dockerfile syntax, that
`COPY`/`WORKDIR` paths match the actual project layout, that `EXPOSE`/port
mapping matches `uvicorn`'s bind address). **Not** verified: an actual image
build or container run.

**Outcome:** Accepted provisionally, flagged as needing the user's own
verification (`docker compose up --build`) on their real machine before the
project is considered done — this is explicitly called out in the README's
"Known limitations" section rather than silently assumed to work.
