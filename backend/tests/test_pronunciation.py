from app.services.languages import analyze_pronunciation, tokenize_words
from app.services.question_language import pronunciation_feedback, shadowing_tip


def test_tokenize_keeps_words_without_punctuation() -> None:
    assert tokenize_words("Put off the meeting!") == ["put", "off", "the", "meeting"]


def test_pronunciation_detects_missed_and_replaced_words() -> None:
    result = analyze_pronunciation(
        "A phrasal verb is a verb plus a particle",
        "A phrasal verb is a verb plus a particule",
        engine="manual",
    )
    assert result["language"] == "en"
    assert "particle" in result["missed_words"] or "particle" in result["replaced_words"]
    assert result["accuracy"] < 1
    assert "Shadowing" in result["shadowing_tip"]
    assert result["engine"] == "manual"


def test_perfect_read_is_full_accuracy() -> None:
    text = "Please put off the meeting until tomorrow."
    result = analyze_pronunciation(text, text, engine="manual")
    assert result["accuracy"] == 1.0
    assert result["missed_words"] == []
    assert result["feedback"] == pronunciation_feedback(1.0, "en")
    assert "Listen to the model" in shadowing_tip("en", [])
