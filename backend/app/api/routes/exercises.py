from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models import Attempt, Document, DocumentStatus, Exercise, ExerciseType, User, UserRole
from app.schemas import AttemptOut, ExerciseOut, GenerateExerciseRequest, SubmitAttemptRequest
from app.services.grading import generate_exercise_payload, grade_attempt
from app.services.ollama import OllamaError

router = APIRouter(prefix="/exercises", tags=["exercises"])


@router.get("", response_model=list[ExerciseOut])
def list_exercises(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(Exercise)
        .filter(Exercise.organization_id == user.organization_id)
        .order_by(Exercise.created_at.desc())
        .all()
    )


@router.get("/attempts/me", response_model=list[AttemptOut])
def my_attempts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(Attempt)
        .filter(Attempt.user_id == user.id, Attempt.organization_id == user.organization_id)
        .order_by(Attempt.created_at.desc())
        .all()
    )


@router.get("/{exercise_id}", response_model=ExerciseOut)
def get_exercise(exercise_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    exercise = (
        db.query(Exercise)
        .filter(Exercise.id == exercise_id, Exercise.organization_id == user.organization_id)
        .first()
    )
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercice introuvable")
    return exercise


@router.post("/generate", response_model=ExerciseOut)
async def generate_exercise(
    payload: GenerateExerciseRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.TRAINER)),
):
    if payload.exercise_type not in {e.value for e in ExerciseType}:
        raise HTTPException(status_code=400, detail="Type d'exercice invalide")
    doc = (
        db.query(Document)
        .filter(
            Document.id == payload.document_id,
            Document.organization_id == user.organization_id,
            Document.status == DocumentStatus.INDEXED.value,
        )
        .first()
    )
    if not doc:
        raise HTTPException(status_code=400, detail="Document indexé requis")

    try:
        exercise_payload = await generate_exercise_payload(
            db,
            user.organization_id,
            payload.document_id,
            payload.exercise_type,
            payload.topic,
            payload.question_count,
        )
    except (OllamaError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    title = payload.title or f"{payload.exercise_type.upper()} — {doc.title}"
    exercise = Exercise(
        organization_id=user.organization_id,
        document_id=doc.id,
        created_by=user.id,
        title=title,
        exercise_type=payload.exercise_type,
        topic=payload.topic,
        payload=exercise_payload,
        time_limit_seconds=payload.time_limit_seconds
        or (1800 if payload.exercise_type == ExerciseType.EXAM.value else None),
    )
    db.add(exercise)
    db.commit()
    db.refresh(exercise)
    return exercise


@router.post("/{exercise_id}/attempts", response_model=AttemptOut)
async def submit_attempt(
    exercise_id: str,
    payload: SubmitAttemptRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    exercise = (
        db.query(Exercise)
        .filter(Exercise.id == exercise_id, Exercise.organization_id == user.organization_id)
        .first()
    )
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercice introuvable")
    try:
        score, max_score, feedback, weak_topics = await grade_attempt(exercise, payload.answers)
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    attempt = Attempt(
        organization_id=user.organization_id,
        exercise_id=exercise.id,
        user_id=user.id,
        answers=payload.answers,
        score=score,
        max_score=max_score,
        feedback=feedback,
        weak_topics=weak_topics,
        duration_seconds=payload.duration_seconds,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt
