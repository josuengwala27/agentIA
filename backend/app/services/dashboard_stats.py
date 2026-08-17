"""Aggregate dashboard figures without touching the database layer."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any


def score_pct(score: float | None, max_score: float | None) -> float | None:
    if score is None or not max_score:
        return None
    return round((float(score) / float(max_score)) * 100, 1)


def _as_date(value: datetime | date | str | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def build_learner_progress(
    learners: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_user: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for attempt in attempts:
        uid = str(attempt.get("user_id") or "")
        if uid:
            by_user[uid].append(attempt)

    rows: list[dict[str, Any]] = []
    for learner in learners:
        uid = str(learner["id"])
        user_attempts = by_user.get(uid, [])
        percents = [
            pct
            for pct in (score_pct(a.get("score"), a.get("max_score")) for a in user_attempts)
            if pct is not None
        ]
        weak: list[str] = []
        last_at = None
        for attempt in user_attempts:
            weak.extend([str(t) for t in (attempt.get("weak_topics") or []) if t])
            created = attempt.get("created_at")
            if created and (last_at is None or str(created) > str(last_at)):
                last_at = created
        top_weak = [topic for topic, _ in Counter(weak).most_common(5)]
        avg = round(sum(percents) / len(percents), 1) if percents else None
        rows.append(
            {
                "user_id": uid,
                "full_name": learner.get("full_name") or "",
                "email": learner.get("email") or "",
                "attempts_count": len(user_attempts),
                "average_score": avg,
                "last_attempt_at": last_at,
                "weak_topics": top_weak,
            }
        )

    rows.sort(
        key=lambda row: (
            row["average_score"] is None,
            row["average_score"] if row["average_score"] is not None else 0,
            row["full_name"].lower(),
        )
    )
    return rows


def build_score_timeline(
    attempts: list[dict[str, Any]],
    days: int = 14,
    today: date | None = None,
) -> list[dict[str, Any]]:
    end = today or datetime.now(timezone.utc).date()
    start = end - timedelta(days=days - 1)
    buckets: dict[str, list[float]] = { (start + timedelta(days=i)).isoformat(): [] for i in range(days) }
    for attempt in attempts:
        day = _as_date(attempt.get("created_at"))
        if day is None or day < start or day > end:
            continue
        pct = score_pct(attempt.get("score"), attempt.get("max_score"))
        if pct is None:
            continue
        buckets[day.isoformat()].append(pct)
    return [
        {
            "date": day,
            "average_score": round(sum(values) / len(values), 1) if values else None,
            "attempts_count": len(values),
        }
        for day, values in buckets.items()
    ]


def _topics_from_exercise(exercise: dict[str, Any]) -> list[str]:
    topics: list[str] = []
    if exercise.get("topic"):
        topics.append(str(exercise["topic"]))
    if exercise.get("title"):
        topics.append(str(exercise["title"]))
    payload = exercise.get("payload") or {}
    questions = payload.get("questions") or []
    case = payload.get("case") or {}
    if isinstance(case, dict) and case.get("questions"):
        questions = case.get("questions") or questions
    for question in questions:
        if isinstance(question, dict) and question.get("topic"):
            topics.append(str(question["topic"]))
    return topics


def match_exercise_for_topic(topic: str, exercises: list[dict[str, Any]]) -> dict[str, str | None] | None:
    needle = (topic or "").strip().lower()
    if not needle or not exercises:
        return None

    def hit(exercise: dict[str, Any]) -> dict[str, str | None]:
        return {
            "exercise_id": str(exercise.get("id") or "") or None,
            "document_id": str(exercise.get("document_id") or "") or None,
        }

    for exercise in exercises:
        if (exercise.get("topic") or "").strip().lower() == needle:
            return hit(exercise)
    for exercise in exercises:
        blob = " ".join(_topics_from_exercise(exercise)).lower()
        if needle in blob:
            return hit(exercise)
    return None


def attach_practice_links(
    weak_topics: list[tuple[str, int]],
    exercises: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for topic, count in weak_topics:
        match = match_exercise_for_topic(topic, exercises) or {}
        rows.append(
            {
                "topic": topic,
                "count": count,
                "exercise_id": match.get("exercise_id"),
                "document_id": match.get("document_id"),
            }
        )
    return rows
