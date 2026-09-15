"""Organisation-scoped database operations for class sessions."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from skillpulse.db.connection import get_engine
from skillpulse.schemas.class_sessions import (
    ClassSessionCreate,
    ClassSessionResponse,
    ClassSessionUpdate,
)

_COUNT_CLASS_SESSIONS = text(
    """
    SELECT COUNT(*)
    FROM class_sessions AS cs
    JOIN cohorts AS h
        ON h.id = cs.cohort_id
    JOIN courses AS c
        ON c.id = h.course_id
    WHERE
        h.id = :cohort_id
        AND h.course_id = :course_id
        AND c.organization_id = :organization_id
    """
)

_LIST_CLASS_SESSIONS = text(
    """
    SELECT
        cs.id,
        cs.cohort_id,
        cs.topic_id,
        cs.title,
        cs.scheduled_start,
        cs.scheduled_end,
        cs.delivery_link,
        cs.recording_url,
        cs.status::TEXT AS status,
        cs.created_at,
        cs.updated_at
    FROM class_sessions AS cs
    JOIN cohorts AS h
        ON h.id = cs.cohort_id
    JOIN courses AS c
        ON c.id = h.course_id
    WHERE
        h.id = :cohort_id
        AND h.course_id = :course_id
        AND c.organization_id = :organization_id
    ORDER BY cs.scheduled_start, cs.id
    LIMIT :limit
    OFFSET :offset
    """
)

_GET_CLASS_SESSION = text(
    """
    SELECT
        cs.id,
        cs.cohort_id,
        cs.topic_id,
        cs.title,
        cs.scheduled_start,
        cs.scheduled_end,
        cs.delivery_link,
        cs.recording_url,
        cs.status::TEXT AS status,
        cs.created_at,
        cs.updated_at
    FROM class_sessions AS cs
    JOIN cohorts AS h
        ON h.id = cs.cohort_id
    JOIN courses AS c
        ON c.id = h.course_id
    WHERE
        cs.id = :session_id
        AND h.id = :cohort_id
        AND h.course_id = :course_id
        AND c.organization_id = :organization_id
    """
)

_CREATE_CLASS_SESSION = text(
    """
    INSERT INTO class_sessions (
        cohort_id,
        topic_id,
        title,
        scheduled_start,
        scheduled_end,
        delivery_link,
        recording_url,
        status
    )
    SELECT
        h.id,
        t.id,
        :title,
        :scheduled_start,
        :scheduled_end,
        :delivery_link,
        :recording_url,
        CAST(:status AS session_status)
    FROM cohorts AS h
    JOIN courses AS c
        ON c.id = h.course_id
    JOIN topics AS t
        ON t.course_id = c.id
        AND t.id = :topic_id
    WHERE
        h.id = :cohort_id
        AND h.course_id = :course_id
        AND c.organization_id = :organization_id
    RETURNING id
    """
)

_UPDATE_CLASS_SESSION = text(
    """
    UPDATE class_sessions AS cs
    SET
        topic_id = t.id,
        title = :title,
        scheduled_start = :scheduled_start,
        scheduled_end = :scheduled_end,
        delivery_link = :delivery_link,
        recording_url = :recording_url,
        status = CAST(:status AS session_status),
        updated_at = NOW()
    FROM cohorts AS h
    JOIN courses AS c
        ON c.id = h.course_id
    JOIN topics AS t
        ON t.course_id = c.id
        AND t.id = :topic_id
    WHERE
        cs.id = :session_id
        AND cs.cohort_id = h.id
        AND h.id = :cohort_id
        AND h.course_id = :course_id
        AND c.organization_id = :organization_id
    RETURNING cs.id
    """
)


def _class_session_from_row(
    row: RowMapping,
) -> ClassSessionResponse:
    """Convert a trusted database row into an API model."""

    return ClassSessionResponse.model_validate(row)


def _fetch_class_session(
    connection: Connection,
    parameters: dict[str, object],
) -> ClassSessionResponse | None:
    """Fetch one class session using an existing connection."""

    row = (
        connection.execute(
            _GET_CLASS_SESSION,
            parameters,
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None

    return _class_session_from_row(row)


def list_class_sessions(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    *,
    limit: int,
    offset: int,
) -> tuple[list[ClassSessionResponse], int]:
    """Return one page of sessions from an organisation-owned cohort."""

    parameters = {
        "organization_id": organization_id,
        "course_id": course_id,
        "cohort_id": cohort_id,
        "limit": limit,
        "offset": offset,
    }

    with get_engine().connect() as connection:
        total = connection.execute(
            _COUNT_CLASS_SESSIONS,
            parameters,
        ).scalar_one()
        rows = connection.execute(
            _LIST_CLASS_SESSIONS,
            parameters,
        ).mappings()
        sessions = [
            _class_session_from_row(row)
            for row in rows
        ]

    return sessions, total


def get_class_session(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    session_id: UUID,
) -> ClassSessionResponse | None:
    """Return a scoped session without exposing another organisation."""

    parameters = {
        "organization_id": organization_id,
        "course_id": course_id,
        "cohort_id": cohort_id,
        "session_id": session_id,
    }

    with get_engine().connect() as connection:
        return _fetch_class_session(
            connection,
            parameters,
        )


def create_class_session(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    payload: ClassSessionCreate,
) -> ClassSessionResponse | None:
    """Create a session when its cohort and topic share a course."""

    parameters = payload.model_dump(mode="python")
    parameters.update(
        {
            "organization_id": organization_id,
            "course_id": course_id,
            "cohort_id": cohort_id,
        }
    )

    with get_engine().begin() as connection:
        session_id = connection.execute(
            _CREATE_CLASS_SESSION,
            parameters,
        ).scalar_one_or_none()
        if session_id is None:
            return None

        parameters["session_id"] = session_id
        return _fetch_class_session(
            connection,
            parameters,
        )


def update_class_session(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    session_id: UUID,
    payload: ClassSessionUpdate,
) -> ClassSessionResponse | None:
    """Update a scoped session after validating its replacement topic."""

    parameters = payload.model_dump(mode="python")
    parameters.update(
        {
            "organization_id": organization_id,
            "course_id": course_id,
            "cohort_id": cohort_id,
            "session_id": session_id,
        }
    )

    with get_engine().begin() as connection:
        updated_id = connection.execute(
            _UPDATE_CLASS_SESSION,
            parameters,
        ).scalar_one_or_none()
        if updated_id is None:
            return None

        return _fetch_class_session(
            connection,
            parameters,
        )
