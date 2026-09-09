"""Authenticated user API routes."""

from fastapi import APIRouter

from skillpulse.api.dependencies.auth import CurrentUser
from skillpulse.schemas.auth import CurrentUserResponse

router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
)


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="Return the authenticated SkillPulse user",
)
def read_current_user(
    current_user: CurrentUser,
) -> CurrentUserResponse:
    """Return the active user and their authorized memberships."""

    return CurrentUserResponse.model_validate(current_user)
