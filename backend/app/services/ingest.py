from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader

from app.core.config import settings


def extract_text(file_path: str, mime_type: str) -> str:
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix == ".txt" or mime_type.startswith("text/"):
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix == ".pdf" or mime_type == "application/pdf":
        reader = PdfReader(str(path))
        parts = []
        for page in reader.pages:
            text = page.extract_text() or ""
            parts.append(text)
        return "\n".join(parts)
    if suffix in {".docx"} or mime_type in {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    }:
        doc = DocxDocument(str(path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    raise ValueError(f"Format non supporté: {suffix or mime_type}")


def chunk_text(text: str) -> list[str]:
    cleaned = " ".join(text.split())
    if not cleaned:
        return []
    size = settings.chunk_size
    overlap = settings.chunk_overlap
    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(start + size, len(cleaned))
        chunks.append(cleaned[start:end])
        if end == len(cleaned):
            break
        start = max(0, end - overlap)
    return chunks
