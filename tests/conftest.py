import json
from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.deps import get_db_session
from app.main import app


@dataclass
class ScriptedFakeClient:
    """Fake LLM client for API-level tests: returns one scripted JSON payload
    per call, in order, so tests don't depend on a real inference server."""

    responses: list[str] = field(default_factory=list)
    calls: list[tuple[str, str]] = field(default_factory=list)

    def chat(self, system_prompt, user_prompt, json_mode=True):
        from app.ai.client import ChatResult

        self.calls.append((system_prompt, user_prompt))
        idx = min(len(self.calls) - 1, len(self.responses) - 1)
        return ChatResult(content=self.responses[idx], latency_seconds=0.01)

    def close(self):
        pass

    @staticmethod
    def cards_response(cards):
        return json.dumps({"cards": cards})


@pytest.fixture()
def test_engine():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture()
def client(test_engine):
    def override_get_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def fake_llm(client):
    fake = ScriptedFakeClient(responses=[ScriptedFakeClient.cards_response([])])
    client.app.state.llm_client = fake
    return fake
