"""Organisation-scoped attendance and understanding database operations."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from skillpulse.db.connection import get_engine
from skillpulse.schemas.session_engagement import (
    AttendanceRecordResponse,
    AttendanceRosterItem,
    AttendanceUpsert,
    UnderstandingCheckResponse,
    UnderstandingCheckUpsert,
    UnderstandingRosterItem,
)

_COUNT_ATTENDANCE_ROSTER = text(
    """
    SELECT COUNT(*)
    FROM class_sessions AS cs
    JOIN cohorts AS h
        ON h.id = cs.cohort_id
    JOIN courses AS c
        ON c.id = h.course_id
    JOIN cohort_memberships AS cm
        ON cm.cohort_id = h.id
        AND cm.cohort_role = 'learner'
        AND cm.status = 'active'
    JOIN users AS u
        ON u.id = cm.user_id
        AND u.status = 'active'
    JOIN organization_memberships AS om
        ON om.organization_id = c.organization_id
        AND om.user_id = u.id
        AND om.role = 'student'
        AND om.status = 'active'
    WHERE
        cs.id = :session_id
        AND h.id = :cohort_id
        AND h.course_id = :course_id
        AND c.organization_id = :organization_id
    """
)

_LIST_ATTENDANCE_ROSTER = text(
    """
    SELECT
        cs.id AS session_id,
        u.id AS learner_id,
        u.email,
        u.full_name,
        ar.id AS attendance_id,
        ar.attendance_status::TEXT AS attendance_status,
        ar.minutes_attended,
        ar.recorded_by,
        ar.recorded_at
    FROM class_sessions AS cs
    JOIN cohorts AS h
        ON h.id = cs.cohort_id
    JOIN courses AS c
        ON c.id = h.course_id
    JOIN cohort_memberships AS cm
        ON cm.cohort_id = h.id
        AND cm.cohort_role = 'learner'
        AND cm.status = 'active'
    JOIN users AS u
        ON u.id = cm.user_id
        AND u.status = 'active'
    JOIN organization_memberships AS om
        ON om.organization_id = c.organization_id
        AND om.user_id = u.id
        AND om.role = 'student'
        AND om.status = 'active'
    LEFT JOIN attendance_records AS ar
        ON ar.session_id = cs.id
        AND ar.learner_id = u.id
    WHERE
        cs.id = :session_id
        AND h.id = :cohort_id
        AND h.course_id = :course_id
        AND c.organization_id = :organization_id
    ORDER BY u.full_name, u.id
    LIMIT :limit
    OFFSET :offset
    """
)

_GET_ATTENDANCE_RECORD = text(
    """
    SELECT
        ar.id,
        ar.session_id,
        ar.learner_id,
        u.email,
        u.full_name,
        ar.attendance_status::TEXT AS attendance_status,
        ar.minutes_attended,
        ar.recorded_by,
        ar.recorded_at,
        ar.created_at,
        ar.updated_at
    FROM attendance_records AS ar
    JOIN class_sessions AS cs
        ON cs.id = ar.session_id
    JOIN cohorts AS h
        ON h.id = cs.cohort_id
    JOIN courses AS c
        ON c.id = h.course_id
    JOIN users AS u
        ON u.id = ar.learner_id
        AND u.status = 'active'
    JOIN organization_memberships AS om
        ON om.organization_id = c.organization_id
        AND om.user_id = u.id
        AND om.role = 'student'
        AND om.status = 'active'
    JOIN cohort_memberships AS cm
        ON cm.cohort_id = h.id
        AND cm.user_id = u.id
        AND cm.cohort_role = 'learner'
        AND cm.status = 'active'
    WHERE
        ar.learner_id = :learner_id
        AND cs.id = :session_id
        AND h.id = :cohort_id
        AND h.course_id = :course_id
        AND c.organization_id = :organization_id
    """
)

_UPSERT_ATTENDANCE_RECORD = text(
    """
    INSERT INTO attendance_records (
        session_id,
        learner_id,
        attendance_status,
        minutes_attended,
        recorded_by,
        recorded_at
    )
    SELECT
        cs.id,
        u.id,
        CAST(:attendance_status AS attendance_status),
        :minutes_attended,
        :recorded_by,
        NOW()
    FROM class_sessions AS cs
    JOIN cohorts AS h
        ON h.id = cs.cohort_id
    JOIN courses AS c
        ON c.id = h.course_id
    JOIN users AS u
        ON u.id = :learner_id
        AND u.status = 'active'
    JOIN organization_memberships AS om
        ON om.organization_id = c.organization_id
        AND om.user_id = u.id
        AND om.role = 'student'
        AND om.status = 'active'
    JOIN cohort_memberships AS cm
        ON cm.cohort_id = h.id
        AND cm.user_id = u.id
        AND cm.cohort_role = 'learner'
        AND cm.status = 'active'
    WHERE
        cs.id = :session_id
        AND cs.status = 'completed'
        AND h.id = :cohort_id
        AND h.course_id = :course_id
        AND c.organization_id = :organization_id
        AND (
            :minutes_attended IS NULL
            OR :minutes_attended <= CEIL(
                EXTRACT(EPOCH FROM (
                    cs.scheduled_end - cs.scheduled_start
                )) / 60
            )
        )
    ON CONFLICT (session_id, learner_id)
    DO UPDATE SET
        attendance_status = EXCLUDED.attendance_status,
        minutes_attended = EXCLUDED.minutes_attended,
        recorded_by = EXCLUDED.recorded_by,
        recorded_at = NOW(),
        updated_at = NOW()
    RETURNING id
    """
)

_COUNT_UNDERSTANDING_ROSTER = text(
    """
    SELECT COUNT(*)
    FROM class_sessions AS cs
    JOIN cohorts AS h
        ON h.id = cs.cohort_id
    JOIN courses AS c
        ON c.id = h.course_id
    JOIN cohort_memberships AS cm
        ON cm.cohort_id = h.id
        AND cm.cohort_role = 'learner'
        AND cm.status = 'active'
    JOIN users AS u
        ON u.id = cm.user_id
        AND u.status = 'active'
    JOIN organization_memberships AS om
        ON om.organization_id = c.organization_id
        AND om.user_id = u.id
        AND om.role = 'student'
        AND om.status = 'active'
    WHERE
        cs.id = :session_id
        AND h.id = :cohort_id
        AND h.course_id = :course_id
        AND c.organization_id = :organization_id
    """
)

_LIST_UNDERSTANDING_ROSTER = text(
    """
    SELECT
        cs.id AS session_id,
        u.id AS learner_id,
        u.email,
        u.full_name,
        uc.id AS understanding_check_id,
        uc.rating::TEXT AS rating,
        uc.confidence_score,
        uc.comment,
        uc.submitted_at
    FROM class_sessions AS cs
    JOIN cohorts AS h
        ON h.id = cs.cohort_id
    JOIN courses AS c
        ON c.id = h.course_id
    JOIN cohort_memberships AS cm
        ON cm.cohort_id = h.id
        AND cm.cohort_role = 'learner'
        AND cm.status = 'active'
    JOIN users AS u
        ON u.id = cm.user_id
        AND u.status = 'active'
    JOIN organization_memberships AS om
        ON om.organization_id = c.organization_id
        AND om.user_id = u.id
        AND om.role = 'student'
        AND om.status = 'active'
    LEFT JOIN understanding_checks AS uc
        ON uc.session_id = cs.id
        AND uc.learner_id = u.id
    WHERE
        cs.id = :session_id
        AND h.id = :cohort_id
        AND h.course_id = :course_id
        AND c.organization_id = :organization_id
    ORDER BY u.full_name, u.id
    LIMIT :limit
    OFFSET :offset
    """
)

_GET_UNDERSTANDING_CHECK = text(
    """
    SELECT
        uc.id,
        uc.session_id,
        uc.learner_id,
        u.email,
        u.full_name,
        uc.rating::TEXT AS rating,
        uc.confidence_score,
        uc.comment,
        uc.submitted_at,
        uc.created_at,
        uc.updated_at
    FROM understanding_checks AS uc
    JOIN class_sessions AS cs
        ON cs.id = uc.session_id
    JOIN cohorts AS h
        ON h.id = cs.cohort_id
    JOIN courses AS c
        ON c.id = h.course_id
    JOIN users AS u
        ON u.id = uc.learner_id
        AND u.status = 'active'
    JOIN organization_memberships AS om
        ON om.organization_id = c.organization_id
        AND om.user_id = u.id
        AND om.role = 'student'
        AND om.status = 'active'
    JOIN cohort_memberships AS cm
        ON cm.cohort_id = h.id
        AND cm.user_id = u.id
        AND cm.cohort_role = 'learner'
        AND cm.status = 'active'
    WHERE
        uc.learner_id = :learner_id
        AND cs.id = :session_id
        AND h.id = :cohort_id
        AND h.course_id = :course_id
        AND c.organization_id = :organization_id
    """
)

_UPSERT_UNDERSTANDING_CHECK = text(
    """
    INSERT INTO understanding_checks (
        session_id,
        learner_id,
        rating,
        comment,
        submitted_at
    )
    SELECT
        cs.id,
        u.id,
        CAST(:rating AS understanding_rating),
        :comment,
        NOW()
    FROM class_sessions AS cs
    JOIN cohorts AS h
        ON h.id = cs.cohort_id
    JOIN courses AS c
        ON c.id = h.course_id
    JOIN users AS u
        ON u.id = :learner_id
        AND u.status = 'active'
    JOIN organization_memberships AS om
        ON om.organization_id = c.organization_id
        AND om.user_id = u.id
        AND om.role = 'student'
        AND om.status = 'active'
    JOIN cohort_memberships AS cm
        ON cm.cohort_id = h.id
        AND cm.user_id = u.id
        AND cm.cohort_role = 'learner'
        AND cm.status = 'active'
    WHERE
        cs.id = :session_id
        AND cs.status = 'completed'
        AND h.id = :cohort_id
        AND h.course_id = :course_id
        AND c.organization_id = :organization_id
    ON CONFLICT (session_id, learner_id)
    DO UPDATE SET
        rating = EXCLUDED.rating,
        comment = EXCLUDED.comment,
        submitted_at = NOW(),
        updated_at = NOW()
    RETURNING id
    """
)


def _attendance_record_from_row(
    row: RowMapping,
) -> AttendanceRecordResponse:
    """Convert a trusted attendance row into an API model."""

    return AttendanceRecordResponse.model_validate(row)


def _attendance_roster_item_from_row(
    row: RowMapping,
) -> AttendanceRosterItem:
    """Convert a trusted attendance roster row into an API model."""

    return AttendanceRosterItem.model_validate(row)


def _understanding_check_from_row(
    row: RowMapping,
) -> UnderstandingCheckResponse:
    """Convert a trusted understanding row into an API model."""

    return UnderstandingCheckResponse.model_validate(row)


def _understanding_roster_item_from_row(
    row: RowMapping,
) -> UnderstandingRosterItem:
    """Convert a trusted understanding roster row into an API model."""

    return UnderstandingRosterItem.model_validate(row)


def _fetch_attendance_record(
    connection: Connection,
    parameters: dict[str, object],
) -> AttendanceRecordResponse | None:
    """Fetch one scoped attendance record using an existing connection."""

    row = (
        connection.execute(
            _GET_ATTENDANCE_RECORD,
            parameters,
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None

    return _attendance_record_from_row(row)


def _fetch_understanding_check(
    connection: Connection,
    parameters: dict[str, object],
) -> UnderstandingCheckResponse | None:
    """Fetch one scoped understanding check using an existing connection."""

    row = (
        connection.execute(
            _GET_UNDERSTANDING_CHECK,
            parameters,
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None

    return _understanding_check_from_row(row)


def list_session_attendance(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    session_id: UUID,
    *,
    limit: int,
    offset: int,
) -> tuple[list[AttendanceRosterItem], int]:
    """Return one page of active learners and their attendance."""

    parameters = {
        "organization_id": organization_id,
        "course_id": course_id,
        "cohort_id": cohort_id,
        "session_id": session_id,
        "limit": limit,
        "offset": offset,
    }

    with get_engine().connect() as connection:
        total = connection.execute(
            _COUNT_ATTENDANCE_ROSTER,
            parameters,
        ).scalar_one()
        rows = connection.execute(
            _LIST_ATTENDANCE_ROSTER,
            parameters,
        ).mappings()
        attendance = [
            _attendance_roster_item_from_row(row)
            for row in rows
        ]

    return attendance, total


def get_session_attendance(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    session_id: UUID,
    learner_id: UUID,
) -> AttendanceRecordResponse | None:
    """Return one learner's scoped attendance record."""

    parameters = {
        "organization_id": organization_id,
        "course_id": course_id,
        "cohort_id": cohort_id,
        "session_id": session_id,
        "learner_id": learner_id,
    }

    with get_engine().connect() as connection:
        return _fetch_attendance_record(
            connection,
            parameters,
        )


