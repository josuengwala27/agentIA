import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import Document, DocumentStatus, User
from app.schemas import ComprehensionRequest, GrammarRequest, GrammarResponse
from app.services.languages import (
    analyze_pronunciation,
    correct_grammar,
    generate_comprehension,
    transcribe_audio,
    whisper_available,
)
from app.services.ollama import OllamaError
from app.services.question_language import detect_question_language

router = APIRouter(prefix="/languages", tags=["languages"])


@router.get("/status")
def languages_status(user: User = Depends(get_current_user)):
    _ = user
    return {"whisper": whisper_available()}


@router.post("/grammar", response_model=GrammarResponse)
async def grammar_check(payload: GrammarRequest, user: User = Depends(get_current_user)):
    _ = user
    try:
        result = await correct_grammar(payload.text, payload.language)
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return GrammarResponse(
        corrected_text=result.get("corrected_text", payload.text),
        explanations=result.get("explanations", []),
    )


@router.post("/comprehension")
async def comprehension(
    payload: ComprehensionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
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
        return await generate_comprehension(
            db, user.organization_id, payload.document_id, payload.question_count
        )
    except (OllamaError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/pronunciation")
async def pronunciation(
    reference_text: str = Form(...),
    audio: UploadFile | None = File(None),
    spoken_text: str | None = Form(None),
    user: User = Depends(get_current_user),
):
    _ = user
    transcript = ""
    engine = "unavailable"
    if audio is not None and audio.filename:
        suffix = Path(audio.filename or "audio.wav").suffix or ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await audio.read())
            tmp_path = tmp.name
        transcript = await transcribe_audio(
            tmp_path, language=detect_question_language(reference_text)
        )
        Path(tmp_path).unlink(missing_ok=True)
        if transcript:
            engine = "faster-whisper"
    if not transcript and (spoken_text or "").strip():
        transcript = spoken_text.strip()
        engine = "manual"
    if not transcript:
        raise HTTPException(
            status_code=400,
            detail=(
                "Fournissez un enregistrement (faster-whisper) ou saisissez ce que vous avez lu "
                "dans le champ transcription."
            ),
        )
    return analyze_pronunciation(reference_text, transcript, engine=engine)
