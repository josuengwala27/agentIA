from app.services.question_language import (
    detect_question_language,
    fallback_message,
    language_display_name,
)


def test_detects_english_question() -> None:
    assert detect_question_language("What is a phrasal verb?") == "en"


def test_detects_french_question() -> None:
    assert detect_question_language("Qu'est-ce qu'un verbe phrasal ?") == "fr"


def test_detects_spanish_question() -> None:
    assert detect_question_language("¿Qué es un phrasal verb y cómo se usa?") == "es"


def test_detects_arabic_script() -> None:
    assert detect_question_language("ما هو الفعل المركب؟") == "ar"


def test_empty_defaults_to_french() -> None:
    assert detect_question_language("   ") == "fr"


def test_english_fallback_message() -> None:
    msg = fallback_message("no_indexed", "What is a phrasal verb?")
    assert "indexed content" in msg.lower()
    assert language_display_name("en") == "English"
