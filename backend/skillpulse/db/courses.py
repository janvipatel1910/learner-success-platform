"""Organisation-scoped database operations for courses."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping

from skillpulse.db.connection import get_engine
from skillpulse.schemas.catalog import (
    CourseCreate,
    CourseResponse,
    CourseUpdate,
)

_COUNT_COURSES = text(
    """
    SELECT COUNT(*)
    FROM courses
    WHERE organization_id = :organization_id
    """
)

_LIST_COURSES = text(
    """
    SELECT
        id,
        organization_id,
        title,
        code,
        description,
        certification_name,
        status::TEXT AS status,
        created_at,
        updated_at
    FROM courses
    WHERE organization_id = :organization_id
    ORDER BY title, id
    LIMIT :limit
    OFFSET :offset
    """
)

_GET_COURSE = text(
    """
    SELECT
        id,
        organization_id,
        title,
        code,
        description,
        certification_name,
        status::TEXT AS status,
        created_at,
        updated_at
    FROM courses
    WHERE
        id = :course_id
        AND organization_id = :organization_id
    """
)

_CREATE_COURSE = text(
    """
    INSERT INTO courses (
        organization_id,
        title,
        code,
        description,
        certification_name,
        status
    )
    VALUES (
        :organization_id,
        :title,
        :code,
        :description,
        :certification_name,
        CAST(:status AS course_status)
    )
    RETURNING
        id,
        organization_id,
        title,
        code,
        description,
        certification_name,
        status::TEXT AS status,
        created_at,
        updated_at
    """
)

_UPDATE_COURSE = text(
    """
    UPDATE courses
    SET
        title = :title,
        code = :code,
        description = :description,
        certification_name = :certification_name,
        status = CAST(:status AS course_status),
        updated_at = NOW()
    WHERE
        id = :course_id
        AND organization_id = :organization_id
    RETURNING
        id,
        organization_id,
        title,
        code,
        description,
        certification_name,
        status::TEXT AS status,
        created_at,
        updated_at
    """
)


def _course_from_row(row: RowMapping) -> CourseResponse:
    """Convert a trusted database row into an API model."""

    return CourseResponse.model_validate(row)


def list_courses(
    organization_id: UUID,
    *,
    limit: int,
    offset: int,
) -> tuple[list[CourseResponse], int]:
    """Return one deterministic page of organisation courses."""

    parameters = {
        "organization_id": organization_id,
        "limit": limit,
        "offset": offset,
    }

    with get_engine().connect() as connection:
        total = connection.execute(
            _COUNT_COURSES,
            {"organization_id": organization_id},
        ).scalar_one()
        rows = connection.execute(
            _LIST_COURSES,
            parameters,
        ).mappings()

        courses = [_course_from_row(row) for row in rows]

    return courses, total


def get_course(
    organization_id: UUID,
    course_id: UUID,
) -> CourseResponse | None:
    """Return an organisation-owned course without leaking other tenants."""

    with get_engine().connect() as connection:
        row = (
            connection.execute(
                _GET_COURSE,
                {
                    "organization_id": organization_id,
                    "course_id": course_id,
                },
            )
            .mappings()
            .one_or_none()
        )

    if row is None:
        return None

    return _course_from_row(row)


def create_course(
    organization_id: UUID,
    payload: CourseCreate,
) -> CourseResponse:
    """Create and commit an organisation-owned course."""

    parameters = payload.model_dump(mode="python")
    parameters["organization_id"] = organization_id

    with get_engine().begin() as connection:
        row = (
            connection.execute(
                _CREATE_COURSE,
                parameters,
            )
            .mappings()
            .one()
        )

    return _course_from_row(row)


def update_course(
    organization_id: UUID,
    course_id: UUID,
    payload: CourseUpdate,
) -> CourseResponse | None:
    """Replace editable fields on an organisation-owned course."""

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
                _UPDATE_COURSE,
                parameters,
            )
            .mappings()
            .one_or_none()
        )

    if row is None:
        return None

    return _course_from_row(row)
