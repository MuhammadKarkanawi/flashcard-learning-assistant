import json
from dataclasses import dataclass

from app.ai.client import ChatResult, InferenceUnavailableError
from app.ai.generation import generate_cards_for_chunk


@dataclass
class FakeClient:
    """Stub satisfying the same interface as LocalLLMClient.chat()."""
    response_content: str | None = None
    raise_error: Exception | None = None

    def chat(self, system_prompt, user_prompt, json_mode=True):
        if self.raise_error:
            raise self.raise_error
        return ChatResult(content=self.response_content, latency_seconds=0.01)


def _cards_json(cards):
    return json.dumps({"cards": cards})


def test_valid_output_is_accepted():
    client = FakeClient(response_content=_cards_json(
        [{"question": "What does SM-2 schedule?", "answer": "Flashcard reviews."}]
    ))
    outcome = generate_cards_for_chunk(
        client, 0, "some excerpt", [], max_cards=3, duplicate_threshold=0.85
    )
    assert outcome.error is None
    assert len(outcome.accepted) == 1
    assert outcome.rejected_duplicates == 0


def test_malformed_json_is_rejected_not_raised():
    client = FakeClient(response_content="not json at all {{{")
    outcome = generate_cards_for_chunk(
        client, 0, "excerpt", [], max_cards=3, duplicate_threshold=0.85
    )
    assert outcome.error is not None
    assert outcome.rejected_invalid == 1
    assert outcome.accepted == []


def test_markdown_fenced_json_is_still_parsed():
    fenced = "```json\n" + _cards_json([{"question": "What is spaced repetition?", "answer": "A review scheduling technique."}]) + "\n```"
    client = FakeClient(response_content=fenced)
    outcome = generate_cards_for_chunk(client, 0, "excerpt", [], max_cards=3, duplicate_threshold=0.85)
    assert outcome.error is None
    assert len(outcome.accepted) == 1


def test_duplicate_against_existing_question_is_rejected():
    client = FakeClient(response_content=_cards_json(
        [{"question": "What is the capital of France?", "answer": "Paris."}]
    ))
    outcome = generate_cards_for_chunk(
        client, 0, "excerpt", ["What is the capital of France?"], max_cards=3, duplicate_threshold=0.8
    )
    assert outcome.rejected_duplicates == 1
    assert outcome.accepted == []


def test_duplicate_within_same_batch_is_rejected():
    client = FakeClient(response_content=_cards_json([
        {"question": "What is the capital of France?", "answer": "Paris."},
        {"question": "What is the capital city of France?", "answer": "Paris."},
    ]))
    outcome = generate_cards_for_chunk(client, 0, "excerpt", [], max_cards=3, duplicate_threshold=0.8)
    assert len(outcome.accepted) == 1
    assert outcome.rejected_duplicates == 1


def test_more_cards_than_max_are_truncated():
    topics = ["Photosynthesis", "The French Revolution", "Binary search trees", "Newtonian mechanics", "DNA replication"]
    cards = [{"question": f"What is {t} in this context?", "answer": f"Answer about {t}"} for t in topics]
    client = FakeClient(response_content=_cards_json(cards))
    outcome = generate_cards_for_chunk(client, 0, "excerpt", [], max_cards=2, duplicate_threshold=0.85)
    assert len(outcome.accepted) == 2


def test_empty_cards_list_is_valid_and_accepted_as_no_op():
    client = FakeClient(response_content=_cards_json([]))
    outcome = generate_cards_for_chunk(client, 0, "excerpt", [], max_cards=3, duplicate_threshold=0.85)
    assert outcome.error is None
    assert outcome.accepted == []


def test_inference_error_is_captured_not_raised():
    client = FakeClient(raise_error=InferenceUnavailableError("connection refused"))
    outcome = generate_cards_for_chunk(client, 0, "excerpt", [], max_cards=3, duplicate_threshold=0.85)
    assert outcome.error is not None
    assert "InferenceUnavailableError" in outcome.error
    assert outcome.accepted == []


def test_card_failing_schema_validation_is_rejected():
    # question too short to pass GeneratedCard's min_length validator
    client = FakeClient(response_content=_cards_json([{"question": "Hi?", "answer": "x"}]))
    outcome = generate_cards_for_chunk(client, 0, "excerpt", [], max_cards=3, duplicate_threshold=0.85)
    assert outcome.error is not None
    assert outcome.rejected_invalid == 1
