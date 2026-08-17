"""Keep a short pedagogical thread so follow-up questions still make sense."""

from __future__ import annotations

HISTORY_LIMIT = 8
MAX_TURN_CHARS = 800
_ERROR_PREFIXES = ("Erreur IA", "Erreur technique")


def is_short_followup(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return False
    return len(stripped.split()) <= 6


def prior_user_texts(history: list[dict[str, str]]) -> list[str]:
    return [
        (item.get("content") or "").strip()
        for item in history
        if item.get("role") == "user" and (item.get("content") or "").strip()
    ]


def retrieval_query(question: str, history: list[dict[str, str]] | None) -> str:
    """Use the previous user question when the current turn is a short follow-up."""
    current = (question or "").strip()
    users = prior_user_texts(history or [])
    if users and is_short_followup(current):
        return f"{users[-1]}\n{current}"[:1500]
    return current


def sanitize_history(
    history: list[dict[str, str]] | None,
    limit: int = HISTORY_LIMIT,
) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []
    for item in history or []:
        role = item.get("role")
        content = (item.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        if role == "assistant" and content.startswith(_ERROR_PREFIXES):
            continue
        if len(content) > MAX_TURN_CHARS:
            content = content[: MAX_TURN_CHARS - 1] + "…"
        if cleaned and cleaned[-1]["role"] == role:
            cleaned[-1]["content"] += "\n" + content
        else:
            cleaned.append({"role": role, "content": content})
    return cleaned[-limit:]


def build_tutor_messages(
    *,
    system: str,
    context: str,
    question: str,
    history: list[dict[str, str]] | None,
    reply_lang: str,
) -> list[dict[str, str]]:
    turns = sanitize_history(history)
    system_content = (
        f"{system}\n\n"
        "Source excerpts (may be in any language; do not switch to their language "
        "unless the question is in that language):\n"
        f"{context}"
    )
    messages: list[dict[str, str]] = [{"role": "system", "content": system_content}]
    if turns and turns[0]["role"] == "assistant":
        turns = turns[1:]
    messages.extend(turns)
    current = {
        "role": "user",
        "content": f"{question.strip()}\n\nMandatory reply language: {reply_lang}.",
    }
    if messages[-1]["role"] == "user":
        messages[-1]["content"] += "\n" + current["content"]
    else:
        messages.append(current)
    return messages
