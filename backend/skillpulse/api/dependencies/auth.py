"""FastAPI authentication and organisation authorization dependencies."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import SQLAlchemyError

from skillpulse.core.security import (
    AuthenticationConfigurationError,
    TokenVerificationError,
    get_token_verifier,
)
from skillpulse.db.identity import (
    AuthenticatedUser,
    MembershipRole,
    find_active_user_by_subject,
)

bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="CognitoAccessToken",
    description="Amazon Cognito access token",
)

BearerCredentials = Annotated[
    HTTPAuthorizationCredentials | None,
    Security(bearer_scheme),
]


@dataclass(frozen=True, slots=True)
class OrganizationAccess:
    """An authenticated user's authorized context for one organisation."""

    user: AuthenticatedUser
    organization_id: UUID
    roles: frozenset[MembershipRole]


def _unauthorized_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication credentials are invalid.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: BearerCredentials,
) -> AuthenticatedUser:
    """Authenticate a Cognito subject and resolve its active SkillPulse user."""

    if credentials is None:
        raise _unauthorized_exception()

    try:
        claims = get_token_verifier().verify(credentials.credentials)
    except TokenVerificationError as exc:
        raise _unauthorized_exception() from exc
    except AuthenticationConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is unavailable.",
        ) from exc

    subject: str = claims["sub"]

    try:
        user = find_active_user_by_subject(subject)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Identity service is unavailable.",
        ) from exc

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authenticated user is not authorized.",
        )

    return user


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


def require_organization_roles(
    *allowed_roles: MembershipRole,
) -> Callable[..., OrganizationAccess]:
    """Create a dependency requiring one allowed organisation role."""

    if not allowed_roles:
        raise ValueError("At least one organization role is required.")

    allowed_role_set = frozenset(allowed_roles)

    def authorize(
        organization_id: Annotated[
            UUID,
            Header(alias="X-Organization-ID"),
        ],
        current_user: CurrentUser,
    ) -> OrganizationAccess:
        roles = current_user.roles_for(organization_id)

        if roles.isdisjoint(allowed_role_set):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient organization permissions.",
            )

        return OrganizationAccess(
            user=current_user,
            organization_id=organization_id,
            roles=roles,
        )

    return authorize
