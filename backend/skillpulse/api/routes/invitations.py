"""Administrator API for inviting people to an organisation."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from skillpulse.api.dependencies.auth import (
    OrganizationAccess,
    require_organization_roles,
)
from skillpulse.core.cognito_admin import (
    CognitoAdminError,
    CognitoUserExistsError,
    delete_cognito_user,
    invite_cognito_user,
)
from skillpulse.db.identity import MembershipRole
from skillpulse.db.invitations import UserAlreadyExistsError, create_invitation
from skillpulse.schemas.invitations import InvitationCreate, InvitationResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin/invitations",
    tags=["invitations"],
)

_require_admin_access = require_organization_roles(MembershipRole.ADMIN)

AdminAccess = Annotated[
    OrganizationAccess,
    Depends(_require_admin_access),
]

_ALREADY_EXISTS = "A user with this email already exists."
_UNAVAILABLE = "The invitation service is unavailable."


def _undo_cognito_user(email: str) -> None:
    """Remove a Cognito user whose invitation could not be saved."""

    try:
        delete_cognito_user(email)
    except CognitoAdminError:
        logger.error("Could not remove Cognito user after a failed invitation.")


@router.post(
    "",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite a person to the organisation",
)
def create_organization_invitation(
    payload: InvitationCreate,
    access: AdminAccess,
) -> InvitationResponse:
    """Create a Cognito account, email a temporary password and save the invite."""

    try:
        auth_subject = invite_cognito_user(
            email=payload.email,
            full_name=payload.full_name,
        )
    except CognitoUserExistsError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, _ALREADY_EXISTS) from exc
    except (CognitoAdminError, ValueError) as exc:
        logger.warning("Cognito invitation failed: %s", exc.__class__.__name__)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _UNAVAILABLE) from exc

    try:
        invitation = create_invitation(
            organization_id=access.organization_id,
            email=payload.email,
            full_name=payload.full_name,
            role=payload.role,
            auth_subject=auth_subject,
        )
    except UserAlreadyExistsError as exc:
        _undo_cognito_user(payload.email)
        raise HTTPException(status.HTTP_409_CONFLICT, _ALREADY_EXISTS) from exc
    except SQLAlchemyError as exc:
        _undo_cognito_user(payload.email)
        logger.warning("Invitation save failed: %s", exc.__class__.__name__)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _UNAVAILABLE) from exc

    return InvitationResponse(
        user_id=invitation.user_id,
        membership_id=invitation.membership_id,
        email=payload.email,
        full_name=payload.full_name,
        role=payload.role,
    )
