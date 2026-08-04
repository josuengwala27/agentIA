import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models import Document, DocumentStatus, User
from app.schemas import ComprehensionRequest, GrammarRequest, GrammarResponse
from app.services.languages import (
    analyze_pronunciation_stub,
    correct_grammar,
    generate_comprehension,
    transcribe_audio,
)
from app.services.ollama import OllamaError

router = APIRouter(prefix="/languages", tags=["languages"])


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
    user: User = Depends(get_current_user),
):
    _ = user
    transcript = ""
    if audio is not None:
        suffix = Path(audio.filename or "audio.wav").suffix or ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await audio.read())
            tmp_path = tmp.name
        transcript = await transcribe_audio(tmp_path)
        Path(tmp_path).unlink(missing_ok=True)
        if not transcript:
            transcript = "(transcription indisponible — installez faster-whisper)"
    else:
        transcript = reference_text
    return analyze_pronunciation_stub(reference_text, transcript)
