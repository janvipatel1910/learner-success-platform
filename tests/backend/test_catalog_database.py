import os
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from scripts.seed_synthetic_data import load_synthetic_data
from sqlalchemy import text

from skillpulse.db import cohorts as cohort_repository
from skillpulse.db import courses as course_repository
from skillpulse.db import topics as topic_repository
from skillpulse.db.connection import get_engine
from skillpulse.schemas.catalog import (
    CohortCreate,
    CohortStatus,
    CohortUpdate,
    CourseCreate,
    CourseStatus,
    CourseUpdate,
    DeliveryMode,
    TopicCreate,
    TopicUpdate,
)

pytestmark = pytest.mark.integration

requires_database = pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "true",
    reason="Set RUN_DATABASE_TESTS=true to run PostgreSQL integration tests",
)

requires_seed_tests = pytest.mark.skipif(
    os.getenv("RUN_SEED_TESTS") != "true",
    reason="Set RUN_SEED_TESTS=true to run synthetic seed tests",
)

ORGANIZATION_ID = UUID("10000000-0000-0000-0000-000000000001")
OTHER_ORGANIZATION_ID = UUID(
    "10000000-0000-0000-0000-000000000099"
)
SEEDED_COURSE_ID = UUID(
    "40000000-0000-0000-0000-000000000001"
)


@requires_database
@requires_seed_tests
def test_seeded_catalog_queries_are_organization_scoped() -> None:
    """Read seeded courses, topics and cohorts without tenant leakage."""

    load_synthetic_data()

    course = course_repository.get_course(
        ORGANIZATION_ID,
        SEEDED_COURSE_ID,
    )
    assert course is not None
    assert course.code == "AWS-SAA-DEMO"

    courses, course_total = course_repository.list_courses(
        ORGANIZATION_ID,
        limit=20,
        offset=0,
    )
    assert course_total >= 1
    assert any(item.id == SEEDED_COURSE_ID for item in courses)

    topics, topic_total = topic_repository.list_topics(
        ORGANIZATION_ID,
        SEEDED_COURSE_ID,
        limit=20,
        offset=0,
    )
    assert topic_total >= 1
    assert topics

    topic = topic_repository.get_topic(
        ORGANIZATION_ID,
        SEEDED_COURSE_ID,
        topics[0].id,
    )
    assert topic is not None
    assert topic.course_id == SEEDED_COURSE_ID

    cohorts, cohort_total = cohort_repository.list_cohorts(
        ORGANIZATION_ID,
        SEEDED_COURSE_ID,
        limit=20,
        offset=0,
    )
    assert cohort_total >= 1
    assert cohorts

    cohort = cohort_repository.get_cohort(
        ORGANIZATION_ID,
        SEEDED_COURSE_ID,
        cohorts[0].id,
    )
    assert cohort is not None
    assert cohort.course_id == SEEDED_COURSE_ID

    assert (
        course_repository.get_course(
            OTHER_ORGANIZATION_ID,
            SEEDED_COURSE_ID,
        )
        is None
    )
    assert (
        topic_repository.get_topic(
            OTHER_ORGANIZATION_ID,
            SEEDED_COURSE_ID,
            topics[0].id,
        )
        is None
    )
    assert (
        cohort_repository.get_cohort(
            OTHER_ORGANIZATION_ID,
            SEEDED_COURSE_ID,
            cohorts[0].id,
        )
        is None
    )

    other_topics, other_topic_total = topic_repository.list_topics(
        OTHER_ORGANIZATION_ID,
        SEEDED_COURSE_ID,
        limit=20,
        offset=0,
    )
    assert other_topics == []
    assert other_topic_total == 0

    other_cohorts, other_cohort_total = (
        cohort_repository.list_cohorts(
            OTHER_ORGANIZATION_ID,
            SEEDED_COURSE_ID,
            limit=20,
            offset=0,
        )
    )
    assert other_cohorts == []
    assert other_cohort_total == 0


