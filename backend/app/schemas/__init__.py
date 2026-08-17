from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: str  # EmailStr rejects .local demo domains
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    organization_id: str
    is_active: bool = True

    model_config = {"from_attributes": True}


class UserAdminOut(UserOut):
    created_at: datetime


class CreateUserRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    full_name: str = Field(min_length=1, max_length=255)
    role: str = "learner"
    password: str | None = Field(default=None, min_length=8)


class UserCreatedOut(UserAdminOut):
    temporary_password: str | None = None


class SetActiveRequest(BaseModel):
    is_active: bool


class ResetPasswordRequest(BaseModel):
    password: str | None = Field(default=None, min_length=8)


class ResetPasswordResponse(BaseModel):
    temporary_password: str


class DocumentOut(BaseModel):
    id: str
    title: str
    filename: str
    status: str
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str | None = None
    document_id: str | None = None


class Citation(BaseModel):
    document_id: str
    document_title: str
    chunk_index: int
    excerpt: str


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    citations: list[Citation]


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    citations: list[Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class GenerateExerciseRequest(BaseModel):
    document_id: str
    exercise_type: str
    title: str | None = None
    topic: str | None = None
    question_count: int = Field(default=5, ge=1, le=20)
    time_limit_seconds: int | None = None


class ExerciseOut(BaseModel):
    id: str
    title: str
    exercise_type: str
    topic: str | None
    payload: dict[str, Any]
    time_limit_seconds: int | None
    document_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SubmitAttemptRequest(BaseModel):
    answers: dict[str, Any]
    duration_seconds: int | None = None


class AttemptOut(BaseModel):
    id: str
    exercise_id: str
    score: float | None
    max_score: float | None
    feedback: dict[str, Any] | None
    weak_topics: list[Any] | None
    duration_seconds: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class LearnerProgress(BaseModel):
    user_id: str
    full_name: str
    email: str
    attempts_count: int
    average_score: float | None
    last_attempt_at: datetime | None
    weak_topics: list[str]


class ScorePoint(BaseModel):
    date: str
    average_score: float | None
    attempts_count: int


class WeakTopicStat(BaseModel):
    topic: str
    count: int
    exercise_id: str | None = None
    document_id: str | None = None


class LearnerStats(BaseModel):
    attempts_count: int
    average_score: float | None
    documents_available: int
    weak_topics: list[str]
    recent_attempts: list[AttemptOut]
    practice_topics: list[WeakTopicStat] = []


class TrainerStats(BaseModel):
    learners_count: int
    documents_count: int
    indexed_documents: int
    attempts_count: int
    average_score: float | None
    recurrent_weak_topics: list[WeakTopicStat]
    score_by_exercise_type: list[dict[str, Any]]
    learners: list[LearnerProgress] = []
    score_over_time: list[ScorePoint] = []


class GrammarRequest(BaseModel):
    text: str = Field(min_length=1)
    language: str = "auto"


class GrammarResponse(BaseModel):
    corrected_text: str
    explanations: list[str]


class ComprehensionRequest(BaseModel):
    document_id: str
    question_count: int = Field(default=3, ge=1, le=10)


class PronunciationRequest(BaseModel):
    reference_text: str = Field(min_length=1)
