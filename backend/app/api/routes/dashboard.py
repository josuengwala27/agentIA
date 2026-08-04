import csv
import io
from collections import Counter, defaultdict

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models import Attempt, Document, DocumentStatus, User, UserRole
from app.schemas import AttemptOut, LearnerStats, TrainerStats

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


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
    weak: list[str] = []
    for a in attempts:
        if a.weak_topics:
            weak.extend(a.weak_topics)
    top_weak = [t for t, _ in Counter(weak).most_common(8)]
    return LearnerStats(
        attempts_count=len(attempts),
        average_score=round(avg, 1) if avg is not None else None,
        documents_available=docs_count,
        weak_topics=top_weak,
        recent_attempts=[AttemptOut.model_validate(a) for a in attempts[:10]],
    )


@router.get("/trainer", response_model=TrainerStats)
def trainer_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.TRAINER)),
):
    org = user.organization_id
    learners_count = (
        db.query(User).filter(User.organization_id == org, User.role == UserRole.LEARNER.value).count()
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
    scored = [a for a in attempts if a.score is not None and a.max_score]
    avg = None
    if scored:
        avg = sum((a.score / a.max_score) * 100 for a in scored) / len(scored)

    weak_counter: Counter[str] = Counter()
    for a in attempts:
        if a.weak_topics:
            weak_counter.update(a.weak_topics)

    by_type: dict[str, list[float]] = defaultdict(list)
    for a in attempts:
        if a.score is None or not a.max_score:
            continue
        ex = a.exercise
        if ex:
            by_type[ex.exercise_type].append((a.score / a.max_score) * 100)

    return TrainerStats(
        learners_count=learners_count,
        documents_count=documents_count,
        indexed_documents=indexed,
        attempts_count=len(attempts),
        average_score=round(avg, 1) if avg is not None else None,
        recurrent_weak_topics=[{"topic": t, "count": c} for t, c in weak_counter.most_common(10)],
        score_by_exercise_type=[
            {"exercise_type": k, "average_score": round(sum(v) / len(v), 1)} for k, v in by_type.items()
        ],
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
        ["attempt_id", "learner_email", "exercise_id", "score", "max_score", "weak_topics", "created_at"]
    )
    for attempt, learner in rows:
        writer.writerow(
            [
                attempt.id,
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
