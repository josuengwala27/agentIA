"""Detect the learner's question language so the tutor can reply in kind."""

from __future__ import annotations

import re

from app.services.conversation_memory import is_short_followup, prior_user_texts

# Distinctive function words / question words. Overlapping tokens (le/la/de)
# still work because we score the whole message, not a single word.
_MARKERS: dict[str, frozenset[str]] = {
    "fr": frozenset(
        {
            "le",
            "la",
            "les",
            "un",
            "une",
            "des",
            "du",
            "et",
            "est",
            "sont",
            "que",
            "qui",
            "quoi",
            "comment",
            "pourquoi",
            "quand",
            "où",
            "dans",
            "pour",
            "avec",
            "sur",
            "pas",
            "plus",
            "cette",
            "cet",
            "ces",
            "c'est",
            "qu'est",
            "qu'est-ce",
            "s'il",
            "n'est",
            "être",
            "fait",
            "peux",
            "peut",
            "explique",
            "expliques",
            "définition",
        }
    ),
    "en": frozenset(
        {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "what",
            "why",
            "how",
            "when",
            "where",
            "which",
            "who",
            "does",
            "do",
            "did",
            "can",
            "could",
            "would",
            "should",
            "this",
            "that",
            "with",
            "from",
            "about",
            "please",
            "explain",
            "mean",
            "means",
            "difference",
            "between",
        }
    ),
    "es": frozenset(
        {
            "el",
            "los",
            "las",
            "una",
            "qué",
            "que",
            "cómo",
            "como",
            "por",
            "para",
            "está",
            "están",
            "cuál",
            "dónde",
            "explica",
            "significa",
            "diferencia",
        }
    ),
    "de": frozenset(
        {
            "der",
            "die",
            "das",
            "und",
            "ist",
            "sind",
            "was",
            "wie",
            "warum",
            "wo",
            "welche",
            "ein",
            "eine",
            "nicht",
            "mit",
            "erklären",
            "bedeutet",
        }
    ),
    "it": frozenset(
        {
            "il",
            "lo",
            "gli",
            "una",
            "che",
            "cosa",
            "cos'è",
            "come",
            "perché",
            "dove",
            "quale",
            "non",
            "con",
            "spiega",
            "significa",
        }
    ),
    "pt": frozenset(
        {
            "uma",
            "os",
            "as",
            "não",
            "que",
            "qual",
            "como",
            "por",
            "está",
            "são",
            "onde",
            "explica",
            "significa",
        }
    ),
}

_LANG_NAMES: dict[str, str] = {
    "fr": "French",
    "en": "English",
    "es": "Spanish",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ar": "Arabic",
    "zh": "Chinese",
    "ru": "Russian",
}

_FALLBACKS: dict[str, dict[str, str]] = {
    "fr": {
        "no_indexed": (
            "Je n'ai trouvé aucun contenu indexé pour répondre. "
            "Demandez à un formateur d'importer des supports pédagogiques."
        ),
        "no_chunks": (
            "Le document est indexé mais aucun passage pertinent n'a pu être récupéré. "
            "Réessayez, ou ré-importez le support."
        ),
    },
    "en": {
        "no_indexed": (
            "I could not find any indexed content to answer. "
            "Please ask a trainer to import course materials."
        ),
        "no_chunks": (
            "The document is indexed but no relevant passage could be retrieved. "
            "Try again, or re-import the material."
        ),
    },
    "es": {
        "no_indexed": (
            "No encontré contenido indexado para responder. "
            "Pide a un formador que importe materiales pedagógicos."
        ),
        "no_chunks": (
            "El documento está indexado pero no se pudo recuperar ningún pasaje pertinente. "
            "Inténtalo de nuevo o vuelve a importar el material."
        ),
    },
    "de": {
        "no_indexed": (
            "Ich habe keine indexierten Inhalte gefunden, um zu antworten. "
            "Bitte bitten Sie eine Lehrkraft, Lernunterlagen zu importieren."
        ),
        "no_chunks": (
            "Das Dokument ist indexiert, aber es konnte keine passende Passage gefunden werden. "
            "Versuchen Sie es erneut oder importieren Sie das Material erneut."
        ),
    },
    "it": {
        "no_indexed": (
            "Non ho trovato contenuti indicizzati per rispondere. "
            "Chiedi a un formatore di importare i materiali didattici."
        ),
        "no_chunks": (
            "Il documento è indicizzato ma non è stato possibile recuperare un passaggio pertinente. "
            "Riprova oppure reimporta il materiale."
        ),
    },
    "pt": {
        "no_indexed": (
            "Não encontrei conteúdo indexado para responder. "
            "Peça a um formador para importar materiais pedagógicos."
        ),
        "no_chunks": (
            "O documento está indexado, mas nenhum trecho pertinente pôde ser recuperado. "
            "Tente novamente ou reimporte o material."
        ),
    },
    "ar": {
        "no_indexed": (
            "لم أجد أي محتوى مفهرس للإجابة. "
            "اطلب من المدرّب استيراد مواد تعليمية."
        ),
        "no_chunks": (
            "المستند مفهرس لكن تعذر استرجاع مقطع مناسب. "
            "حاول مرة أخرى أو أعد استيراد المادة."
        ),
    },
    "zh": {
        "no_indexed": "未找到可用于回答的已索引内容。请让培训师导入教材。",
        "no_chunks": "文档已索引，但未能检索到相关段落。请重试或重新导入教材。",
    },
    "ru": {
        "no_indexed": (
            "Я не нашёл проиндексированного содержимого для ответа. "
            "Попросите преподавателя загрузить учебные материалы."
        ),
        "no_chunks": (
            "Документ проиндексирован, но подходящий фрагмент не удалось получить. "
            "Попробуйте ещё раз или загрузите материал заново."
        ),
    },
}

