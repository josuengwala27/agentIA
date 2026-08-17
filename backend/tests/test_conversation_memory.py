from app.services.conversation_memory import (
    build_tutor_messages,
    is_short_followup,
    retrieval_query,
    sanitize_history,
)
from app.services.question_language import detect_thread_language


def test_short_followup_uses_previous_question_for_retrieval() -> None:
    history = [{"role": "user", "content": "What is a phrasal verb?"}]
    query = retrieval_query("Give me 3 examples", history)
    assert "phrasal verb" in query.lower()
    assert "examples" in query.lower()


def test_full_question_does_not_mix_previous_topic() -> None:
    history = [{"role": "user", "content": "What is a phrasal verb?"}]
    query = retrieval_query("What are the main safety rules at work?", history)
    assert "phrasal" not in query.lower()
    assert "safety rules" in query.lower()


def test_followup_keeps_previous_language() -> None:
    history = [{"role": "user", "content": "What is a phrasal verb?"}]
    assert detect_thread_language("Give me 3 examples", history) == "en"
    assert is_short_followup("Give me 3 examples")


def test_sanitize_drops_error_turns_and_clips() -> None:
    history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Erreur IA : timeout"},
        {"role": "assistant", "content": "A phrasal verb combines a verb and a particle."},
    ]
    cleaned = sanitize_history(history)
    assert all("Erreur IA" not in item["content"] for item in cleaned)
    assert cleaned[-1]["role"] == "assistant"


def test_tutor_messages_include_history_then_current_question() -> None:
    messages = build_tutor_messages(
        system="Tutor",
        context="[1] A phrasal verb has a special meaning.",
        question="Give me 3 examples",
        history=[
            {"role": "user", "content": "What is a phrasal verb?"},
            {"role": "assistant", "content": "It is a verb plus a particle."},
        ],
        reply_lang="English",
    )
    roles = [m["role"] for m in messages]
    assert roles == ["system", "user", "assistant", "user"]
    assert "phrasal verb" in messages[1]["content"].lower()
    assert "Give me 3 examples" in messages[-1]["content"]
    assert "English" in messages[-1]["content"]
