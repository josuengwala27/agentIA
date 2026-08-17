from datetime import date, datetime, timezone

from app.services.dashboard_stats import (
    attach_practice_links,
    build_learner_progress,
    build_score_timeline,
    match_exercise_for_topic,
    score_pct,
)


def test_score_pct() -> None:
    assert score_pct(8, 10) == 80.0
    assert score_pct(None, 10) is None


def test_learner_progress_sorts_lowest_scores_first() -> None:
    learners = [
        {"id": "a", "full_name": "Ada", "email": "ada@demo.local"},
        {"id": "b", "full_name": "Bob", "email": "bob@demo.local"},
    ]
    attempts = [
        {"user_id": "a", "score": 9, "max_score": 10, "weak_topics": [], "created_at": "2026-08-01"},
        {"user_id": "b", "score": 3, "max_score": 10, "weak_topics": ["phrasal verbs"], "created_at": "2026-08-02"},
    ]
    rows = build_learner_progress(learners, attempts)
    assert rows[0]["full_name"] == "Bob"
    assert rows[0]["average_score"] == 30.0
    assert rows[0]["weak_topics"] == ["phrasal verbs"]
    assert rows[1]["average_score"] == 90.0


def test_score_timeline_fills_requested_days() -> None:
    today = date(2026, 8, 17)
    points = build_score_timeline(
        [
            {
                "score": 10,
                "max_score": 10,
                "created_at": datetime(2026, 8, 17, tzinfo=timezone.utc),
            }
        ],
        days=14,
        today=today,
    )
    assert len(points) == 14
    assert points[-1]["date"] == "2026-08-17"
    assert points[-1]["average_score"] == 100.0
    assert points[0]["attempts_count"] == 0


def test_match_exercise_from_question_topic() -> None:
    exercises = [
        {
            "id": "ex-1",
            "title": "QCM grammar",
            "topic": None,
            "document_id": "doc-1",
            "payload": {"questions": [{"id": "q1", "topic": "phrasal verbs"}]},
        }
    ]
    match = match_exercise_for_topic("phrasal verbs", exercises)
    assert match == {"exercise_id": "ex-1", "document_id": "doc-1"}
    linked = attach_practice_links([("phrasal verbs", 4)], exercises)
    assert linked[0]["exercise_id"] == "ex-1"
    assert linked[0]["count"] == 4
