from app.models import ExerciseType
from app.services.grading import build_exercise_prompt
from app.services.languages import analyze_pronunciation_stub
from app.services.question_language import (
    default_topic_label,
    detect_content_language,
    pronunciation_feedback,
    whisper_language_code,
)


def test_english_course_is_detected_from_title_and_excerpt() -> None:
    code = detect_content_language(
        "Fundamentals of english grammar",
        "A phrasal verb is a verb and a particle that together have a special meaning.",
    )
    assert code == "en"


def test_qcm_prompt_for_english_material_is_not_forced_to_french() -> None:
    prompt = build_exercise_prompt(ExerciseType.QCM.value, 5, "phrasal verbs", "English")
    assert "in English" in prompt
    assert "en français" not in prompt.lower()


def test_qcm_prompt_for_french_material_stays_french() -> None:
    prompt = build_exercise_prompt(ExerciseType.QCM.value, 5, "prévention", "French")
    assert "in French" in prompt


def test_pronunciation_feedback_follows_reference_language() -> None:
    result = analyze_pronunciation_stub(
        "Please put off the meeting until tomorrow.",
        "Please put off the meeting until tomorrow.",
    )
    assert result["language"] == "en"
    assert result["feedback"] == pronunciation_feedback(1.0, "en")
    assert whisper_language_code("en") == "en"
    assert default_topic_label("en") == "course content"
