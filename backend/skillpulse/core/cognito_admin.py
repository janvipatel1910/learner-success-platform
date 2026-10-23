"""Amazon Cognito administrator operations used for invitations."""

from functools import lru_cache
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from skillpulse.core.config import get_settings


class CognitoUserExistsError(Exception):
    """Raised when the email already has an account in the Cognito user pool."""


class CognitoAdminError(Exception):
    """Raised when a Cognito administrator call fails for any other reason."""


@lru_cache(maxsize=1)
def get_cognito_client() -> Any:
    """Return a Cognito client that uses the EC2 instance role credentials."""

    region, _, _ = get_settings().validated_cognito_configuration()
    return boto3.client("cognito-idp", region_name=region)


def _user_pool_id() -> str:
    _, user_pool_id, _ = get_settings().validated_cognito_configuration()
    return user_pool_id


def invite_cognito_user(*, email: str, full_name: str) -> str:
    """Create a Cognito user and email them a temporary password.

    Returns the new user's Cognito subject (``sub``).
    """

    try:
        response = get_cognito_client().admin_create_user(
            UserPoolId=_user_pool_id(),
            Username=email,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "email_verified", "Value": "true"},
                {"Name": "name", "Value": full_name},
            ],
            DesiredDeliveryMediums=["EMAIL"],
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "UsernameExistsException":
            raise CognitoUserExistsError(email) from exc
        raise CognitoAdminError("Cognito could not create the user.") from exc
    except BotoCoreError as exc:
        raise CognitoAdminError("Cognito could not be reached.") from exc

    for attribute in response["User"]["Attributes"]:
        if attribute["Name"] == "sub":
            return attribute["Value"]

    raise CognitoAdminError("Cognito did not return a user subject.")


def delete_cognito_user(email: str) -> None:
    """Delete a Cognito user, used to undo an invite that failed to save."""

    try:
        get_cognito_client().admin_delete_user(
            UserPoolId=_user_pool_id(),
            Username=email,
        )
    except (ClientError, BotoCoreError) as exc:
        raise CognitoAdminError("Cognito could not delete the user.") from exc
