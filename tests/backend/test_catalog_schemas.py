from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from skillpulse.schemas.catalog import (
    CohortCreate,
    CohortStatus,
    CourseCreate,
    CourseStatus,
    DeliveryMode,
    TopicCreate,
)


def test_course_create_strips_text_and_defaults_to_draft() -> None:
    course = CourseCreate(
        title="  AWS Solutions Architect  ",
        code="  AWS-SAA  ",
        description="  Certification preparation  ",
    )

    assert course.title == "AWS Solutions Architect"
    assert course.code == "AWS-SAA"
    assert course.description == "Certification preparation"
    assert course.status is CourseStatus.DRAFT


def test_course_code_rejects_spaces() -> None:
    with pytest.raises(ValidationError):
        CourseCreate(
            title="AWS Course",
            code="AWS SAA",
        )


def test_course_payload_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        CourseCreate.model_validate(
            {
                "title": "AWS Course",
                "code": "AWS-SAA",
                "organization_id": (
                    "10000000-0000-0000-0000-000000000001"
                ),
            }
        )


@pytest.mark.parametrize(
    "payload",
    [
        {
            "title": "Invalid sequence",
            "sequence_number": 0,
        },
        {
            "title": "Invalid duration",
            "sequence_number": 1,
            "expected_hours": Decimal("0"),
        },
    ],
)
def test_topic_rejects_non_positive_values(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        TopicCreate.model_validate(payload)


def test_cohort_rejects_end_date_before_start_date() -> None:
    with pytest.raises(
        ValidationError,
        match="end_date must be on or after start_date",
    ):
        CohortCreate(
            name="Invalid Cohort",
            start_date=date(2026, 9, 30),
            end_date=date(2026, 9, 1),
            delivery_mode=DeliveryMode.ONLINE,
        )


def test_cohort_create_uses_controlled_enums_and_default_status() -> None:
    cohort = CohortCreate(
        name="  September Cohort  ",
        start_date=date(2026, 9, 1),
        end_date=date(2026, 12, 1),
        delivery_mode="hybrid",
    )

    assert cohort.name == "September Cohort"
    assert cohort.delivery_mode is DeliveryMode.HYBRID
    assert cohort.status is CohortStatus.PLANNED
