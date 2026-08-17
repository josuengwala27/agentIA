from typing import Any

from sqlalchemy.orm import Session

from app.models import Document, Exercise, ExerciseType
from app.services.ollama import chat_completion, parse_json_response
from app.services.question_language import (
    default_topic_label,
    detect_content_language,
    language_display_name,
)
from app.services.rag import retrieve_chunks


async def build_context_from_document(
    db: Session, organization_id: str, document_id: str, topic: str | None
) -> tuple[str, str]:
    doc = db.get(Document, document_id)
    title = doc.title if doc else ""
    query = topic or title or "key concepts"
    chunks = await retrieve_chunks(db, organization_id, query, document_id=document_id, top_k=8)
    if not chunks:
        raise ValueError(f"Document non indexé ou vide: {title or document_id}")
    return "\n\n".join(c.content for c in chunks), title


def build_exercise_prompt(
    exercise_type: str,
    question_count: int,
    topic: str | None,
    lang_name: str,
) -> str:
    topic_hint = topic or "a precise topic taken from the context"
    lang_rule = (
        f"Write ALL learner-facing text (stems, choices, explanations, case brief, topics) in {lang_name}. "
        f"Do not use French unless {lang_name} is French."
    )
    if exercise_type == ExerciseType.QCM.value:
        return (
            f"Generate {question_count} multiple-choice questions from the context only. {lang_rule} "
            f"Each question MUST have a short concrete topic field tied to the content "
            f"(never 'general' / 'général'; prefer: {topic_hint}). "
            'JSON: {"questions":[{"id":"q1","stem":"...","choices":["A","B","C","D"],'
            '"correct_index":0,"explanation":"...","topic":"..."}]}'
        )
    if exercise_type == ExerciseType.OPEN.value:
        return (
            f"Generate {question_count} open questions. {lang_rule} "
            f"Each question MUST have a concrete topic (never 'general' / 'général'; prefer: {topic_hint}). "
            'JSON: {"questions":[{"id":"q1","stem":"...","expected_points":["..."],'
            '"max_score":5,"topic":"..."}]}'
        )
    if exercise_type == ExerciseType.CASE.value:
        return (
            f"Generate a short case study. {lang_rule} "
            f"Each question MUST have a concrete topic (never 'general' / 'général'; prefer: {topic_hint}). "
            'JSON: {"case":{"brief":"...","questions":[{"id":"q1","stem":"...",'
            '"expected_points":["..."],"max_score":5,"topic":"..."}]}}'
        )
    if exercise_type == ExerciseType.EXAM.value:
        return (
            f"Generate an exam simulation with {question_count} mixed items (MCQ and open). {lang_rule} "
            f"Each item MUST have a concrete topic (never 'general' / 'général'; prefer: {topic_hint}). "
            'JSON: {"questions":[{"id":"q1","type":"qcm","stem":"...","choices":["A","B","C","D"],'
            '"correct_index":0,"max_score":1,"topic":"..."},'
            '{"id":"q2","type":"open","stem":"...","expected_points":["..."],"max_score":5,"topic":"..."}]}'
        )
    raise ValueError("Type d'exercice non supporté")


async def generate_exercise_payload(
    db: Session,
    organization_id: str,
    document_id: str,
    exercise_type: str,
    topic: str | None,
    question_count: int,
) -> dict[str, Any]:
    context, title = await build_context_from_document(db, organization_id, document_id, topic)
    lang_code = detect_content_language(title, topic, context[:1500])
    lang_name = language_display_name(lang_code)
    prompt = build_exercise_prompt(exercise_type, question_count, topic, lang_name)

    content = await chat_completion(
        [
            {
                "role": "system",
                "content": (
                    "You generate pedagogical exercises strictly based on the context. "
                    f"Reply in JSON. Learner-facing text must be in {lang_name}."
                ),
            },
            {"role": "user", "content": f"Context:\n{context}\n\n{prompt}"},
        ],
        temperature=0.3,
        format_json=True,
    )
    payload = parse_json_response(content)
    return _ensure_question_topics(payload, exercise_type, topic, lang_code)


