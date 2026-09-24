"""Organisation-scoped learner-blocker and intervention operations."""

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from skillpulse.db.connection import get_engine
from skillpulse.schemas.blocker_interventions import (
    BlockerCreate,
    BlockerDetailResponse,
    BlockerEventResponse,
    BlockerResponse,
    BlockerSeverity,
    BlockerStatus,
    BlockerUpdate,
    InterventionCompletion,
    InterventionCreate,
    TutorInterventionResponse,
)

_BLOCKER_COLUMNS = """
    b.id,
    b.learner_id,
    learner.email AS learner_email,
    learner.full_name AS learner_full_name,
    b.cohort_id,
    h.name AS cohort_name,
    c.id AS course_id,
    c.title AS course_title,
    b.topic_id,
    topic.title AS topic_title,
    b.title,
    b.description,
    b.category,
    b.severity::TEXT AS severity,
    b.status::TEXT AS status,
    b.assigned_tutor_id,
    assigned_tutor.email AS assigned_tutor_email,
    assigned_tutor.full_name AS assigned_tutor_full_name,
    b.opened_at,
    b.resolved_at,
    b.resolution_summary,
    b.created_at,
    b.updated_at
"""

_BLOCKER_FROM = """
FROM blockers AS b
JOIN users AS learner
    ON learner.id = b.learner_id
JOIN cohorts AS h
    ON h.id = b.cohort_id
JOIN courses AS c
    ON c.id = h.course_id
LEFT JOIN topics AS topic
    ON topic.id = b.topic_id
    AND topic.course_id = c.id
LEFT JOIN users AS assigned_tutor
    ON assigned_tutor.id = b.assigned_tutor_id
"""

_COUNT_MY_BLOCKERS = text(
    f"""
    SELECT COUNT(*)
    {_BLOCKER_FROM}
    WHERE
        c.organization_id = :organization_id
        AND b.learner_id = :learner_id
        AND (
            CAST(:status_filter AS TEXT) IS NULL
            OR b.status = CAST(:status_filter AS blocker_status)
        )
        AND (
            CAST(:severity_filter AS TEXT) IS NULL
            OR b.severity = CAST(:severity_filter AS blocker_severity)
        )
    """
)

_LIST_MY_BLOCKERS = text(
    f"""
    SELECT
        {_BLOCKER_COLUMNS}
    {_BLOCKER_FROM}
    WHERE
        c.organization_id = :organization_id
        AND b.learner_id = :learner_id
        AND (
            CAST(:status_filter AS TEXT) IS NULL
            OR b.status = CAST(:status_filter AS blocker_status)
        )
        AND (
            CAST(:severity_filter AS TEXT) IS NULL
            OR b.severity = CAST(:severity_filter AS blocker_severity)
        )
    ORDER BY
        CASE b.severity
            WHEN 'critical' THEN 4
            WHEN 'high' THEN 3
            WHEN 'medium' THEN 2
            ELSE 1
        END DESC,
        b.opened_at DESC,
        b.id
    LIMIT :limit
    OFFSET :offset
    """
)

_COUNT_COHORT_BLOCKERS = text(
    f"""
    SELECT COUNT(*)
    {_BLOCKER_FROM}
    WHERE
        c.organization_id = :organization_id
        AND c.id = :course_id
        AND h.id = :cohort_id
        AND (
            CAST(:status_filter AS TEXT) IS NULL
            OR b.status = CAST(:status_filter AS blocker_status)
        )
        AND (
            CAST(:severity_filter AS TEXT) IS NULL
            OR b.severity = CAST(:severity_filter AS blocker_severity)
        )
    """
)

_LIST_COHORT_BLOCKERS = text(
    f"""
    SELECT
        {_BLOCKER_COLUMNS}
    {_BLOCKER_FROM}
    WHERE
        c.organization_id = :organization_id
        AND c.id = :course_id
        AND h.id = :cohort_id
        AND (
            CAST(:status_filter AS TEXT) IS NULL
            OR b.status = CAST(:status_filter AS blocker_status)
        )
        AND (
            CAST(:severity_filter AS TEXT) IS NULL
            OR b.severity = CAST(:severity_filter AS blocker_severity)
        )
    ORDER BY
        CASE b.severity
            WHEN 'critical' THEN 4
            WHEN 'high' THEN 3
            WHEN 'medium' THEN 2
            ELSE 1
        END DESC,
        b.opened_at DESC,
        b.id
    LIMIT :limit
    OFFSET :offset
    """
)

