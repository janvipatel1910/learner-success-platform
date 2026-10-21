"""Server-side grading for practice quizzes and timed mock exams.

Unlike module checks, practice attempts allow unanswered questions (they
score zero, which matters when a timed exam runs out) and support
multiple-choice questions such as "Choose two".
"""

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation

from skillpulse.core.module_assessment import InvalidAnswers, InvalidAssessment

__all__ = [
    "InvalidAnswers",
    "InvalidAssessment",
    "grade_assessment",
    "validate_question",
]


def _marks(question: Mapping[str, object]) -> Decimal:
    try:
        marks = Decimal(str(question["marks"]))
    except InvalidOperation as exc:
        raise InvalidAssessment("Invalid question marks.") from exc
    if not marks.is_finite() or marks <= 0:
        raise InvalidAssessment("Invalid question marks.")
    return marks


def validate_question(question: Mapping[str, object]) -> None:
    """Reject question configuration that cannot be graded safely."""
    options = question["options_json"]
    correct = question["correct_answer_json"]
    question_type = question["question_type"]

    if (
        not isinstance(options, list)
        or len(options) < 2
        or not all(isinstance(option, str) for option in options)
        or len(set(options)) != len(options)
    ):
        raise InvalidAssessment("Invalid question options.")

    if (
        not isinstance(correct, list)
        or not correct
        or len(set(correct)) != len(correct)
        or not all(answer in options for answer in correct)
    ):
        raise InvalidAssessment("Invalid answer key.")

    if question_type == "single_choice":
        if len(correct) != 1:
            raise InvalidAssessment("Single-choice questions need one answer.")
    elif question_type == "multiple_choice":
        if not 2 <= len(correct) < len(options):
            raise InvalidAssessment("Invalid multiple-choice answer key.")
    else:
        raise InvalidAssessment("Unsupported question type.")

    _marks(question)


def grade_assessment(
    questions: Sequence[Mapping[str, object]],
    answers: Mapping[str, list[str]],
    pass_percentage: Decimal,
) -> dict[str, object]:
    """Grade an attempt using server-owned answer keys and marks.

    A question is correct only when the selected set exactly matches the
    answer key. Unanswered questions are recorded with no selection.
    """
    if not questions:
        raise InvalidAssessment("Assessment has no questions.")

    try:
        threshold = Decimal(str(pass_percentage))
    except InvalidOperation as exc:
        raise InvalidAssessment("Invalid pass percentage.") from exc
    if not threshold.is_finite() or not 0 <= threshold <= 100:
        raise InvalidAssessment("Invalid pass percentage.")

    question_ids = [str(question["id"]) for question in questions]
    if len(set(question_ids)) != len(question_ids):
        raise InvalidAssessment("Assessment has duplicate questions.")

    unknown = set(answers) - set(question_ids)
    if unknown:
        raise InvalidAnswers("Answers include questions not in this attempt.")

    score = Decimal("0")
    maximum_score = Decimal("0")
    responses = []

    for question in questions:
        validate_question(question)
        question_id = str(question["id"])
        options = question["options_json"]
        correct = question["correct_answer_json"]
        marks = _marks(question)
        maximum_score += marks

        selected = answers.get(question_id)
        if selected is None or selected == []:
            responses.append({
                "question_id": question_id,
                "selected_answer_json": None,
                "is_correct": False,
                "marks_awarded": Decimal("0"),
            })
            continue

        if (
            not isinstance(selected, list)
            or len(set(selected)) != len(selected)
            or not all(option in options for option in selected)
        ):
            raise InvalidAnswers("Select only valid options, once each.")

        if question["question_type"] == "single_choice" and len(selected) != 1:
            raise InvalidAnswers("Select one option for single-choice questions.")

        if (
            question["question_type"] == "multiple_choice"
            and len(selected) > len(correct)
        ):
            raise InvalidAnswers(
                f"Select at most {len(correct)} options for this question."
            )

        is_correct = set(selected) == set(correct)
        awarded = marks if is_correct else Decimal("0")
        score += awarded
        responses.append({
            "question_id": question_id,
            "selected_answer_json": list(selected),
            "is_correct": is_correct,
            "marks_awarded": awarded,
        })

    percentage = score * Decimal("100") / maximum_score

    return {
        "score": score,
        "percentage": percentage.quantize(Decimal("0.01")),
        # Compare before rounding to avoid promoting a near miss.
        "passed": percentage >= threshold,
        "responses": responses,
    }
