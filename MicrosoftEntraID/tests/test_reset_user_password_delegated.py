from unittest.mock import patch

import pytest
from azure.core.exceptions import ClientAuthenticationError

from azure_ad.delegated_credential import ConfidentialUsernamePasswordCredential
from azure_ad.user import ResetUserPasswordAction
from tests.test_actions import configured_action

SCOPE = "UserAuthenticationMethod.ReadWrite.All"

AADSTS7000218_RESPONSE = {
    "error": "invalid_client",
    "error_description": "AADSTS7000218: The request body must contain the following parameter: "
    "'client_assertion' or 'client_secret'.",
    "error_codes": [7000218],
}


def build_credential() -> ConfidentialUsernamePasswordCredential:
    return ConfidentialUsernamePasswordCredential(
        tenant_id="tenant_id",
        client_id="client_id",
        client_secret="client_secret",
        username="username",
        password="password",
    )


def test_client_uses_confidential_credential_when_client_secret_is_set():
    action = configured_action(ResetUserPasswordAction)

    with (
        patch("azure_ad.user.ConfidentialUsernamePasswordCredential") as confidential_credential,
        patch("azure_ad.user.UsernamePasswordCredential") as public_credential,
    ):
        assert action.client is not None

    confidential_credential.assert_called_once_with(
        tenant_id="azefazefazegazetazeytazeyaze",
        client_id="e139c076-122f-4c2e-9d0d-azefazegazeg",
        client_secret="client_secret",
        username="username",
        password="password",
    )
    public_credential.assert_not_called()


def test_client_falls_back_to_public_client_without_client_secret():
    action = configured_action(ResetUserPasswordAction)
    action.module.configuration = {**action.module.configuration.model_dump(), "client_secret": ""}

    with (
        patch("azure_ad.user.ConfidentialUsernamePasswordCredential") as confidential_credential,
        patch("azure_ad.user.UsernamePasswordCredential") as public_credential,
    ):
        assert action.client is not None

    public_credential.assert_called_once()
    confidential_credential.assert_not_called()


def test_credential_gets_delegated_token_as_confidential_client():
    with patch("azure_ad.delegated_credential.msal.ConfidentialClientApplication") as application_class:
        application = application_class.return_value
        application.acquire_token_by_username_password.return_value = {"access_token": "token", "expires_in": 3600}

        credential = build_credential()
        first_token = credential.get_token(SCOPE, claims=None, enable_cae=False)
        second_token = credential.get_token(SCOPE, claims=None, enable_cae=False)

    # The secret is sent to authenticate the app, but the token is obtained with the delegated account (ROPC)
    application_class.assert_called_once_with(
        "client_id",
        client_credential="client_secret",
        authority="https://login.microsoftonline.com/tenant_id",
    )
    application.acquire_token_by_username_password.assert_called_once_with(
        username="username", password="password", scopes=[SCOPE], claims_challenge=None
    )
    application.acquire_token_for_client.assert_not_called()
    assert first_token.token == "token"
    assert second_token is first_token


def test_credential_requests_new_token_on_claims_challenge():
    with patch("azure_ad.delegated_credential.msal.ConfidentialClientApplication") as application_class:
        application = application_class.return_value
        application.acquire_token_by_username_password.return_value = {"access_token": "token", "expires_in": 3600}

        credential = build_credential()
        credential.get_token(SCOPE)
        credential.get_token(SCOPE, claims='{"access_token": {}}')

    assert application.acquire_token_by_username_password.call_count == 2


def test_credential_raises_error_with_aadsts_code():
    with patch("azure_ad.delegated_credential.msal.ConfidentialClientApplication") as application_class:
        application_class.return_value.acquire_token_by_username_password.return_value = AADSTS7000218_RESPONSE

        with pytest.raises(ClientAuthenticationError, match="AADSTS7000218") as error:
            build_credential().get_token(SCOPE)

    assert "Hint: The application requires a client secret" in error.value.message


@pytest.mark.asyncio
async def test_reset_user_password_reports_authentication_error():
    action = configured_action(ResetUserPasswordAction)
    authentication_error = ClientAuthenticationError(message="invalid_client: AADSTS50126: Invalid credentials.")

    with (
        patch("azure_ad.user.ResetUserPasswordAction.query_list_user_methods", side_effect=authentication_error),
        patch("azure_ad.user.ResetUserPasswordAction.query_reset_user_password") as reset_password,
    ):
        results = await action.run({"userPrincipalName": "test@test.test", "userNewPassword": "test_password"})

    assert results is None
    assert "Authentication of the delegated account failed" in action.error_message
    assert "AADSTS50126" in action.error_message
    reset_password.assert_not_called()


@pytest.mark.asyncio
async def test_reset_user_password_validation_message():
    action = configured_action(ResetUserPasswordAction)

    with pytest.raises(ValueError, match="'userNewPassword' and either 'id' or 'userPrincipalName' must be specified"):
        await action.run({"userPrincipalName": "test@test.test"})