_GET_BLOCKER = text(
    f"""
    SELECT
        {_BLOCKER_COLUMNS}
    {_BLOCKER_FROM}
    WHERE
        b.id = :blocker_id
        AND c.organization_id = :organization_id
        AND (
            CAST(:course_id AS UUID) IS NULL
            OR c.id = CAST(:course_id AS UUID)
        )
        AND (
            CAST(:cohort_id AS UUID) IS NULL
            OR h.id = CAST(:cohort_id AS UUID)
        )
        AND (
            CAST(:learner_id AS UUID) IS NULL
            OR b.learner_id = CAST(:learner_id AS UUID)
        )
    """
)

_LIST_BLOCKER_EVENTS = text(
    """
    SELECT
        event.id,
        event.blocker_id,
        event.actor_id,
        actor.email AS actor_email,
        actor.full_name AS actor_full_name,
        event.event_type,
        event.old_status::TEXT AS old_status,
        event.new_status::TEXT AS new_status,
        event.comment,
        event.created_at
    FROM blocker_events AS event
    JOIN users AS actor
        ON actor.id = event.actor_id
    JOIN blockers AS b
        ON b.id = event.blocker_id
    JOIN cohorts AS h
        ON h.id = b.cohort_id
    JOIN courses AS c
        ON c.id = h.course_id
    WHERE
        event.blocker_id = :blocker_id
        AND c.organization_id = :organization_id
        AND (
            CAST(:course_id AS UUID) IS NULL
            OR c.id = CAST(:course_id AS UUID)
        )
        AND (
            CAST(:cohort_id AS UUID) IS NULL
            OR h.id = CAST(:cohort_id AS UUID)
        )
        AND (
            CAST(:learner_id AS UUID) IS NULL
            OR b.learner_id = CAST(:learner_id AS UUID)
        )
    ORDER BY event.created_at, event.id
    """
)

_LIST_BLOCKER_INTERVENTIONS = text(
    """
    SELECT
        intervention.id,
        intervention.learner_id,
        intervention.cohort_id,
        intervention.topic_id,
        topic.title AS topic_title,
        intervention.blocker_id,
        intervention.intervention_type,
        intervention.action_taken,
        intervention.baseline_metric,
        intervention.baseline_value,
        intervention.follow_up_value,
        intervention.outcome,
        intervention.tutor_id,
        tutor.email AS tutor_email,
        tutor.full_name AS tutor_full_name,
        intervention.started_at,
        intervention.completed_at,
        intervention.created_at,
        intervention.updated_at
    FROM tutor_interventions AS intervention
    JOIN blockers AS b
        ON b.id = intervention.blocker_id
    JOIN cohorts AS h
        ON h.id = b.cohort_id
    JOIN courses AS c
        ON c.id = h.course_id
    JOIN users AS tutor
        ON tutor.id = intervention.tutor_id
    LEFT JOIN topics AS topic
        ON topic.id = intervention.topic_id
        AND topic.course_id = c.id
    WHERE
        intervention.blocker_id = :blocker_id
        AND c.organization_id = :organization_id
        AND (
            CAST(:course_id AS UUID) IS NULL
            OR c.id = CAST(:course_id AS UUID)
        )
        AND (
            CAST(:cohort_id AS UUID) IS NULL
            OR h.id = CAST(:cohort_id AS UUID)
        )
        AND (
            CAST(:learner_id AS UUID) IS NULL
            OR b.learner_id = CAST(:learner_id AS UUID)
        )
    ORDER BY intervention.started_at, intervention.id
    """
)

