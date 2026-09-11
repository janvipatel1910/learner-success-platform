"""Organisation-scoped database operations for delivery cohorts."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping

from skillpulse.db.connection import get_engine
from skillpulse.schemas.catalog import (
    CohortCreate,
    CohortResponse,
    CohortUpdate,
)

_COUNT_COHORTS = text(
    """
    SELECT COUNT(*)
    FROM cohorts AS h
    JOIN courses AS c
        ON c.id = h.course_id
    WHERE
        h.course_id = :course_id
        AND c.organization_id = :organization_id
    """
)

_LIST_COHORTS = text(
    """
    SELECT
        h.id,
        h.course_id,
        h.name,
        h.start_date,
        h.end_date,
        h.delivery_mode::TEXT AS delivery_mode,
        h.status::TEXT AS status,
        h.created_at,
        h.updated_at
    FROM cohorts AS h
    JOIN courses AS c
        ON c.id = h.course_id
    WHERE
        h.course_id = :course_id
        AND c.organization_id = :organization_id
    ORDER BY h.start_date DESC, h.name, h.id
    LIMIT :limit
    OFFSET :offset
    """
)

_GET_COHORT = text(
    """
    SELECT
        h.id,
        h.course_id,
        h.name,
        h.start_date,
        h.end_date,
        h.delivery_mode::TEXT AS delivery_mode,
        h.status::TEXT AS status,
        h.created_at,
        h.updated_at
    FROM cohorts AS h
    JOIN courses AS c
        ON c.id = h.course_id
    WHERE
        h.id = :cohort_id
        AND h.course_id = :course_id
        AND c.organization_id = :organization_id
    """
)

_CREATE_COHORT = text(
    """
    INSERT INTO cohorts (
        course_id,
        name,
        start_date,
        end_date,
        delivery_mode,
        status
    )
    SELECT
        c.id,
        :name,
        :start_date,
        :end_date,
        CAST(:delivery_mode AS delivery_mode),
        CAST(:status AS cohort_status)
    FROM courses AS c
    WHERE
        c.id = :course_id
        AND c.organization_id = :organization_id
    RETURNING
        id,
        course_id,
        name,
        start_date,
        end_date,
        delivery_mode::TEXT AS delivery_mode,
        status::TEXT AS status,
        created_at,
        updated_at
    """
)

_UPDATE_COHORT = text(
    """
    UPDATE cohorts AS h
    SET
        name = :name,
        start_date = :start_date,
        end_date = :end_date,
        delivery_mode = CAST(:delivery_mode AS delivery_mode),
        status = CAST(:status AS cohort_status),
        updated_at = NOW()
    FROM courses AS c
    WHERE
        h.id = :cohort_id
        AND h.course_id = :course_id
        AND c.id = h.course_id
        AND c.organization_id = :organization_id
    RETURNING
        h.id,
        h.course_id,
        h.name,
        h.start_date,
        h.end_date,
        h.delivery_mode::TEXT AS delivery_mode,
        h.status::TEXT AS status,
        h.created_at,
        h.updated_at
    """
)


def _cohort_from_row(row: RowMapping) -> CohortResponse:
    """Convert a trusted database row into an API model."""

    return CohortResponse.model_validate(row)


def list_cohorts(
    organization_id: UUID,
    course_id: UUID,
    *,
    limit: int,
    offset: int,
) -> tuple[list[CohortResponse], int]:
    """Return one page of cohorts from an organisation-owned course."""

    parameters = {
        "organization_id": organization_id,
        "course_id": course_id,
        "limit": limit,
        "offset": offset,
    }

    with get_engine().connect() as connection:
        total = connection.execute(
            _COUNT_COHORTS,
            parameters,
        ).scalar_one()
        rows = connection.execute(
            _LIST_COHORTS,
            parameters,
        ).mappings()

        cohorts = [_cohort_from_row(row) for row in rows]

    return cohorts, total


def get_cohort(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
) -> CohortResponse | None:
    """Return a cohort without exposing another organisation's data."""

    with get_engine().connect() as connection:
        row = (
            connection.execute(
                _GET_COHORT,
                {
                    "organization_id": organization_id,
                    "course_id": course_id,
                    "cohort_id": cohort_id,
                },
            )
            .mappings()
            .one_or_none()
        )

    if row is None:
        return None

    return _cohort_from_row(row)


def create_cohort(
    organization_id: UUID,
    course_id: UUID,
    payload: CohortCreate,
) -> CohortResponse | None:
    """Create a cohort only inside an organisation-owned course."""

    parameters = payload.model_dump(mode="python")
    parameters.update(
        {
            "organization_id": organization_id,
            "course_id": course_id,
        }
    )

    with get_engine().begin() as connection:
        row = (
            connection.execute(
                _CREATE_COHORT,
                parameters,
            )
            .mappings()
            .one_or_none()
        )

    if row is None:
        return None

    return _cohort_from_row(row)


def update_cohort(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    payload: CohortUpdate,
) -> CohortResponse | None:
    """Update a cohort within its organisation-owned parent course."""

    parameters = payload.model_dump(mode="python")
    parameters.update(
        {
            "organization_id": organization_id,
            "course_id": course_id,
            "cohort_id": cohort_id,
        }
    )

    with get_engine().begin() as connection:
        row = (
            connection.execute(
                _UPDATE_COHORT,
                parameters,
            )
            .mappings()
            .one_or_none()
        )

    if row is None:
        return None

    return _cohort_from_row(row)
