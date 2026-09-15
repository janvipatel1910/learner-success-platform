"""Organisation-scoped cohort enrollment database operations."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from skillpulse.db.connection import get_engine
from skillpulse.schemas.enrollment import (
    CohortMembershipCreate,
    CohortMembershipResponse,
    CohortMembershipUpdate,
    CohortRole,
    MyCohortMembershipResponse,
)

_COUNT_COHORT_MEMBERSHIPS = text(
    """
    SELECT COUNT(*)
    FROM cohort_memberships AS cm
    JOIN cohorts AS h
        ON h.id = cm.cohort_id
    JOIN courses AS c
        ON c.id = h.course_id
    WHERE
        h.id = :cohort_id
        AND h.course_id = :course_id
        AND c.organization_id = :organization_id
    """
)

_LIST_COHORT_MEMBERSHIPS = text(
    """
    SELECT
        cm.id,
        cm.cohort_id,
        cm.user_id,
        u.email::TEXT AS email,
        u.full_name,
        cm.cohort_role::TEXT AS cohort_role,
        cm.status::TEXT AS status,
        cm.enrolled_at,
        cm.created_at,
        cm.updated_at
    FROM cohort_memberships AS cm
    JOIN users AS u
        ON u.id = cm.user_id
    JOIN cohorts AS h
        ON h.id = cm.cohort_id
    JOIN courses AS c
        ON c.id = h.course_id
    WHERE
        h.id = :cohort_id
        AND h.course_id = :course_id
        AND c.organization_id = :organization_id
    ORDER BY
        CASE cm.cohort_role
            WHEN 'tutor' THEN 0
            ELSE 1
        END,
        u.full_name,
        cm.id
    LIMIT :limit
    OFFSET :offset
    """
)

_GET_COHORT_MEMBERSHIP = text(
    """
    SELECT
        cm.id,
        cm.cohort_id,
        cm.user_id,
        u.email::TEXT AS email,
        u.full_name,
        cm.cohort_role::TEXT AS cohort_role,
        cm.status::TEXT AS status,
        cm.enrolled_at,
        cm.created_at,
        cm.updated_at
    FROM cohort_memberships AS cm
    JOIN users AS u
        ON u.id = cm.user_id
    JOIN cohorts AS h
        ON h.id = cm.cohort_id
    JOIN courses AS c
        ON c.id = h.course_id
    WHERE
        cm.id = :membership_id
        AND h.id = :cohort_id
        AND h.course_id = :course_id
        AND c.organization_id = :organization_id
    """
)

_CREATE_COHORT_MEMBERSHIP = text(
    """
    INSERT INTO cohort_memberships (
        cohort_id,
        user_id,
        cohort_role,
        status
    )
    SELECT
        h.id,
        u.id,
        CAST(:cohort_role AS cohort_role),
        CAST(:status AS membership_status)
    FROM cohorts AS h
    JOIN courses AS c
        ON c.id = h.course_id
    JOIN users AS u
        ON u.id = :user_id
       AND u.status = 'active'
    JOIN organization_memberships AS om
        ON om.organization_id = c.organization_id
       AND om.user_id = u.id
       AND om.status = 'active'
    WHERE
        h.id = :cohort_id
        AND h.course_id = :course_id
        AND c.organization_id = :organization_id
        AND (
            (
                CAST(:cohort_role AS TEXT) = 'learner'
                AND om.role = 'student'
            )
            OR (
                CAST(:cohort_role AS TEXT) = 'tutor'
                AND om.role = 'tutor'
            )
        )
    RETURNING id
    """
)

_UPDATE_COHORT_MEMBERSHIP = text(
    """
    UPDATE cohort_memberships AS cm
    SET
        cohort_role = CAST(:cohort_role AS cohort_role),
        status = CAST(:status AS membership_status),
        updated_at = NOW()
    FROM cohorts AS h
    JOIN courses AS c
        ON c.id = h.course_id
    WHERE
        cm.id = :membership_id
        AND cm.cohort_id = h.id
        AND h.id = :cohort_id
        AND h.course_id = :course_id
        AND c.organization_id = :organization_id
        AND (
            EXISTS (
                SELECT 1
                FROM users AS u
                JOIN organization_memberships AS om
                    ON om.user_id = u.id
                   AND om.organization_id = c.organization_id
                   AND om.status = 'active'
                WHERE
                    u.id = cm.user_id
                    AND u.status = 'active'
                    AND (
                        (
                            CAST(:cohort_role AS TEXT) = 'learner'
                            AND om.role = 'student'
                        )
                        OR (
                            CAST(:cohort_role AS TEXT) = 'tutor'
                            AND om.role = 'tutor'
                        )
                    )
            )
            OR (
                CAST(:status AS TEXT) = 'inactive'
                AND cm.cohort_role::TEXT = CAST(
                    :cohort_role AS TEXT
                )
            )
        )
    RETURNING cm.id
    """
)

_IS_ACTIVE_COHORT_TUTOR = text(
    """
    SELECT EXISTS (
        SELECT 1
        FROM cohort_memberships AS cm
        JOIN cohorts AS h
            ON h.id = cm.cohort_id
        JOIN courses AS c
            ON c.id = h.course_id
        WHERE
            cm.user_id = :user_id
            AND cm.cohort_role = 'tutor'
            AND cm.status = 'active'
            AND h.id = :cohort_id
            AND h.course_id = :course_id
            AND c.organization_id = :organization_id
    )
    """
)

_HAS_ACTIVE_COHORT_ROLE = text(
    """
    SELECT EXISTS (
        SELECT 1
        FROM cohort_memberships AS cm
        JOIN cohorts AS h
            ON h.id = cm.cohort_id
        JOIN courses AS c
            ON c.id = h.course_id
        WHERE
            cm.user_id = :user_id
            AND cm.cohort_role::TEXT = CAST(
                :cohort_role AS TEXT
            )
            AND cm.status = 'active'
            AND h.id = :cohort_id
            AND h.course_id = :course_id
            AND c.organization_id = :organization_id
    )
    """
)

_COUNT_MY_COHORT_MEMBERSHIPS = text(
    """
    SELECT COUNT(*)
    FROM cohort_memberships AS cm
    JOIN cohorts AS h
        ON h.id = cm.cohort_id
    JOIN courses AS c
        ON c.id = h.course_id
    WHERE
        cm.user_id = :user_id
        AND c.organization_id = :organization_id
    """
)

_LIST_MY_COHORT_MEMBERSHIPS = text(
    """
    SELECT
        cm.id,
        c.id AS course_id,
        c.title AS course_title,
        h.id AS cohort_id,
        h.name AS cohort_name,
        cm.cohort_role::TEXT AS cohort_role,
        cm.status::TEXT AS status,
        h.start_date,
        h.end_date,
        cm.enrolled_at
    FROM cohort_memberships AS cm
    JOIN cohorts AS h
        ON h.id = cm.cohort_id
    JOIN courses AS c
        ON c.id = h.course_id
    WHERE
        cm.user_id = :user_id
        AND c.organization_id = :organization_id
    ORDER BY
        h.start_date DESC,
        h.name,
        h.id
    LIMIT :limit
    OFFSET :offset
    """
)


def _cohort_membership_from_row(
    row: RowMapping,
) -> CohortMembershipResponse:
    """Convert a trusted roster row into an API model."""

    return CohortMembershipResponse.model_validate(row)


def _my_cohort_membership_from_row(
    row: RowMapping,
) -> MyCohortMembershipResponse:
    """Convert a trusted self-membership row into an API model."""

    return MyCohortMembershipResponse.model_validate(row)


def _fetch_cohort_membership(
    connection: Connection,
    parameters: dict[str, object],
) -> CohortMembershipResponse | None:
    """Fetch one scoped cohort membership using an existing connection."""

    row = (
        connection.execute(
            _GET_COHORT_MEMBERSHIP,
            parameters,
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None

    return _cohort_membership_from_row(row)


def list_cohort_memberships(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    *,
    limit: int,
    offset: int,
) -> tuple[list[CohortMembershipResponse], int]:
    """Return one page of a scoped cohort roster."""

    parameters = {
        "organization_id": organization_id,
        "course_id": course_id,
        "cohort_id": cohort_id,
        "limit": limit,
        "offset": offset,
    }

    with get_engine().connect() as connection:
        total = connection.execute(
            _COUNT_COHORT_MEMBERSHIPS,
            parameters,
        ).scalar_one()
        rows = connection.execute(
            _LIST_COHORT_MEMBERSHIPS,
            parameters,
        ).mappings()
        memberships = [
            _cohort_membership_from_row(row)
            for row in rows
        ]

    return memberships, total

def has_active_cohort_role(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    user_id: UUID,
    cohort_role: CohortRole,
) -> bool:
    """Return whether a user holds an active scoped cohort role."""

    with get_engine().connect() as connection:
        result = connection.execute(
            _HAS_ACTIVE_COHORT_ROLE,
            {
                "organization_id": organization_id,
                "course_id": course_id,
                "cohort_id": cohort_id,
                "user_id": user_id,
                "cohort_role": cohort_role.value,
            },
        ).scalar_one()

    return bool(result)


def get_cohort_membership(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    membership_id: UUID,
) -> CohortMembershipResponse | None:
    """Return one membership without exposing another organisation."""

    parameters = {
        "organization_id": organization_id,
        "course_id": course_id,
        "cohort_id": cohort_id,
        "membership_id": membership_id,
    }

    with get_engine().connect() as connection:
        return _fetch_cohort_membership(
            connection,
            parameters,
        )


def create_cohort_membership(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    payload: CohortMembershipCreate,
) -> CohortMembershipResponse | None:
    """Enroll an eligible active organisation member."""

    parameters = payload.model_dump(mode="python")
    parameters.update(
        {
            "organization_id": organization_id,
            "course_id": course_id,
            "cohort_id": cohort_id,
        }
    )

    with get_engine().begin() as connection:
        membership_id = connection.execute(
            _CREATE_COHORT_MEMBERSHIP,
            parameters,
        ).scalar_one_or_none()
        if membership_id is None:
            return None

        parameters["membership_id"] = membership_id
        return _fetch_cohort_membership(
            connection,
            parameters,
        )


def update_cohort_membership(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    membership_id: UUID,
    payload: CohortMembershipUpdate,
) -> CohortMembershipResponse | None:
    """Update a scoped membership after eligibility validation."""

    parameters = payload.model_dump(mode="python")
    parameters.update(
        {
            "organization_id": organization_id,
            "course_id": course_id,
            "cohort_id": cohort_id,
            "membership_id": membership_id,
        }
    )

    with get_engine().begin() as connection:
        updated_id = connection.execute(
            _UPDATE_COHORT_MEMBERSHIP,
            parameters,
        ).scalar_one_or_none()
        if updated_id is None:
            return None

        return _fetch_cohort_membership(
            connection,
            parameters,
        )


def is_active_cohort_tutor(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    user_id: UUID,
) -> bool:
    """Return whether a user is an active tutor for the scoped cohort."""

    with get_engine().connect() as connection:
        result = connection.execute(
            _IS_ACTIVE_COHORT_TUTOR,
            {
                "organization_id": organization_id,
                "course_id": course_id,
                "cohort_id": cohort_id,
                "user_id": user_id,
            },
        ).scalar_one()

    return bool(result)


def list_my_cohort_memberships(
    organization_id: UUID,
    user_id: UUID,
    *,
    limit: int,
    offset: int,
) -> tuple[list[MyCohortMembershipResponse], int]:
    """Return one page of the authenticated user's memberships."""

    parameters = {
        "organization_id": organization_id,
        "user_id": user_id,
        "limit": limit,
        "offset": offset,
    }

    with get_engine().connect() as connection:
        total = connection.execute(
            _COUNT_MY_COHORT_MEMBERSHIPS,
            parameters,
        ).scalar_one()
        rows = connection.execute(
            _LIST_MY_COHORT_MEMBERSHIPS,
            parameters,
        ).mappings()
        memberships = [
            _my_cohort_membership_from_row(row)
            for row in rows
        ]

    return memberships, total
