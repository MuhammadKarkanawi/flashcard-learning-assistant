"""Prompt templates for flashcard generation. Kept separate from the calling
logic so prompt variants can be swapped/compared during evaluation."""

SYSTEM_PROMPT = (
    "You are a flashcard-writing assistant for a spaced-repetition learning app. "
    "Given a short excerpt of study material, produce concise question/answer "
    "flashcards that test understanding of ONLY that excerpt. "
    "Never invent facts that are not supported by the excerpt. "
    "If the excerpt does not contain enough substantive, testable content, "
    "return an empty list of cards instead of inventing questions. "
    'Respond with ONLY a JSON object of the exact form: '
    '{"cards": [{"question": "...", "answer": "..."}]}. '
    "No prose, no markdown fences, no extra keys."
)

USER_PROMPT_TEMPLATE = (
    "Excerpt (source material):\n---\n{excerpt}\n---\n\n"
    "Produce at most {max_cards} flashcards grounded strictly in this excerpt."
)


def build_user_prompt(excerpt: str, max_cards: int) -> str:
    return USER_PROMPT_TEMPLATE.format(excerpt=excerpt, max_cards=max_cards)
