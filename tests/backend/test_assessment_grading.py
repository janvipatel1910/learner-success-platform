"""Grading rules for practice quizzes and mock exams."""

from decimal import Decimal

import pytest

from skillpulse.core.assessment_grading import (
    InvalidAnswers,
    InvalidAssessment,
    grade_assessment,
)


def question(identifier, correct, *, question_type=None, options=None, marks=1):
    options = options or ["A", "B", "C", "D"]
    return {
        "id": identifier,
        "question_type": question_type
        or ("single_choice" if len(correct) == 1 else "multiple_choice"),
        "options_json": options,
        "correct_answer_json": correct,
        "marks": marks,
    }


def test_single_and_multiple_choice_are_marked_by_exact_match():
    questions = [
        question("q1", ["B"]),
        question("q2", ["A", "C"]),
        question("q3", ["A", "D"]),
    ]

    result = grade_assessment(
        questions,
        {"q1": ["B"], "q2": ["C", "A"], "q3": ["A"]},
        Decimal("60"),
    )

    assert [r["is_correct"] for r in result["responses"]] == [True, True, False]
    assert result["score"] == Decimal("2")
    assert result["percentage"] == Decimal("66.67")
    assert result["passed"] is True


def test_unanswered_questions_score_zero_and_are_recorded_empty():
    questions = [question("q1", ["A"]), question("q2", ["B"])]

    result = grade_assessment(questions, {"q1": ["A"]}, Decimal("70"))

    assert result["responses"][1] == {
        "question_id": "q2",
        "selected_answer_json": None,
        "is_correct": False,
        "marks_awarded": Decimal("0"),
    }
    assert result["percentage"] == Decimal("50.00")
    assert result["passed"] is False


def test_pass_mark_compares_before_rounding():
    questions = [question(f"q{i}", ["A"]) for i in range(3)]

    result = grade_assessment(
        questions, {"q0": ["A"], "q1": ["A"]}, Decimal("66.67")
    )

    assert result["percentage"] == Decimal("66.67")
    assert result["passed"] is False


def test_marks_are_weighted():
    questions = [question("q1", ["A"], marks=3), question("q2", ["A"], marks=1)]

    result = grade_assessment(questions, {"q1": ["A"]}, Decimal("70"))

    assert result["score"] == Decimal("3")
    assert result["percentage"] == Decimal("75.00")


@pytest.mark.parametrize(
    "answers",
    [
        {"unknown": ["A"]},
        {"q1": ["Z"]},
        {"q1": ["A", "A"]},
        {"q1": ["A", "B"]},
        {"q2": ["A", "B", "C"]},
    ],
)
def test_invalid_answers_are_rejected(answers):
    questions = [question("q1", ["A"]), question("q2", ["A", "B"])]

    with pytest.raises(InvalidAnswers):
        grade_assessment(questions, answers, Decimal("70"))


@pytest.mark.parametrize(
    "bad_question",
    [
        question("q1", ["Z"]),
        question("q1", ["A", "B"], question_type="single_choice"),
        question("q1", ["A"], question_type="multiple_choice"),
        question("q1", ["A", "B", "C", "D"]),
        question("q1", ["A"], options=["A", "A"]),
        question("q1", ["A"], marks=0),
        {**question("q1", ["A"]), "question_type": "essay"},
    ],
)
def test_invalid_configuration_is_rejected(bad_question):
    with pytest.raises(InvalidAssessment):
        grade_assessment([bad_question], {}, Decimal("70"))


def test_empty_and_duplicate_assessments_are_rejected():
    with pytest.raises(InvalidAssessment):
        grade_assessment([], {}, Decimal("70"))

    with pytest.raises(InvalidAssessment):
        grade_assessment(
            [question("q1", ["A"]), question("q1", ["A"])], {}, Decimal("70")
        )


def test_invalid_pass_percentage_is_rejected():
    with pytest.raises(InvalidAssessment):
        grade_assessment([question("q1", ["A"])], {}, Decimal("101"))