def _ensure_question_topics(
    payload: dict[str, Any],
    exercise_type: str,
    topic: str | None,
    lang_code: str = "fr",
) -> dict[str, Any]:
    """Guarantee each question has a concrete topic (Ollama often omits it)."""
    fallback = (topic or "").strip() or default_topic_label(lang_code)
    if fallback.lower() in {"général", "general"}:
        fallback = default_topic_label(lang_code)

    def fix_list(questions: list) -> None:
        for q in questions:
            if not isinstance(q, dict):
                continue
            raw = str(q.get("topic") or "").strip()
            if not raw or raw.lower() in {"général", "general"}:
                q["topic"] = fallback

    if exercise_type == ExerciseType.CASE.value:
        case = payload.get("case") or {}
        fix_list(case.get("questions") or [])
        payload["case"] = case
    else:
        fix_list(payload.get("questions") or [])
    return payload


async def grade_attempt(exercise: Exercise, answers: dict[str, Any]) -> tuple[float, float, dict, list[str]]:
    payload = exercise.payload
    feedback: dict[str, Any] = {"items": []}
    weak_topics: list[str] = []
    score = 0.0
    max_score = 0.0

    questions: list[dict] = []
    if exercise.exercise_type == ExerciseType.CASE.value:
        questions = payload.get("case", {}).get("questions", [])
    else:
        questions = payload.get("questions", [])

    for q in questions:
        qid = q["id"]
        stem = str(q.get("stem") or "")
        lang_code = detect_content_language(stem, q.get("topic"), exercise.topic)
        topic_fallback = default_topic_label(lang_code)
        topic_raw = (q.get("topic") or exercise.topic or topic_fallback).strip()
        topic = topic_fallback if topic_raw.lower() in {"général", "general", ""} else topic_raw
        user_answer = answers.get(qid)

        if "correct_index" in q or q.get("type") == "qcm":
            max_item = float(q.get("max_score", 1))
            max_score += max_item
            correct = int(q["correct_index"])
            ok = user_answer is not None and int(user_answer) == correct
            gained = max_item if ok else 0.0
            score += gained
            if not ok:
                weak_topics.append(topic)
            feedback["items"].append(
                {
                    "id": qid,
                    "correct": ok,
                    "score": gained,
                    "max_score": max_item,
                    "explanation": q.get("explanation", ""),
                    "topic": topic,
                }
            )
        else:
            max_item = float(q.get("max_score", 5))
            max_score += max_item
            expected = q.get("expected_points", [])
            lang_name = language_display_name(lang_code)
            grading_prompt = (
                f"Grade the learner answer. Write the feedback field in {lang_name}. "
                f'JSON: {{"score":0,"max_score":{max_item},"feedback":"...","weak":true}}'
            )
            content = await chat_completion(
                [
                    {
                        "role": "system",
                        "content": (
                            "You are a strict but kind pedagogical grader. JSON only. "
                            f"Feedback language: {lang_name}."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Question: {q.get('stem')}\n"
                            f"Expected points: {expected}\n"
                            f"Answer: {user_answer}\n"
                            f"{grading_prompt}"
                        ),
                    },
                ],
                temperature=0.1,
                format_json=True,
            )
            result = parse_json_response(content)
            gained = float(result.get("score", 0))
            score += min(max(gained, 0), max_item)
            if result.get("weak") or gained < max_item * 0.6:
                weak_topics.append(topic)
            feedback["items"].append(
                {
                    "id": qid,
                    "correct": gained >= max_item * 0.8,
                    "score": gained,
                    "max_score": max_item,
                    "explanation": result.get("feedback", ""),
                    "topic": topic,
                }
            )

    feedback["summary"] = f"Score {score:.1f}/{max_score:.1f}"
    return score, max_score, feedback, sorted(set(weak_topics))