_TOKEN_RE = re.compile(r"[a-zàâäáãåéèêëíìîïóòôöõúùûüçñß']+", re.IGNORECASE)


def detect_question_language(text: str) -> str:
    """Return a short language code inferred from the learner question."""
    raw = (text or "").strip()
    if not raw:
        return "fr"

    if re.search(r"[\u0600-\u06FF]", raw):
        return "ar"
    if re.search(r"[\u4e00-\u9fff]", raw):
        return "zh"
    if re.search(r"[\u0400-\u04FF]", raw):
        return "ru"

    tokens = [t.lower() for t in _TOKEN_RE.findall(raw)]
    if not tokens:
        return "fr"

    scores = {code: sum(1 for t in tokens if t in words) for code, words in _MARKERS.items()}
    best_code, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score == 0:
        return "fr"

    tied = [code for code, score in scores.items() if score == best_score]
    if len(tied) == 1:
        return best_code

    # Prefer the language with the highest density of markers among ties.
    density = {
        code: scores[code] / max(1, len(tokens))
        for code in tied
    }
    return max(density.items(), key=lambda item: item[1])[0]


def language_display_name(code: str) -> str:
    return _LANG_NAMES.get(code, "the same language as the question")


def detect_content_language(*parts: str | None) -> str:
    """Infer language from titles, topics or source excerpts."""
    combined = " ".join(part.strip() for part in parts if part and part.strip())
    return detect_question_language(combined)


def whisper_language_code(code: str) -> str | None:
    """ISO code accepted by faster-whisper, or None to let Whisper auto-detect."""
    if code in _LANG_NAMES:
        return code
    return None


def default_topic_label(code: str) -> str:
    labels = {
        "fr": "contenu du cours",
        "en": "course content",
        "es": "contenido del curso",
        "de": "Kursinhalt",
        "it": "contenuto del corso",
        "pt": "conteúdo do curso",
        "ar": "محتوى الدورة",
        "zh": "课程内容",
        "ru": "содержание курса",
    }
    return labels.get(code, "course content")


def pronunciation_feedback(accuracy: float, code: str) -> str:
    if accuracy >= 0.8:
        messages = {
            "fr": "Bonne fluidité globale.",
            "en": "Good overall fluency.",
            "es": "Buena fluidez general.",
            "de": "Gute allgemeine Flüssigkeit.",
            "it": "Buona fluidità complessiva.",
            "pt": "Boa fluência geral.",
            "ar": "طلاقة عامة جيدة.",
            "zh": "整体流畅度良好。",
            "ru": "Хорошая общая беглость.",
        }
    else:
        messages = {
            "fr": "Répétez lentement les mots non reconnus et travaillez la liaison.",
            "en": "Repeat slowly the words that were not recognized and practise linking.",
            "es": "Repite despacio las palabras no reconocidas.",
            "de": "Wiederholen Sie die nicht erkannten Wörter langsam.",
            "it": "Ripeti lentamente le parole non riconosciute.",
            "pt": "Repita lentamente as palavras não reconhecidas.",
            "ar": "أعد ببطء الكلمات غير المعروفة.",
            "zh": "请放慢速度重复未被识别的词语。",
            "ru": "Медленно повторите нераспознанные слова.",
        }
    return messages.get(code) or messages["en"]


def shadowing_tip(code: str, practice_words: list[str]) -> str:
    joined = " · ".join(practice_words) if practice_words else ""
    if not joined:
        tips = {
            "fr": "Écoutez le modèle, puis répétez la phrase entière au même rythme.",
            "en": "Listen to the model, then repeat the whole sentence at the same pace.",
            "es": "Escucha el modelo y luego repite la frase al mismo ritmo.",
            "de": "Hören Sie das Modell und wiederholen Sie den Satz im gleichen Tempo.",
            "it": "Ascolta il modello, poi ripeti la frase allo stesso ritmo.",
            "pt": "Ouça o modelo e depois repita a frase no mesmo ritmo.",
            "ar": "استمع إلى النموذج ثم أعد الجملة بنفس الإيقاع.",
            "zh": "先听示范，再按同样节奏重复整句。",
            "ru": "Прослушайте образец, затем повторите фразу в том же темпе.",
        }
        return tips.get(code) or tips["en"]
    tips = {
        "fr": f"Shadowing : écoutez, puis répétez lentement ces mots : {joined}.",
        "en": f"Shadowing: listen, then slowly repeat these words: {joined}.",
        "es": f"Shadowing: escucha y luego repite despacio: {joined}.",
        "de": f"Shadowing: zuhören, dann langsam wiederholen: {joined}.",
        "it": f"Shadowing: ascolta, poi ripeti lentamente: {joined}.",
        "pt": f"Shadowing: ouça e depois repita devagar: {joined}.",
        "ar": f"ظلّ صوتي: استمع ثم أعد ببطء: {joined}.",
        "zh": f"跟读：先听，再慢速重复：{joined}。",
        "ru": f"Shadowing: слушайте, затем медленно повторите: {joined}.",
    }
    return tips.get(code) or tips["en"]


def detect_thread_language(question: str, history: list[dict[str, str]] | None = None) -> str:
    """Prefer the previous user turn when the current message is a short follow-up."""
    users = prior_user_texts(history or [])
    if is_short_followup(question) and users:
        return detect_question_language(users[-1])
    return detect_question_language(question)


def fallback_message(
    key: str,
    question: str,
    history: list[dict[str, str]] | None = None,
) -> str:
    code = detect_thread_language(question, history)
    messages = _FALLBACKS.get(code) or _FALLBACKS["fr"]
    return messages[key]
