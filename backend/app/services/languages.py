from typing import Any

from app.services.ollama import chat_completion, parse_json_response
from app.services.rag import retrieve_chunks
from sqlalchemy.orm import Session


async def correct_grammar(text: str, language: str = "fr") -> dict[str, Any]:
    content = await chat_completion(
        [
            {
                "role": "system",
                "content": (
                    "Tu corriges orthographe et grammaire. "
                    'JSON: {"corrected_text":"...","explanations":["..."]}'
                ),
            },
            {
                "role": "user",
                "content": f"Langue: {language}\nTexte:\n{text}",
            },
        ],
        temperature=0.1,
        format_json=True,
    )
    return parse_json_response(content)


async def generate_comprehension(
    db: Session,
    organization_id: str,
    document_id: str,
    question_count: int,
) -> dict[str, Any]:
    chunks = await retrieve_chunks(db, organization_id, "compréhension écrite", document_id=document_id, top_k=6)
    if not chunks:
        raise ValueError("Document non indexé")
    context = "\n\n".join(c.content for c in chunks)
    content = await chat_completion(
        [
            {
                "role": "system",
                "content": (
                    "Génère un exercice de compréhension écrite. "
                    'JSON: {"passage":"...","questions":[{"id":"q1","stem":"...",'
                    '"choices":["A","B","C","D"],"correct_index":0,"explanation":"..."}]}'
                ),
            },
            {
                "role": "user",
                "content": f"Contexte:\n{context}\n\nNombre de questions: {question_count}",
            },
        ],
        temperature=0.3,
        format_json=True,
    )
    return parse_json_response(content)


def analyze_pronunciation_stub(reference_text: str, transcript: str) -> dict[str, Any]:
    ref_words = [w.lower().strip(".,;:!?") for w in reference_text.split() if w.strip()]
    hyp_words = [w.lower().strip(".,;:!?") for w in transcript.split() if w.strip()]
    matches = sum(1 for a, b in zip(ref_words, hyp_words) if a == b)
    total = max(len(ref_words), 1)
    accuracy = matches / total
    return {
        "transcript": transcript,
        "accuracy": round(accuracy, 3),
        "matched_words": matches,
        "total_words": len(ref_words),
        "feedback": (
            "Bonne fluidité globale."
            if accuracy >= 0.8
            else "Répétez lentement les mots non reconnus et travaillez la liaison."
        ),
        "engine": "faster-whisper" if transcript else "unavailable",
    }


async def transcribe_audio(file_path: str) -> str:
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError:
        return ""

    model = WhisperModel("base", device="cpu", compute_type="int8")
    segments, _ = model.transcribe(file_path, language="fr")
    return " ".join(seg.text.strip() for seg in segments).strip()
