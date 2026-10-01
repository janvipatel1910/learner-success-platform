"""Server-side grading for single-choice module checks."""

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation


class InvalidAssessment(ValueError):
    """Assessment configuration cannot be graded safely."""


class InvalidAnswers(ValueError):
    """Submitted answers do not match the assessment."""


def grade_module_check(
    questions: Sequence[Mapping[str, object]],
    answers: Mapping[str, list[str]],
    pass_percentage: Decimal,
) -> dict[str, object]:
    """Grade every question using server-owned answer keys and marks."""
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

    if set(answers) != set(question_ids):
        raise InvalidAnswers("Answer every question exactly once.")

    score = Decimal("0")
    maximum_score = Decimal("0")
    responses = []

    for question in questions:
        question_id = str(question["id"])
        options = question["options_json"]
        correct = question["correct_answer_json"]

        if question["question_type"] != "single_choice":
            raise InvalidAssessment("Only single-choice checks are supported.")

        if (
            not isinstance(options, list)
            or len(options) < 2
            or not all(isinstance(option, str) for option in options)
            or len(set(options)) != len(options)
        ):
            raise InvalidAssessment("Invalid question options.")

        if (
            not isinstance(correct, list)
            or len(correct) != 1
            or correct[0] not in options
        ):
            raise InvalidAssessment("Invalid answer key.")

        try:
            marks = Decimal(str(question["marks"]))
        except InvalidOperation as exc:
            raise InvalidAssessment("Invalid question marks.") from exc

        if not marks.is_finite() or marks <= 0:
            raise InvalidAssessment("Invalid question marks.")

        selected = answers[question_id]
        if (
            not isinstance(selected, list)
            or len(selected) != 1
            or selected[0] not in options
        ):
            raise InvalidAnswers("Select one valid option for each question.")

        is_correct = selected == correct
        awarded = marks if is_correct else Decimal("0")
        score += awarded
        maximum_score += marks

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