_GET_INTERVENTION = text(
    """
    SELECT
        intervention.id,
        intervention.learner_id,
        intervention.cohort_id,
        intervention.topic_id,
        topic.title AS topic_title,
        intervention.blocker_id,
        intervention.intervention_type,
        intervention.action_taken,
        intervention.baseline_metric,
        intervention.baseline_value,
        intervention.follow_up_value,
        intervention.outcome,
        intervention.tutor_id,
        tutor.email AS tutor_email,
        tutor.full_name AS tutor_full_name,
        intervention.started_at,
        intervention.completed_at,
        intervention.created_at,
        intervention.updated_at
    FROM tutor_interventions AS intervention
    JOIN blockers AS b
        ON b.id = intervention.blocker_id
    JOIN cohorts AS h
        ON h.id = b.cohort_id
    JOIN courses AS c
        ON c.id = h.course_id
    JOIN users AS tutor
        ON tutor.id = intervention.tutor_id
    LEFT JOIN topics AS topic
        ON topic.id = intervention.topic_id
        AND topic.course_id = c.id
    WHERE
        intervention.id = :intervention_id
        AND intervention.blocker_id = :blocker_id
        AND c.organization_id = :organization_id
        AND c.id = :course_id
        AND h.id = :cohort_id
    """
)

_CREATE_BLOCKER = text(
    """
    WITH eligible_learner AS (
        SELECT h.id AS cohort_id
        FROM cohorts AS h
        JOIN courses AS c
            ON c.id = h.course_id
        JOIN cohort_memberships AS cm
            ON cm.cohort_id = h.id
            AND cm.user_id = :learner_id
            AND cm.cohort_role = 'learner'
            AND cm.status = 'active'
        JOIN users AS learner
            ON learner.id = cm.user_id
            AND learner.status = 'active'
        JOIN organization_memberships AS om
            ON om.organization_id = c.organization_id
            AND om.user_id = learner.id
            AND om.role = 'student'
            AND om.status = 'active'
        WHERE
            c.organization_id = :organization_id
            AND c.id = :course_id
            AND h.id = :cohort_id
            AND (
                CAST(:topic_id AS UUID) IS NULL
                OR EXISTS (
                    SELECT 1
                    FROM topics AS topic
                    WHERE
                        topic.id = CAST(:topic_id AS UUID)
                        AND topic.course_id = c.id
                )
            )
    )
    INSERT INTO blockers (
        learner_id,
        cohort_id,
        topic_id,
        title,
        description,
        category,
        severity
    )
    SELECT
        :learner_id,
        eligible_learner.cohort_id,
        CAST(:topic_id AS UUID),
        :title,
        :description,
        :category,
        CAST(:severity AS blocker_severity)
    FROM eligible_learner
    RETURNING id
    """
)

_LOCK_SCOPED_BLOCKER = text(
    """
    SELECT
        b.status::TEXT AS status,
        b.severity::TEXT AS severity,
        b.assigned_tutor_id,
        b.resolution_summary
    FROM blockers AS b
    JOIN cohorts AS h
        ON h.id = b.cohort_id
    JOIN courses AS c
        ON c.id = h.course_id
    WHERE
        b.id = :blocker_id
        AND c.organization_id = :organization_id
        AND c.id = :course_id
        AND h.id = :cohort_id
    FOR UPDATE OF b
    """
)

