import csv
import io
from collections import Counter, defaultdict

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models import Attempt, Document, DocumentStatus, Exercise, User, UserRole
from app.schemas import AttemptOut, LearnerStats, TrainerStats
from app.services.dashboard_stats import (
    attach_practice_links,
    build_learner_progress,
    build_score_timeline,
    score_pct,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _attempt_dict(attempt: Attempt) -> dict:
    return {
        "user_id": attempt.user_id,
        "score": attempt.score,
        "max_score": attempt.max_score,
        "weak_topics": attempt.weak_topics or [],
        "created_at": attempt.created_at,
        "exercise_id": attempt.exercise_id,
    }


def _exercise_dict(exercise: Exercise) -> dict:
    return {
        "id": exercise.id,
        "title": exercise.title,
        "topic": exercise.topic,
        "payload": exercise.payload or {},
        "document_id": exercise.document_id,
    }


@router.get("/learner", response_model=LearnerStats)
def learner_dashboard(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    attempts = (
        db.query(Attempt)
        .filter(Attempt.user_id == user.id, Attempt.organization_id == user.organization_id)
        .order_by(Attempt.created_at.desc())
        .all()
    )
    docs_count = (
        db.query(Document)
        .filter(
            Document.organization_id == user.organization_id,
            Document.status == DocumentStatus.INDEXED.value,
        )
        .count()
    )
    scored = [a for a in attempts if a.score is not None and a.max_score]
    avg = None
    if scored:
        avg = sum((a.score / a.max_score) * 100 for a in scored) / len(scored)
    weak_counter = Counter()
    for a in attempts:
        if a.weak_topics:
            weak_counter.update(a.weak_topics)
    exercises = (
        db.query(Exercise)
        .filter(Exercise.organization_id == user.organization_id)
        .order_by(Exercise.created_at.desc())
        .all()
    )
    practice = attach_practice_links(
        weak_counter.most_common(8),
        [_exercise_dict(ex) for ex in exercises],
    )
    return LearnerStats(
        attempts_count=len(attempts),
        average_score=round(avg, 1) if avg is not None else None,
        documents_available=docs_count,
        weak_topics=[row["topic"] for row in practice],
        recent_attempts=[AttemptOut.model_validate(a) for a in attempts[:10]],
        practice_topics=practice,
    )


@router.get("/trainer", response_model=TrainerStats)
def trainer_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.TRAINER)),
):
    org = user.organization_id
    learner_users = (
        db.query(User).filter(User.organization_id == org, User.role == UserRole.LEARNER.value).all()
    )
    documents_count = db.query(Document).filter(Document.organization_id == org).count()
    indexed = (
        db.query(Document)
        .filter(Document.organization_id == org, Document.status == DocumentStatus.INDEXED.value)
        .count()
    )
    attempts = (
        db.query(Attempt)
        .options(joinedload(Attempt.exercise))
        .filter(Attempt.organization_id == org)
        .all()
    )
    exercises = db.query(Exercise).filter(Exercise.organization_id == org).all()
    learner_ids = {u.id for u in learner_users}
    learner_attempts = [a for a in attempts if a.user_id in learner_ids]
    scored = [a for a in learner_attempts if a.score is not None and a.max_score]
    avg = None
    if scored:
        avg = sum((a.score / a.max_score) * 100 for a in scored) / len(scored)

    weak_counter: Counter[str] = Counter()
    for a in learner_attempts:
        if a.weak_topics:
            weak_counter.update(a.weak_topics)

    by_type: dict[str, list[float]] = defaultdict(list)
    for a in learner_attempts:
        pct = score_pct(a.score, a.max_score)
        if pct is None:
            continue
        ex = a.exercise
        if ex:
            by_type[ex.exercise_type].append(pct)

    return TrainerStats(
        learners_count=len(learner_users),
        documents_count=documents_count,
        indexed_documents=indexed,
        attempts_count=len(learner_attempts),
        average_score=round(avg, 1) if avg is not None else None,
        recurrent_weak_topics=attach_practice_links(
            weak_counter.most_common(10),
            [_exercise_dict(ex) for ex in exercises],
        ),
        score_by_exercise_type=[
            {"exercise_type": k, "average_score": round(sum(v) / len(v), 1)} for k, v in by_type.items()
        ],
        learners=build_learner_progress(
            [{"id": u.id, "full_name": u.full_name, "email": u.email} for u in learner_users],
            [_attempt_dict(a) for a in learner_attempts],
        ),
        score_over_time=build_score_timeline([_attempt_dict(a) for a in learner_attempts]),
    )


@router.get("/trainer/export.csv")
def export_trainer_csv(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.TRAINER)),
):
    rows = (
        db.query(Attempt, User)
        .join(User, User.id == Attempt.user_id)
        .filter(Attempt.organization_id == user.organization_id)
        .order_by(Attempt.created_at.desc())
        .all()
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "attempt_id",
            "learner_name",
            "learner_email",
            "exercise_id",
            "score",
            "max_score",
            "weak_topics",
            "created_at",
        ]
    )
    for attempt, learner in rows:
        writer.writerow(
            [
                attempt.id,
                learner.full_name,
                learner.email,
                attempt.exercise_id,
                attempt.score,
                attempt.max_score,
                "|".join(attempt.weak_topics or []),
                attempt.created_at.isoformat() if attempt.created_at else "",
            ]
        )
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=rapport-formation.csv"},
    )