@requires_database
@requires_seed_tests
def test_catalog_create_and_update_lifecycle() -> None:
    """Execute real create and update SQL for all catalog resources."""

    load_synthetic_data()

    suffix = uuid4().hex[:10]
    course_code = f"SC006-{suffix.upper()}"
    created_course_id: UUID | None = None

    try:
        created_course = course_repository.create_course(
            ORGANIZATION_ID,
            CourseCreate(
                title=f"SC-006 Test Course {suffix}",
                code=course_code,
                description="Temporary catalog integration test course.",
                certification_name=None,
            ),
        )
        created_course_id = created_course.id

        assert created_course.organization_id == ORGANIZATION_ID
        assert created_course.status is CourseStatus.DRAFT

        updated_course = course_repository.update_course(
            ORGANIZATION_ID,
            created_course.id,
            CourseUpdate(
                title=f"Updated SC-006 Course {suffix}",
                code=course_code,
                description="Updated integration test course.",
                certification_name="SkillPulse Test Certification",
                status=CourseStatus.ACTIVE,
            ),
        )
        assert updated_course is not None
        assert updated_course.status is CourseStatus.ACTIVE
        assert updated_course.title.startswith("Updated SC-006")

        created_topic = topic_repository.create_topic(
            ORGANIZATION_ID,
            created_course.id,
            TopicCreate(
                title=f"Integration Topic {suffix}",
                sequence_number=1,
                exam_domain="Cloud Architecture",
                expected_hours=Decimal("4.50"),
            ),
        )
        assert created_topic is not None
        assert created_topic.course_id == created_course.id

        updated_topic = topic_repository.update_topic(
            ORGANIZATION_ID,
            created_course.id,
            created_topic.id,
            TopicUpdate(
                title=f"Updated Integration Topic {suffix}",
                sequence_number=2,
                exam_domain="Secure Cloud Architecture",
                expected_hours=Decimal("5.00"),
            ),
        )
        assert updated_topic is not None
        assert updated_topic.sequence_number == 2
        assert updated_topic.expected_hours == Decimal("5.00")

        created_cohort = cohort_repository.create_cohort(
            ORGANIZATION_ID,
            created_course.id,
            CohortCreate(
                name=f"SC-006 Cohort {suffix}",
                start_date=date(2026, 10, 1),
                end_date=date(2026, 12, 20),
                delivery_mode=DeliveryMode.ONLINE,
            ),
        )
        assert created_cohort is not None
        assert created_cohort.status is CohortStatus.PLANNED

        updated_cohort = cohort_repository.update_cohort(
            ORGANIZATION_ID,
            created_course.id,
            created_cohort.id,
            CohortUpdate(
                name=f"Updated SC-006 Cohort {suffix}",
                start_date=date(2026, 10, 1),
                end_date=date(2026, 12, 20),
                delivery_mode=DeliveryMode.HYBRID,
                status=CohortStatus.ACTIVE,
            ),
        )
        assert updated_cohort is not None
        assert updated_cohort.delivery_mode is DeliveryMode.HYBRID
        assert updated_cohort.status is CohortStatus.ACTIVE

        assert (
            course_repository.get_course(
                OTHER_ORGANIZATION_ID,
                created_course.id,
            )
            is None
        )
        assert (
            topic_repository.get_topic(
                OTHER_ORGANIZATION_ID,
                created_course.id,
                created_topic.id,
            )
            is None
        )
        assert (
            cohort_repository.get_cohort(
                OTHER_ORGANIZATION_ID,
                created_course.id,
                created_cohort.id,
            )
            is None
        )

        blocked_topic = topic_repository.create_topic(
            OTHER_ORGANIZATION_ID,
            created_course.id,
            TopicCreate(
                title="Blocked cross-organisation topic",
                sequence_number=3,
                exam_domain=None,
                expected_hours=Decimal("1.00"),
            ),
        )
        assert blocked_topic is None

        blocked_cohort = cohort_repository.create_cohort(
            OTHER_ORGANIZATION_ID,
            created_course.id,
            CohortCreate(
                name="Blocked cross-organisation cohort",
                start_date=date(2027, 1, 1),
                end_date=None,
                delivery_mode=DeliveryMode.ONLINE,
            ),
        )
        assert blocked_cohort is None

    finally:
        if created_course_id is not None:
            with get_engine().begin() as connection:
                connection.execute(
                    text(
                        """
                        DELETE FROM cohorts
                        WHERE course_id = :course_id
                        """
                    ),
                    {"course_id": created_course_id},
                )
                connection.execute(
                    text(
                        """
                        DELETE FROM courses
                        WHERE
                            id = :course_id
                            AND organization_id = :organization_id
                        """
                    ),
                    {
                        "course_id": created_course_id,
                        "organization_id": ORGANIZATION_ID,
                    },
                )
