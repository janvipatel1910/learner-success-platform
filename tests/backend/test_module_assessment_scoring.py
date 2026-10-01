"""Server-side module check grading tests."""

from decimal import Decimal

import pytest

from skillpulse.core.module_assessment import (
    InvalidAnswers,
    InvalidAssessment,
    grade_module_check,
)


def question(question_id="q1", marks="1"):
    return {
        "id": question_id,
        "question_type": "single_choice",
        "options_json": ["Option A", "Option B"],
        "correct_answer_json": ["Option B"],
        "marks": Decimal(marks),
    }


def test_correct_answer_passes():
    result = grade_module_check(
        [question()], {"q1": ["Option B"]}, Decimal("100")
    )
    assert result["passed"] is True
    assert result["percentage"] == Decimal("100.00")
    assert result["responses"][0]["marks_awarded"] == Decimal("1")


def test_wrong_answer_fails():
    result = grade_module_check(
        [question()], {"q1": ["Option A"]}, Decimal("100")
    )
    assert result["passed"] is False
    assert result["score"] == 0


@pytest.mark.parametrize(
    "answers",
    [
        {},
        {"q1": ["Option B"], "extra": ["Option B"]},
        {"q1": []},
        {"q1": ["Option A", "Option B"]},
        {"q1": ["Invented option"]},
    ],
)
def test_invalid_submissions_are_rejected(answers):
    with pytest.raises(InvalidAnswers):
        grade_module_check([question()], answers, Decimal("100"))


def test_weighted_marks_and_unrounded_pass_threshold():
    result = grade_module_check(
        [question("q1", "2"), question("q2", "1")],
        {"q1": ["Option B"], "q2": ["Option A"]},
        Decimal("66.67"),
    )
    assert result["score"] == Decimal("2")
    assert result["percentage"] == Decimal("66.67")
    assert result["passed"] is False


def test_invalid_answer_key_is_rejected():
    broken = question()
    broken["correct_answer_json"] = ["Missing option"]
    with pytest.raises(InvalidAssessment):
        grade_module_check(
            [broken], {"q1": ["Option B"]}, Decimal("100")
        )


def test_duplicate_questions_are_rejected():
    with pytest.raises(InvalidAssessment):
        grade_module_check(
            [question(), question()],
            {"q1": ["Option B"]},
            Decimal("100"),
        )