_UPDATE_BLOCKER = text(
    """
    UPDATE blockers AS b
    SET
        assigned_tutor_id = CASE
            WHEN CAST(:set_assigned_tutor AS BOOLEAN)
            THEN CAST(:assigned_tutor_id AS UUID)
            ELSE b.assigned_tutor_id
        END,
        severity = CASE
            WHEN CAST(:set_severity AS BOOLEAN)
            THEN CAST(:severity AS blocker_severity)
            ELSE b.severity
        END,
        status = CASE
            WHEN CAST(:set_status AS BOOLEAN)
            THEN CAST(:status AS blocker_status)
            ELSE b.status
        END,
        resolved_at = CASE
            WHEN CAST(:set_status AS BOOLEAN)
                AND CAST(:status AS TEXT) IN ('resolved', 'closed')
            THEN COALESCE(b.resolved_at, NOW())
            WHEN CAST(:set_status AS BOOLEAN)
            THEN NULL
            ELSE b.resolved_at
        END,
        resolution_summary = CASE
            WHEN CAST(:set_status AS BOOLEAN)
                AND CAST(:status AS TEXT) NOT IN ('resolved', 'closed')
            THEN NULL
            WHEN CAST(:set_resolution_summary AS BOOLEAN)
            THEN :resolution_summary
            ELSE b.resolution_summary
        END,
        updated_at = NOW()
    FROM cohorts AS h
    JOIN courses AS c
        ON c.id = h.course_id
    WHERE
        b.id = :blocker_id
        AND b.cohort_id = h.id
        AND c.organization_id = :organization_id
        AND c.id = :course_id
        AND h.id = :cohort_id
        AND (
            NOT CAST(:set_assigned_tutor AS BOOLEAN)
            OR CAST(:assigned_tutor_id AS UUID) IS NULL
            OR EXISTS (
                SELECT 1
                FROM users AS tutor
                JOIN cohort_memberships AS cm
                    ON cm.user_id = tutor.id
                    AND cm.cohort_id = h.id
                    AND cm.cohort_role = 'tutor'
                    AND cm.status = 'active'
                JOIN organization_memberships AS om
                    ON om.user_id = tutor.id
                    AND om.organization_id = c.organization_id
                    AND om.role = 'tutor'
                    AND om.status = 'active'
                WHERE
                    tutor.id = CAST(:assigned_tutor_id AS UUID)
                    AND tutor.status = 'active'
            )
        )
        AND (
            NOT CAST(:set_status AS BOOLEAN)
            OR CAST(:status AS TEXT)
                NOT IN ('assigned', 'waiting_student')
            OR (
                CASE
                    WHEN CAST(:set_assigned_tutor AS BOOLEAN)
                    THEN CAST(:assigned_tutor_id AS UUID)
                    ELSE b.assigned_tutor_id
                END
            ) IS NOT NULL
        )
        AND (
            NOT CAST(:set_status AS BOOLEAN)
            OR CAST(:status AS TEXT) NOT IN ('resolved', 'closed')
            OR (
                CASE
                    WHEN CAST(:set_resolution_summary AS BOOLEAN)
                    THEN :resolution_summary
                    ELSE b.resolution_summary
                END
            ) IS NOT NULL
        )
    RETURNING b.id
    """
)

_INSERT_BLOCKER_EVENT = text(
    """
    INSERT INTO blocker_events (
        blocker_id,
        actor_id,
        event_type,
        old_status,
        new_status,
        comment
    )
    VALUES (
        :blocker_id,
        :actor_id,
        :event_type,
        CAST(:old_status AS blocker_status),
        CAST(:new_status AS blocker_status),
        :event_comment
    )
    RETURNING id
    """
)

_CREATE_INTERVENTION = text(
    """
    INSERT INTO tutor_interventions (
        learner_id,
        cohort_id,
        topic_id,
        blocker_id,
        intervention_type,
        action_taken,
        baseline_metric,
        baseline_value,
        tutor_id
    )
    SELECT
        b.learner_id,
        b.cohort_id,
        b.topic_id,
        b.id,
        :intervention_type,
        :action_taken,
        :baseline_metric,
        :baseline_value,
        :tutor_id
    FROM blockers AS b
    JOIN cohorts AS h
        ON h.id = b.cohort_id
    JOIN courses AS c
        ON c.id = h.course_id
    WHERE
        b.id = :blocker_id
        AND c.organization_id = :organization_id
        AND c.id = :course_id
        AND h.id = :cohort_id
        AND b.status IN ('open', 'assigned', 'waiting_student')
    RETURNING id
    """
)

_COMPLETE_INTERVENTION = text(
    """
    UPDATE tutor_interventions AS intervention
    SET
        follow_up_value = :follow_up_value,
        outcome = CAST(:outcome AS VARCHAR),
        completed_at = NOW(),
        updated_at = NOW()
    FROM blockers AS b
    JOIN cohorts AS h
        ON h.id = b.cohort_id
    JOIN courses AS c
        ON c.id = h.course_id
    WHERE
        intervention.id = :intervention_id
        AND intervention.blocker_id = b.id
        AND b.id = :blocker_id
        AND c.organization_id = :organization_id
        AND c.id = :course_id
        AND h.id = :cohort_id
        AND intervention.outcome = 'pending'
        AND intervention.completed_at IS NULL
    RETURNING intervention.id
    """
)


