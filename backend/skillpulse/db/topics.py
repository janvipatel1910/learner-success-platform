"""Organisation-scoped database operations for course topics."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping

from skillpulse.db.connection import get_engine
from skillpulse.schemas.catalog import (
    TopicCreate,
    TopicResponse,
    TopicUpdate,
)

_COUNT_TOPICS = text(
    """
    SELECT COUNT(*)
    FROM topics AS t
    JOIN courses AS c
        ON c.id = t.course_id
    WHERE
        t.course_id = :course_id
        AND c.organization_id = :organization_id
    """
)

_LIST_TOPICS = text(
    """
    SELECT
        t.id,
        t.course_id,
        t.title,
        t.sequence_number,
        t.exam_domain,
        t.expected_hours,
        t.created_at,
        t.updated_at
    FROM topics AS t
    JOIN courses AS c
        ON c.id = t.course_id
    WHERE
        t.course_id = :course_id
        AND c.organization_id = :organization_id
    ORDER BY t.sequence_number, t.id
    LIMIT :limit
    OFFSET :offset
    """
)

_GET_TOPIC = text(
    """
    SELECT
        t.id,
        t.course_id,
        t.title,
        t.sequence_number,
        t.exam_domain,
        t.expected_hours,
        t.created_at,
        t.updated_at
    FROM topics AS t
    JOIN courses AS c
        ON c.id = t.course_id
    WHERE
        t.id = :topic_id
        AND t.course_id = :course_id
        AND c.organization_id = :organization_id
    """
)

_CREATE_TOPIC = text(
    """
    INSERT INTO topics (
        course_id,
        title,
        sequence_number,
        exam_domain,
        expected_hours
    )
    SELECT
        c.id,
        :title,
        :sequence_number,
        :exam_domain,
        :expected_hours
    FROM courses AS c
    WHERE
        c.id = :course_id
        AND c.organization_id = :organization_id
    RETURNING
        id,
        course_id,
        title,
        sequence_number,
        exam_domain,
        expected_hours,
        created_at,
        updated_at
    """
)

_UPDATE_TOPIC = text(
    """
    UPDATE topics AS t
    SET
        title = :title,
        sequence_number = :sequence_number,
        exam_domain = :exam_domain,
        expected_hours = :expected_hours,
        updated_at = NOW()
    FROM courses AS c
    WHERE
        t.id = :topic_id
        AND t.course_id = :course_id
        AND c.id = t.course_id
        AND c.organization_id = :organization_id
    RETURNING
        t.id,
        t.course_id,
        t.title,
        t.sequence_number,
        t.exam_domain,
        t.expected_hours,
        t.created_at,
        t.updated_at
    """
)


def _topic_from_row(row: RowMapping) -> TopicResponse:
    """Convert a trusted database row into an API model."""

    return TopicResponse.model_validate(row)


def list_topics(
    organization_id: UUID,
    course_id: UUID,
    *,
    limit: int,
    offset: int,
) -> tuple[list[TopicResponse], int]:
    """Return one page of topics from an organisation-owned course."""

    parameters = {
        "organization_id": organization_id,
        "course_id": course_id,
        "limit": limit,
        "offset": offset,
    }

    with get_engine().connect() as connection:
        total = connection.execute(
            _COUNT_TOPICS,
            parameters,
        ).scalar_one()
        rows = connection.execute(
            _LIST_TOPICS,
            parameters,
        ).mappings()

        topics = [_topic_from_row(row) for row in rows]

    return topics, total


def get_topic(
    organization_id: UUID,
    course_id: UUID,
    topic_id: UUID,
) -> TopicResponse | None:
    """Return a topic without exposing another organisation's data."""

    with get_engine().connect() as connection:
        row = (
            connection.execute(
                _GET_TOPIC,
                {
                    "organization_id": organization_id,
                    "course_id": course_id,
                    "topic_id": topic_id,
                },
            )
            .mappings()
            .one_or_none()
        )

    if row is None:
        return None

    return _topic_from_row(row)


def create_topic(
    organization_id: UUID,
    course_id: UUID,
    payload: TopicCreate,
) -> TopicResponse | None:
    """Create a topic only when the parent course belongs to the organisation."""

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
                _CREATE_TOPIC,
                parameters,
            )
            .mappings()
            .one_or_none()
        )

    if row is None:
        return None

    return _topic_from_row(row)


def update_topic(
    organization_id: UUID,
    course_id: UUID,
    topic_id: UUID,
    payload: TopicUpdate,
) -> TopicResponse | None:
    """Update a topic only within its organisation-owned parent course."""

    parameters = payload.model_dump(mode="python")
    parameters.update(
        {
            "organization_id": organization_id,
            "course_id": course_id,
            "topic_id": topic_id,
        }
    )

    with get_engine().begin() as connection:
        row = (
            connection.execute(
                _UPDATE_TOPIC,
                parameters,
            )
            .mappings()
            .one_or_none()
        )

    if row is None:
        return None

    return _topic_from_row(row)
