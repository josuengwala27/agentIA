from typing import Any

from sqlalchemy.orm import Session

from app.models import Document, Exercise, ExerciseType
from app.services.ollama import chat_completion, parse_json_response
from app.services.rag import retrieve_chunks


async def build_context_from_document(db: Session, organization_id: str, document_id: str, topic: str | None) -> str:
    query = topic or "concepts clés du document"
    chunks = await retrieve_chunks(db, organization_id, query, document_id=document_id, top_k=8)
    if not chunks:
        doc = db.get(Document, document_id)
        raise ValueError(f"Document non indexé ou vide: {doc.title if doc else document_id}")
    return "\n\n".join(c.content for c in chunks)


async def generate_exercise_payload(
    db: Session,
    organization_id: str,
    document_id: str,
    exercise_type: str,
    topic: str | None,
    question_count: int,
) -> dict[str, Any]:
    context = await build_context_from_document(db, organization_id, document_id, topic)

    if exercise_type == ExerciseType.QCM.value:
        topic_hint = topic or "thème précis tiré du contexte (ex: EPI, prévention, urgences)"
        prompt = (
            f"Génère {question_count} QCM en français à partir du contexte uniquement. "
            f"Chaque question DOIT avoir un champ topic concret et court lié au contenu "
            f"(jamais 'général' ; priorité: {topic_hint}). "
            'JSON: {"questions":[{"id":"q1","stem":"...","choices":["A","B","C","D"],'
            '"correct_index":0,"explanation":"...","topic":"..."}]}'
        )
    elif exercise_type == ExerciseType.OPEN.value:
        topic_hint = topic or "thème précis tiré du contexte"
        prompt = (
            f"Génère {question_count} questions ouvertes en français. "
            f"Chaque question DOIT avoir un topic concret (jamais 'général' ; priorité: {topic_hint}). "
            'JSON: {"questions":[{"id":"q1","stem":"...","expected_points":["..."],'
            '"max_score":5,"topic":"..."}]}'
        )
    elif exercise_type == ExerciseType.CASE.value:
        topic_hint = topic or "thème précis tiré du contexte"
        prompt = (
            "Génère une étude de cas courte en français. "
            f"Chaque question DOIT avoir un topic concret (jamais 'général' ; priorité: {topic_hint}). "
            'JSON: {"case":{"brief":"...","questions":[{"id":"q1","stem":"...",'
            '"expected_points":["..."],"max_score":5,"topic":"..."}]}}'
        )
    elif exercise_type == ExerciseType.EXAM.value:
        topic_hint = topic or "thème précis tiré du contexte"
        prompt = (
            f"Génère une simulation d'examen avec {question_count} items mixtes (QCM et ouvertes). "
            f"Chaque item DOIT avoir un topic concret (jamais 'général' ; priorité: {topic_hint}). "
            'JSON: {"questions":[{"id":"q1","type":"qcm","stem":"...","choices":["A","B","C","D"],'
            '"correct_index":0,"max_score":1,"topic":"..."},'
            '{"id":"q2","type":"open","stem":"...","expected_points":["..."],"max_score":5,"topic":"..."}]}'
        )
    else:
        raise ValueError("Type d'exercice non supporté")

    content = await chat_completion(
        [
            {
                "role": "system",
                "content": "Tu génères des exercices pédagogiques strictement basés sur le contexte. Réponds en JSON.",
            },
            {"role": "user", "content": f"Contexte:\n{context}\n\n{prompt}"},
        ],
        temperature=0.3,
        format_json=True,
    )
    payload = parse_json_response(content)
    return _ensure_question_topics(payload, exercise_type, topic)


def _ensure_question_topics(payload: dict[str, Any], exercise_type: str, topic: str | None) -> dict[str, Any]:
    """Guarantee each question has a concrete topic (Ollama often omits it)."""
    fallback = (topic or "").strip() or "contenu du cours"
    if fallback.lower() in {"général", "general"}:
        fallback = "contenu du cours"

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
        topic_raw = (q.get("topic") or exercise.topic or "contenu du cours").strip()
        topic = "contenu du cours" if topic_raw.lower() in {"général", "general", ""} else topic_raw
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
            grading_prompt = (
                "Note la réponse de l'apprenant. "
                f'JSON: {{"score":0,"max_score":{max_item},"feedback":"...","weak":true}}'
            )
            content = await chat_completion(
                [
                    {
                        "role": "system",
                        "content": "Tu es un correcteur pédagogique strict mais bienveillant. JSON uniquement.",
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Question: {q.get('stem')}\n"
                            f"Points attendus: {expected}\n"
                            f"Réponse: {user_answer}\n"
                            f"{grading_prompt}"
                        ),
                    },
                ],
                temperature=0.1,
                format_json=True,
            )
            from app.services.ollama import parse_json_response

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