def _blocker_from_row(row: RowMapping) -> BlockerResponse:
    """Convert a trusted blocker row into an API model."""

    return BlockerResponse.model_validate(row)


def _blocker_event_from_row(row: RowMapping) -> BlockerEventResponse:
    """Convert a trusted blocker-event row into an API model."""

    return BlockerEventResponse.model_validate(row)


def _intervention_from_row(
    row: RowMapping,
) -> TutorInterventionResponse:
    """Convert a trusted intervention row into an API model."""

    return TutorInterventionResponse.model_validate(row)


def _fetch_blocker_detail(
    connection: Connection,
    parameters: dict[str, object],
) -> BlockerDetailResponse | None:
    """Fetch one scoped blocker with its events and interventions."""

    row = (
        connection.execute(
            _GET_BLOCKER,
            parameters,
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None

    blocker = _blocker_from_row(row)

    event_rows = connection.execute(
        _LIST_BLOCKER_EVENTS,
        parameters,
    ).mappings()
    events = [
        _blocker_event_from_row(event_row)
        for event_row in event_rows
    ]

    intervention_rows = connection.execute(
        _LIST_BLOCKER_INTERVENTIONS,
        parameters,
    ).mappings()
    interventions = [
        _intervention_from_row(intervention_row)
        for intervention_row in intervention_rows
    ]

    return BlockerDetailResponse.model_validate(
        {
            **blocker.model_dump(mode="python"),
            "events": events,
            "interventions": interventions,
        }
    )


def _fetch_intervention(
    connection: Connection,
    parameters: dict[str, object],
) -> TutorInterventionResponse | None:
    """Fetch one scoped intervention using an existing connection."""

    row = (
        connection.execute(
            _GET_INTERVENTION,
            parameters,
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None

    return _intervention_from_row(row)


def _filter_value(
    value: BlockerStatus | BlockerSeverity | None,
) -> str | None:
    """Convert an optional string enum into a database value."""

    if value is None:
        return None
    return value.value


def list_my_blockers(
    organization_id: UUID,
    learner_id: UUID,
    *,
    status_filter: BlockerStatus | None,
    severity_filter: BlockerSeverity | None,
    limit: int,
    offset: int,
) -> tuple[list[BlockerResponse], int]:
    """Return one page of the authenticated learner's blockers."""

    parameters = {
        "organization_id": organization_id,
        "learner_id": learner_id,
        "status_filter": _filter_value(status_filter),
        "severity_filter": _filter_value(severity_filter),
        "limit": limit,
        "offset": offset,
    }

    with get_engine().connect() as connection:
        total = connection.execute(
            _COUNT_MY_BLOCKERS,
            parameters,
        ).scalar_one()

        rows = connection.execute(
            _LIST_MY_BLOCKERS,
            parameters,
        ).mappings()
        blockers = [_blocker_from_row(row) for row in rows]

    return blockers, total


def list_cohort_blockers(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    *,
    status_filter: BlockerStatus | None,
    severity_filter: BlockerSeverity | None,
    limit: int,
    offset: int,
) -> tuple[list[BlockerResponse], int]:
    """Return one page of blockers within a scoped cohort."""

    parameters = {
        "organization_id": organization_id,
        "course_id": course_id,
        "cohort_id": cohort_id,
        "status_filter": _filter_value(status_filter),
        "severity_filter": _filter_value(severity_filter),
        "limit": limit,
        "offset": offset,
    }

    with get_engine().connect() as connection:
        total = connection.execute(
            _COUNT_COHORT_BLOCKERS,
            parameters,
        ).scalar_one()

        rows = connection.execute(
            _LIST_COHORT_BLOCKERS,
            parameters,
        ).mappings()
        blockers = [_blocker_from_row(row) for row in rows]

    return blockers, total


def get_my_blocker(
    organization_id: UUID,
    learner_id: UUID,
    blocker_id: UUID,
) -> BlockerDetailResponse | None:
    """Return one blocker owned by the authenticated learner."""

    parameters = {
        "organization_id": organization_id,
        "course_id": None,
        "cohort_id": None,
        "learner_id": learner_id,
        "blocker_id": blocker_id,
    }

    with get_engine().connect() as connection:
        return _fetch_blocker_detail(connection, parameters)


def get_cohort_blocker(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    blocker_id: UUID,
) -> BlockerDetailResponse | None:
    """Return one blocker within a scoped cohort."""

    parameters = {
        "organization_id": organization_id,
        "course_id": course_id,
        "cohort_id": cohort_id,
        "learner_id": None,
        "blocker_id": blocker_id,
    }

    with get_engine().connect() as connection:
        return _fetch_blocker_detail(connection, parameters)


def create_my_blocker(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    learner_id: UUID,
    payload: BlockerCreate,
) -> BlockerDetailResponse | None:
    """Create a blocker for an eligible authenticated learner."""

    parameters = payload.model_dump(mode="python")
    parameters.update(
        {
            "organization_id": organization_id,
            "course_id": course_id,
            "cohort_id": cohort_id,
            "learner_id": learner_id,
            "severity": payload.severity.value,
        }
    )

    with get_engine().begin() as connection:
        blocker_id = connection.execute(
            _CREATE_BLOCKER,
            parameters,
        ).scalar_one_or_none()
        if blocker_id is None:
            return None

        connection.execute(
            _INSERT_BLOCKER_EVENT,
            {
                "blocker_id": blocker_id,
                "actor_id": learner_id,
                "event_type": "created",
                "old_status": None,
                "new_status": BlockerStatus.OPEN.value,
                "event_comment": "Learner reported a blocker.",
            },
        ).scalar_one()

        detail_parameters = {
            "organization_id": organization_id,
            "course_id": course_id,
            "cohort_id": cohort_id,
            "learner_id": learner_id,
            "blocker_id": blocker_id,
        }
        return _fetch_blocker_detail(
            connection,
            detail_parameters,
        )


def _blocker_update_event(
    payload: BlockerUpdate,
    previous_status: BlockerStatus,
) -> tuple[str, str | None, str | None, str]:
    """Build one auditable event for a blocker update."""

    fields = payload.model_fields_set

    if "status" in fields and payload.status is not None:
        comment = payload.comment or (
            f"Blocker status changed to {payload.status.value}."
        )
        return (
            payload.status.value,
            previous_status.value,
            payload.status.value,
            comment,
        )

    if "assigned_tutor_id" in fields:
        if payload.assigned_tutor_id is None:
            comment = payload.comment or "Tutor assignment removed."
            return "unassigned", None, None, comment

        comment = payload.comment or "Tutor assignment updated."
        return "assigned", None, None, comment

    if "severity" in fields and payload.severity is not None:
        comment = payload.comment or (
            f"Blocker severity changed to {payload.severity.value}."
        )
        return "severity_changed", None, None, comment

    if "resolution_summary" in fields:
        comment = payload.comment or "Resolution summary updated."
        return "resolution_updated", None, None, comment

    return "commented", None, None, payload.comment or "Comment added."


def update_cohort_blocker(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    blocker_id: UUID,
    actor_id: UUID,
    payload: BlockerUpdate,
) -> BlockerDetailResponse | None:
    """Update a scoped blocker and append its event atomically."""

    fields = payload.model_fields_set
    parameters = {
        "organization_id": organization_id,
        "course_id": course_id,
        "cohort_id": cohort_id,
        "blocker_id": blocker_id,
        "assigned_tutor_id": payload.assigned_tutor_id,
        "severity": (
            payload.severity.value
            if payload.severity is not None
            else None
        ),
        "status": (
            payload.status.value
            if payload.status is not None
            else None
        ),
        "resolution_summary": payload.resolution_summary,
        "set_assigned_tutor": "assigned_tutor_id" in fields,
        "set_severity": "severity" in fields,
        "set_status": "status" in fields,
        "set_resolution_summary": "resolution_summary" in fields,
    }

    with get_engine().begin() as connection:
        locked_row = (
            connection.execute(
                _LOCK_SCOPED_BLOCKER,
                parameters,
            )
            .mappings()
            .one_or_none()
        )
        if locked_row is None:
            return None

        previous_status = BlockerStatus(locked_row["status"])

        updated_id = connection.execute(
            _UPDATE_BLOCKER,
            parameters,
        ).scalar_one_or_none()
        if updated_id is None:
            return None

        (
            event_type,
            old_status,
            new_status,
            event_comment,
        ) = _blocker_update_event(
            payload,
            previous_status,
        )

        connection.execute(
            _INSERT_BLOCKER_EVENT,
            {
                "blocker_id": blocker_id,
                "actor_id": actor_id,
                "event_type": event_type,
                "old_status": old_status,
                "new_status": new_status,
                "event_comment": event_comment,
            },
        ).scalar_one()

        detail_parameters = {
            "organization_id": organization_id,
            "course_id": course_id,
            "cohort_id": cohort_id,
            "learner_id": None,
            "blocker_id": blocker_id,
        }
        return _fetch_blocker_detail(
            connection,
            detail_parameters,
        )


def get_cohort_intervention(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    blocker_id: UUID,
    intervention_id: UUID,
) -> TutorInterventionResponse | None:
    """Return one intervention linked to a scoped blocker."""

    parameters = {
        "organization_id": organization_id,
        "course_id": course_id,
        "cohort_id": cohort_id,
        "blocker_id": blocker_id,
        "intervention_id": intervention_id,
    }

    with get_engine().connect() as connection:
        return _fetch_intervention(connection, parameters)


def create_blocker_intervention(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    blocker_id: UUID,
    tutor_id: UUID,
    payload: InterventionCreate,
) -> TutorInterventionResponse | None:
    """Create an intervention and append a blocker event atomically."""

    parameters = payload.model_dump(mode="python")
    parameters.update(
        {
            "organization_id": organization_id,
            "course_id": course_id,
            "cohort_id": cohort_id,
            "blocker_id": blocker_id,
            "tutor_id": tutor_id,
        }
    )

    with get_engine().begin() as connection:
        intervention_id = connection.execute(
            _CREATE_INTERVENTION,
            parameters,
        ).scalar_one_or_none()
        if intervention_id is None:
            return None

        connection.execute(
            _INSERT_BLOCKER_EVENT,
            {
                "blocker_id": blocker_id,
                "actor_id": tutor_id,
                "event_type": "intervention_created",
                "old_status": None,
                "new_status": None,
                "event_comment": (
                    "Intervention created: "
                    f"{payload.intervention_type}."
                ),
            },
        ).scalar_one()

        parameters["intervention_id"] = intervention_id
        return _fetch_intervention(connection, parameters)


def complete_blocker_intervention(
    organization_id: UUID,
    course_id: UUID,
    cohort_id: UUID,
    blocker_id: UUID,
    intervention_id: UUID,
    actor_id: UUID,
    payload: InterventionCompletion,
) -> TutorInterventionResponse | None:
    """Complete a pending intervention and append an event atomically."""

    parameters = payload.model_dump(mode="python")
    parameters.update(
        {
            "organization_id": organization_id,
            "course_id": course_id,
            "cohort_id": cohort_id,
            "blocker_id": blocker_id,
            "intervention_id": intervention_id,
            "outcome": payload.outcome.value,
        }
    )

    with get_engine().begin() as connection:
        completed_id = connection.execute(
            _COMPLETE_INTERVENTION,
            parameters,
        ).scalar_one_or_none()
        if completed_id is None:
            return None

        connection.execute(
            _INSERT_BLOCKER_EVENT,
            {
                "blocker_id": blocker_id,
                "actor_id": actor_id,
                "event_type": "intervention_completed",
                "old_status": None,
                "new_status": None,
                "event_comment": (
                    "Intervention completed with outcome: "
                    f"{payload.outcome.value}."
                ),
            },
        ).scalar_one()

        return _fetch_intervention(connection, parameters)
