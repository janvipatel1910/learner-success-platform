"""Organisation-scoped course management API routes."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from skillpulse.api.dependencies.auth import (
    OrganizationAccess,
    require_organization_roles,
)
from skillpulse.db import cohorts as cohort_repository
from skillpulse.db import courses as course_repository
from skillpulse.db import topics as topic_repository
from skillpulse.db.identity import MembershipRole
from skillpulse.schemas.catalog import (
    CohortCreate,
    CohortResponse,
    CohortUpdate,
    CourseCreate,
    CourseResponse,
    CourseUpdate,
    PaginatedResponse,
    TopicCreate,
    TopicResponse,
    TopicUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/catalog",
    tags=["catalog"],
)

_require_catalog_read_access = require_organization_roles(
    MembershipRole.STUDENT,
    MembershipRole.TUTOR,
    MembershipRole.ADMIN,
)
_require_catalog_admin_access = require_organization_roles(
    MembershipRole.ADMIN,
)

CatalogReadAccess = Annotated[
    OrganizationAccess,
    Depends(_require_catalog_read_access),
]
CatalogAdminAccess = Annotated[
    OrganizationAccess,
    Depends(_require_catalog_admin_access),
]


def _course_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Course was not found.",
    )


def _catalog_unavailable(exc: SQLAlchemyError) -> HTTPException:
    logger.warning(
        "Catalog database operation failed: %s",
        exc.__class__.__name__,
    )
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Catalog service is unavailable.",
    )


@router.get(
    "/courses",
    response_model=PaginatedResponse[CourseResponse],
)
def list_course_records(
    access: CatalogReadAccess,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedResponse[CourseResponse]:
    """List courses belonging to the authorized organisation."""

    try:
        courses, total = course_repository.list_courses(
            access.organization_id,
            limit=limit,
            offset=offset,
        )
    except SQLAlchemyError as exc:
        raise _catalog_unavailable(exc) from exc

    return PaginatedResponse[CourseResponse](
        items=courses,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/courses/{course_id}",
    response_model=CourseResponse,
)
def get_course_record(
    course_id: UUID,
    access: CatalogReadAccess,
) -> CourseResponse:
    """Return one course from the authorized organisation."""

    try:
        course = course_repository.get_course(
            access.organization_id,
            course_id,
        )
    except SQLAlchemyError as exc:
        raise _catalog_unavailable(exc) from exc

    if course is None:
        raise _course_not_found()

    return course


@router.post(
    "/courses",
    response_model=CourseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_course_record(
    payload: CourseCreate,
    access: CatalogAdminAccess,
) -> CourseResponse:
    """Create a course as an organisation administrator."""

    try:
        return course_repository.create_course(
            access.organization_id,
            payload,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Course conflicts with an existing record.",
        ) from exc
    except SQLAlchemyError as exc:
        raise _catalog_unavailable(exc) from exc


@router.put(
    "/courses/{course_id}",
    response_model=CourseResponse,
)
def update_course_record(
    course_id: UUID,
    payload: CourseUpdate,
    access: CatalogAdminAccess,
) -> CourseResponse:
    """Update a course as an organisation administrator."""

    try:
        course = course_repository.update_course(
            access.organization_id,
            course_id,
            payload,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Course conflicts with an existing record.",
        ) from exc
    except SQLAlchemyError as exc:
        raise _catalog_unavailable(exc) from exc

    if course is None:
        raise _course_not_found()

    return course
def _topic_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Topic was not found.",
    )


@router.get(
    "/courses/{course_id}/topics",
    response_model=PaginatedResponse[TopicResponse],
)
def list_topic_records(
    course_id: UUID,
    access: CatalogReadAccess,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedResponse[TopicResponse]:
    """List topics from an organisation-owned course."""

    try:
        course = course_repository.get_course(
            access.organization_id,
            course_id,
        )
        if course is None:
            raise _course_not_found()

        topics, total = topic_repository.list_topics(
            access.organization_id,
            course_id,
            limit=limit,
            offset=offset,
        )
    except SQLAlchemyError as exc:
        raise _catalog_unavailable(exc) from exc

    return PaginatedResponse[TopicResponse](
        items=topics,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/courses/{course_id}/topics/{topic_id}",
    response_model=TopicResponse,
)
def get_topic_record(
    course_id: UUID,
    topic_id: UUID,
    access: CatalogReadAccess,
) -> TopicResponse:
    """Return one topic from an organisation-owned course."""

    try:
        topic = topic_repository.get_topic(
            access.organization_id,
            course_id,
            topic_id,
        )
    except SQLAlchemyError as exc:
        raise _catalog_unavailable(exc) from exc

    if topic is None:
        raise _topic_not_found()

    return topic


@router.post(
    "/courses/{course_id}/topics",
    response_model=TopicResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_topic_record(
    course_id: UUID,
    payload: TopicCreate,
    access: CatalogAdminAccess,
) -> TopicResponse:
    """Create a topic inside an organisation-owned course."""

    try:
        topic = topic_repository.create_topic(
            access.organization_id,
            course_id,
            payload,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Topic conflicts with an existing record.",
        ) from exc
    except SQLAlchemyError as exc:
        raise _catalog_unavailable(exc) from exc

    if topic is None:
        raise _course_not_found()

    return topic


@router.put(
    "/courses/{course_id}/topics/{topic_id}",
    response_model=TopicResponse,
)
def update_topic_record(
    course_id: UUID,
    topic_id: UUID,
    payload: TopicUpdate,
    access: CatalogAdminAccess,
) -> TopicResponse:
    """Update a topic inside an organisation-owned course."""

    try:
        topic = topic_repository.update_topic(
            access.organization_id,
            course_id,
            topic_id,
            payload,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Topic conflicts with an existing record.",
        ) from exc
    except SQLAlchemyError as exc:
        raise _catalog_unavailable(exc) from exc

    if topic is None:
        raise _topic_not_found()

    return topic
def _cohort_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Cohort was not found.",
    )


@router.get(
    "/courses/{course_id}/cohorts",
    response_model=PaginatedResponse[CohortResponse],
)
def list_cohort_records(
    course_id: UUID,
    access: CatalogReadAccess,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedResponse[CohortResponse]:
    """List cohorts from an organisation-owned course."""

    try:
        course = course_repository.get_course(
            access.organization_id,
            course_id,
        )
        if course is None:
            raise _course_not_found()

        cohorts, total = cohort_repository.list_cohorts(
            access.organization_id,
            course_id,
            limit=limit,
            offset=offset,
        )
    except SQLAlchemyError as exc:
        raise _catalog_unavailable(exc) from exc

    return PaginatedResponse[CohortResponse](
        items=cohorts,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/courses/{course_id}/cohorts/{cohort_id}",
    response_model=CohortResponse,
)
def get_cohort_record(
    course_id: UUID,
    cohort_id: UUID,
    access: CatalogReadAccess,
) -> CohortResponse:
    """Return one cohort from an organisation-owned course."""

    try:
        cohort = cohort_repository.get_cohort(
            access.organization_id,
            course_id,
            cohort_id,
        )
    except SQLAlchemyError as exc:
        raise _catalog_unavailable(exc) from exc

    if cohort is None:
        raise _cohort_not_found()

    return cohort


@router.post(
    "/courses/{course_id}/cohorts",
    response_model=CohortResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_cohort_record(
    course_id: UUID,
    payload: CohortCreate,
    access: CatalogAdminAccess,
) -> CohortResponse:
    """Create a cohort inside an organisation-owned course."""

    try:
        cohort = cohort_repository.create_cohort(
            access.organization_id,
            course_id,
            payload,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cohort conflicts with an existing record.",
        ) from exc
    except SQLAlchemyError as exc:
        raise _catalog_unavailable(exc) from exc

    if cohort is None:
        raise _course_not_found()

    return cohort


@router.put(
    "/courses/{course_id}/cohorts/{cohort_id}",
    response_model=CohortResponse,
)
def update_cohort_record(
    course_id: UUID,
    cohort_id: UUID,
    payload: CohortUpdate,
    access: CatalogAdminAccess,
) -> CohortResponse:
    """Update a cohort inside an organisation-owned course."""

    try:
        cohort = cohort_repository.update_cohort(
            access.organization_id,
            course_id,
            cohort_id,
            payload,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cohort conflicts with an existing record.",
        ) from exc
    except SQLAlchemyError as exc:
        raise _catalog_unavailable(exc) from exc

    if cohort is None:
        raise _cohort_not_found()

    return cohort
