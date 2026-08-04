import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models import Chunk, Document, DocumentStatus, User, UserRole
from app.schemas import DocumentOut
from app.services.ingest import chunk_text, extract_text
from app.services.ollama import OllamaError, embed_texts

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentOut])
def list_documents(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return (
        db.query(Document)
        .filter(Document.organization_id == user.organization_id)
        .order_by(Document.created_at.desc())
        .all()
    )


@router.post("/upload", response_model=DocumentOut)
async def upload_document(
    title: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.TRAINER)),
):
    allowed = {".pdf", ".docx", ".txt"}
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in allowed:
        raise HTTPException(status_code=400, detail="Formats acceptés: PDF, DOCX, TXT")

    upload_root = Path(settings.upload_dir)
    upload_root.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4()}{suffix}"
    dest = upload_root / stored_name
    content = await file.read()
    dest.write_bytes(content)

    doc = Document(
        organization_id=user.organization_id,
        uploaded_by=user.id,
        title=title,
        filename=file.filename or stored_name,
        file_path=str(dest),
        mime_type=file.content_type or "application/octet-stream",
        status=DocumentStatus.PENDING.value,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    try:
        text = extract_text(doc.file_path, doc.mime_type)
        parts = chunk_text(text)
        if not parts:
            raise ValueError("Aucun texte extractible")
        vectors = await embed_texts(parts)
        for idx, (part, vector) in enumerate(zip(parts, vectors)):
            db.add(
                Chunk(
                    document_id=doc.id,
                    organization_id=user.organization_id,
                    content=part,
                    chunk_index=idx,
                    embedding=vector,
                    meta={"source": doc.filename},
                )
            )
        doc.status = DocumentStatus.INDEXED.value
        doc.error_message = None
    except (OllamaError, ValueError, Exception) as exc:
        doc.status = DocumentStatus.FAILED.value
        doc.error_message = str(exc)
    db.commit()
    db.refresh(doc)
    return doc


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.TRAINER)),
):
    doc = (
        db.query(Document)
        .filter(Document.id == document_id, Document.organization_id == user.organization_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document introuvable")
    path = Path(doc.file_path)
    if path.exists():
        path.unlink(missing_ok=True)
    db.delete(doc)
    db.commit()