def upsert_session_attendance(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    session_id: UUID,
    learner_id: UUID,
    recorded_by: UUID,
    payload: AttendanceUpsert,
) -> AttendanceRecordResponse | None:
    """Create or update attendance for an eligible learner."""

    parameters = payload.model_dump(mode="python")
    parameters.update(
        {
            "organization_id": organization_id,
            "course_id": course_id,
            "cohort_id": cohort_id,
            "session_id": session_id,
            "learner_id": learner_id,
            "recorded_by": recorded_by,
        }
    )

    with get_engine().begin() as connection:
        attendance_id = connection.execute(
            _UPSERT_ATTENDANCE_RECORD,
            parameters,
        ).scalar_one_or_none()
        if attendance_id is None:
            return None

        return _fetch_attendance_record(
            connection,
            parameters,
        )


def list_session_understanding(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    session_id: UUID,
    *,
    limit: int,
    offset: int,
) -> tuple[list[UnderstandingRosterItem], int]:
    """Return one page of active learners and their understanding checks."""

    parameters = {
        "organization_id": organization_id,
        "course_id": course_id,
        "cohort_id": cohort_id,
        "session_id": session_id,
        "limit": limit,
        "offset": offset,
    }

    with get_engine().connect() as connection:
        total = connection.execute(
            _COUNT_UNDERSTANDING_ROSTER,
            parameters,
        ).scalar_one()
        rows = connection.execute(
            _LIST_UNDERSTANDING_ROSTER,
            parameters,
        ).mappings()
        checks = [
            _understanding_roster_item_from_row(row)
            for row in rows
        ]

    return checks, total


def get_session_understanding(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    session_id: UUID,
    learner_id: UUID,
) -> UnderstandingCheckResponse | None:
    """Return one learner's scoped understanding check."""

    parameters = {
        "organization_id": organization_id,
        "course_id": course_id,
        "cohort_id": cohort_id,
        "session_id": session_id,
        "learner_id": learner_id,
    }

    with get_engine().connect() as connection:
        return _fetch_understanding_check(
            connection,
            parameters,
        )


def upsert_session_understanding(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    session_id: UUID,
    learner_id: UUID,
    payload: UnderstandingCheckUpsert,
) -> UnderstandingCheckResponse | None:
    """Create or update an eligible learner's own understanding check."""

    parameters = payload.model_dump(mode="python")
    parameters.update(
        {
            "organization_id": organization_id,
            "course_id": course_id,
            "cohort_id": cohort_id,
            "session_id": session_id,
            "learner_id": learner_id,
        }
    )

    with get_engine().begin() as connection:
        check_id = connection.execute(
            _UPSERT_UNDERSTANDING_CHECK,
            parameters,
        ).scalar_one_or_none()
        if check_id is None:
            return None

        return _fetch_understanding_check(
            connection,
            parameters,
        )
