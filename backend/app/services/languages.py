from difflib import SequenceMatcher
import re
from typing import Any

from sqlalchemy.orm import Session

from app.models import Document
from app.services.ollama import chat_completion, parse_json_response
from app.services.question_language import (
    detect_content_language,
    detect_question_language,
    language_display_name,
    pronunciation_feedback,
    shadowing_tip,
    whisper_language_code,
)
from app.services.rag import retrieve_chunks

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


async def correct_grammar(text: str, language: str = "auto") -> dict[str, Any]:
    if language and language not in {"auto", "detect"}:
        lang_code = language
    else:
        lang_code = detect_question_language(text)
    lang_name = language_display_name(lang_code)
    content = await chat_completion(
        [
            {
                "role": "system",
                "content": (
                    "You correct spelling and grammar. "
                    f"Write explanations in {lang_name}. Keep the same language as the input text. "
                    'JSON: {"corrected_text":"...","explanations":["..."]}'
                ),
            },
            {
                "role": "user",
                "content": f"Language: {lang_name}\nText:\n{text}",
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
    doc = db.get(Document, document_id)
    title = doc.title if doc else ""
    chunks = await retrieve_chunks(
        db,
        organization_id,
        title or "reading comprehension",
        document_id=document_id,
        top_k=6,
    )
    if not chunks:
        raise ValueError("Document non indexé")
    context = "\n\n".join(c.content for c in chunks)
    lang_name = language_display_name(detect_content_language(title, context[:1500]))
    last_error: Exception | None = None
    for attempt in range(2):
        content = await chat_completion(
            [
                {
                    "role": "system",
                    "content": (
                        "Generate a reading-comprehension exercise from the context only. "
                        f"The passage, questions, choices and explanations MUST be in {lang_name}. "
                        "Return valid compact JSON only, with double quotes and no trailing commas. "
                        'JSON: {"passage":"...","questions":[{"id":"q1","stem":"...",'
                        '"choices":["A","B","C","D"],"correct_index":0,"explanation":"..."}]}'
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Context:\n{context[:3500]}\n\n"
                        f"Number of questions: {question_count}\nLanguage: {lang_name}"
                    ),
                },
            ],
            temperature=0.2 if attempt else 0.3,
            format_json=True,
        )
        try:
            parsed = parse_json_response(content)
            if isinstance(parsed, dict) and parsed.get("questions"):
                return parsed
            last_error = ValueError("JSON compréhension incomplet")
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise last_error or ValueError("JSON compréhension invalide")


def whisper_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        return False
    return True


def tokenize_words(text: str) -> list[str]:
    return [match.group(0).lower() for match in _WORD_RE.finditer(text or "")]


def analyze_pronunciation(
    reference_text: str,
    transcript: str,
    *,
    engine: str,
) -> dict[str, Any]:
    lang_code = detect_question_language(reference_text)
    ref_words = tokenize_words(reference_text)
    hyp_words = tokenize_words(transcript)
    matcher = SequenceMatcher(a=ref_words, b=hyp_words, autojunk=False)

    aligned: list[dict[str, str]] = []
    missed: list[str] = []
    extra: list[str] = []
    replaced: list[str] = []
    matched = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for word in ref_words[i1:i2]:
                aligned.append({"word": word, "status": "match"})
                matched += 1
        elif tag == "delete":
            for word in ref_words[i1:i2]:
                aligned.append({"word": word, "status": "missed"})
                missed.append(word)
        elif tag == "insert":
            for word in hyp_words[j1:j2]:
                aligned.append({"word": word, "status": "extra"})
                extra.append(word)
        elif tag == "replace":
            for word in ref_words[i1:i2]:
                aligned.append({"word": word, "status": "replaced"})
                replaced.append(word)
            extra.extend(hyp_words[j1:j2])

    total = max(len(ref_words), 1)
    accuracy = matched / total
    error_count = len(missed) + len(extra) + len(replaced)
    fluency = max(0.0, 1.0 - error_count / max(len(ref_words) + len(hyp_words), 1))
    practice = missed + replaced
    return {
        "transcript": transcript,
        "accuracy": round(accuracy, 3),
        "fluency": round(fluency, 3),
        "matched_words": matched,
        "total_words": len(ref_words),
        "missed_words": missed,
        "extra_words": extra,
        "replaced_words": replaced,
        "words": aligned,
        "language": lang_code,
        "feedback": pronunciation_feedback(accuracy, lang_code),
        "shadowing_text": " ".join(practice) if practice else (reference_text or "").strip(),
        "shadowing_tip": shadowing_tip(lang_code, practice),
        "engine": engine,
    }


def analyze_pronunciation_stub(reference_text: str, transcript: str) -> dict[str, Any]:
    """Backward-compatible alias used by older tests."""
    engine = "faster-whisper" if transcript and not transcript.startswith("(") else "unavailable"
    return analyze_pronunciation(reference_text, transcript, engine=engine)


async def transcribe_audio(file_path: str, language: str | None = None) -> str:
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError:
        return ""

    model = WhisperModel("base", device="cpu", compute_type="int8")
    kwargs: dict[str, Any] = {}
    whisper_lang = whisper_language_code(language) if language else None
    if whisper_lang:
        kwargs["language"] = whisper_lang
    segments, _ = model.transcribe(file_path, **kwargs)
    return " ".join(seg.text.strip() for seg in segments).strip()
