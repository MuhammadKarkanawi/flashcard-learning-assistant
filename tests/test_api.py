import io

from tests.conftest import ScriptedFakeClient


def test_health_endpoint_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_create_and_list_deck(client):
    resp = client.post("/decks", json={"name": "Networking Basics", "description": "TCP/IP etc."})
    assert resp.status_code == 201
    deck_id = resp.json()["id"]

    resp = client.get("/decks")
    assert resp.status_code == 200
    assert any(d["id"] == deck_id for d in resp.json())


def test_get_unknown_deck_returns_404(client):
    resp = client.get("/decks/999999")
    assert resp.status_code == 404


def test_upload_empty_file_is_rejected(client):
    deck_id = client.post("/decks", json={"name": "D"}).json()["id"]
    resp = client.post(
        f"/decks/{deck_id}/sources",
        files={"file": ("empty.txt", io.BytesIO(b""), "text/plain")},
    )
    assert resp.status_code == 422


def test_generate_on_unknown_source_returns_404(client, fake_llm):
    deck_id = client.post("/decks", json={"name": "D"}).json()["id"]
    resp = client.post(f"/decks/{deck_id}/sources/999999/generate")
    assert resp.status_code == 404


def test_full_flow_upload_generate_review_study(client):
    # 1. create deck
    deck_id = client.post("/decks", json={"name": "Biology", "description": "Cell biology basics"}).json()["id"]

    # 2. upload a source document with enough content to yield one chunk
    text = ("Mitochondria are the powerhouse of the cell. " * 20).encode("utf-8")
    resp = client.post(
        f"/decks/{deck_id}/sources",
        files={"file": ("notes.txt", io.BytesIO(text), "text/plain")},
    )
    assert resp.status_code == 201
    source_id = resp.json()["source_id"]
    assert resp.json()["chunk_count"] >= 1

    # 3. script the fake LLM to return one valid flashcard for the (single) chunk
    fake = ScriptedFakeClient(
        responses=[ScriptedFakeClient.cards_response(
            [{"question": "What is the function of mitochondria?", "answer": "They produce energy (ATP) for the cell."}]
        )]
    )
    client.app.state.llm_client = fake

    resp = client.post(f"/decks/{deck_id}/sources/{source_id}/generate")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_candidates_created"] == 1

    # 4. the generated card is a candidate awaiting review
    candidates = client.get(f"/decks/{deck_id}/cards", params={"status": "candidate"}).json()
    assert len(candidates) == 1
    card_id = candidates[0]["id"]
    assert candidates[0]["origin"] == "ai_generated"

    # 5. accept it
    resp = client.post(f"/cards/{card_id}/review-decision", json={"action": "accept"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"

    # accepting twice should now fail: no longer a pending candidate
    resp = client.post(f"/cards/{card_id}/review-decision", json={"action": "accept"})
    assert resp.status_code == 409

    # 6. it should now show up as due (freshly accepted cards are immediately due)
    due = client.get(f"/decks/{deck_id}/due").json()
    assert any(c["id"] == card_id for c in due)

    # 7. answer it with a good grade -> reschedules into the future, drops off "due"
    resp = client.post(f"/cards/{card_id}/answer", json={"grade": 5})
    assert resp.status_code == 200
    assert resp.json()["repetitions"] == 1

    due_after = client.get(f"/decks/{deck_id}/due").json()
    assert all(c["id"] != card_id for c in due_after)


def test_reject_candidate(client, fake_llm):
    deck_id = client.post("/decks", json={"name": "D"}).json()["id"]
    text = ("Photosynthesis converts light into chemical energy. " * 20).encode("utf-8")
    source_id = client.post(
        f"/decks/{deck_id}/sources", files={"file": ("n.txt", io.BytesIO(text), "text/plain")}
    ).json()["source_id"]

    fake = ScriptedFakeClient(
        responses=[ScriptedFakeClient.cards_response(
            [{"question": "What does photosynthesis convert?", "answer": "Light into chemical energy."}]
        )]
    )
    client.app.state.llm_client = fake
    client.post(f"/decks/{deck_id}/sources/{source_id}/generate")

    card_id = client.get(f"/decks/{deck_id}/cards", params={"status": "candidate"}).json()[0]["id"]
    resp = client.post(f"/cards/{card_id}/review-decision", json={"action": "reject"})
    assert resp.json()["status"] == "rejected"

    due = client.get(f"/decks/{deck_id}/due").json()
    assert due == []


def test_manual_card_creation_and_answer(client):
    deck_id = client.post("/decks", json={"name": "D"}).json()["id"]
    resp = client.post(
        f"/decks/{deck_id}/cards", json={"question": "What is 2+2?", "answer": "4"}
    )
    assert resp.status_code == 201
    assert resp.json()["origin"] == "manual"
    card_id = resp.json()["id"]

    resp = client.post(f"/cards/{card_id}/answer", json={"grade": 4})
    assert resp.status_code == 200


def test_invalid_grade_returns_422(client):
    deck_id = client.post("/decks", json={"name": "D"}).json()["id"]
    card_id = client.post(f"/decks/{deck_id}/cards", json={"question": "Q?", "answer": "A"}).json()["id"]
    resp = client.post(f"/cards/{card_id}/answer", json={"grade": 9})
    assert resp.status_code == 422


def test_home_page_renders_created_deck(client):
    client.post("/decks", json={"name": "UI Test Deck"})
    resp = client.get("/")
    assert resp.status_code == 200
    assert "UI Test Deck" in resp.text


def test_deck_page_renders(client):
    deck_id = client.post("/decks", json={"name": "Deck Page Test"}).json()["id"]
    resp = client.get(f"/decks/{deck_id}")
    assert resp.status_code == 200
    assert "Deck Page Test" in resp.text
