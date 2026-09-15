"""Tests for class-session API schemas."""

from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from skillpulse.schemas.class_sessions import (
    ClassSessionCreate,
    ClassSessionResponse,
    ClassSessionUpdate,
    SessionStatus,
)

_TOPIC_ID = "41000000-0000-0000-0000-000000000001"

_VALID_CREATE_PAYLOAD = {
    "topic_id": _TOPIC_ID,
    "title": "VPC foundations",
    "scheduled_start": "2026-09-15T09:00:00+01:00",
    "scheduled_end": "2026-09-15T11:00:00+01:00",
    "delivery_link": "https://meet.example.com/vpc-foundations",
}


def test_create_strips_title_and_defaults_to_scheduled() -> None:
    payload = {
        **_VALID_CREATE_PAYLOAD,
        "title": "  VPC foundations  ",
    }

    session = ClassSessionCreate.model_validate(payload)

    assert session.topic_id == UUID(_TOPIC_ID)
    assert session.title == "VPC foundations"
    assert session.status is SessionStatus.SCHEDULED
    assert session.recording_url is None
    assert session.scheduled_start.utcoffset() is not None


@pytest.mark.parametrize(
    "scheduled_end",
    [
        "2026-09-15T09:00:00+01:00",
        "2026-09-15T08:59:59+01:00",
    ],
)
def test_create_rejects_non_positive_duration(
    scheduled_end: str,
) -> None:
    payload = {
        **_VALID_CREATE_PAYLOAD,
        "scheduled_end": scheduled_end,
    }

    with pytest.raises(
        ValidationError,
        match="scheduled_end must be after scheduled_start",
    ):
        ClassSessionCreate.model_validate(payload)


@pytest.mark.parametrize(
    "field_name",
    [
        "scheduled_start",
        "scheduled_end",
    ],
)
def test_create_rejects_naive_timestamps(
    field_name: str,
) -> None:
    payload = dict(_VALID_CREATE_PAYLOAD)
    payload[field_name] = "2026-09-15T10:00:00"

    with pytest.raises(
        ValidationError,
        match="must include a timezone",
    ):
        ClassSessionCreate.model_validate(payload)


@pytest.mark.parametrize(
    "field_name",
    [
        "delivery_link",
        "recording_url",
    ],
)
def test_create_rejects_non_http_urls(
    field_name: str,
) -> None:
    payload = {
        **_VALID_CREATE_PAYLOAD,
        field_name: "ftp://files.example.com/session",
    }

    with pytest.raises(ValidationError):
        ClassSessionCreate.model_validate(payload)


def test_create_rejects_unknown_fields() -> None:
    payload = {
        **_VALID_CREATE_PAYLOAD,
        "organization_id": "10000000-0000-0000-0000-000000000001",
    }

    with pytest.raises(
        ValidationError,
        match="Extra inputs are not permitted",
    ):
        ClassSessionCreate.model_validate(payload)


def test_create_rejects_unknown_status() -> None:
    payload = {
        **_VALID_CREATE_PAYLOAD,
        "status": "running",
    }

    with pytest.raises(ValidationError):
        ClassSessionCreate.model_validate(payload)


def test_update_requires_explicit_status() -> None:
    with pytest.raises(ValidationError, match="status"):
        ClassSessionUpdate.model_validate(_VALID_CREATE_PAYLOAD)


def test_update_accepts_complete_replacement() -> None:
    payload = {
        **_VALID_CREATE_PAYLOAD,
        "recording_url": "https://recordings.example.com/vpc-foundations",
        "status": "completed",
    }

    session = ClassSessionUpdate.model_validate(payload)

    assert session.status is SessionStatus.COMPLETED
    assert session.recording_url == (
        "https://recordings.example.com/vpc-foundations"
    )


def test_response_validates_database_record() -> None:
    payload = {
        **_VALID_CREATE_PAYLOAD,
        "id": "43000000-0000-0000-0000-000000000001",
        "cohort_id": "42000000-0000-0000-0000-000000000001",
        "status": "scheduled",
        "created_at": datetime(2026, 9, 13, 10, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 9, 13, 10, 0, tzinfo=UTC),
    }

    session = ClassSessionResponse.model_validate(payload)

    assert session.id == UUID(
        "43000000-0000-0000-0000-000000000001"
    )
    assert session.cohort_id == UUID(
        "42000000-0000-0000-0000-000000000001"
    )
    assert session.status is SessionStatus.SCHEDULED
