import time
from typing import Any

import msal
from azure.core.credentials import AccessToken
from azure.core.exceptions import ClientAuthenticationError

# Hints for the most common AADSTS errors met with the delegated (ROPC) flow
AADSTS_HINTS = {
    7000215: "Invalid client secret: check the client_secret of the module configuration.",
    7000218: "The application requires a client secret: set the client_secret in the module configuration.",
    50126: "Invalid username or password for the delegated account.",
    50076: "MFA is required for the delegated account: ROPC does not support MFA.",
    50079: "MFA registration is required for the delegated account: ROPC does not support MFA.",
    53003: "Access blocked by a Conditional Access policy for the delegated account.",
}

# Renew the token a bit before its real expiration
EXPIRATION_MARGIN_SECONDS = 300


def format_authentication_error(result: dict) -> str:
    """
    Build a readable message from an MSAL error response, including the AADSTS codes
    """
    message = f"{result.get('error')}: {result.get('error_description')}"
    hints = [AADSTS_HINTS[code] for code in result.get("error_codes", []) if code in AADSTS_HINTS]
    if hints:
        message += " Hint: " + " ".join(hints)

    return message


class ConfidentialUsernamePasswordCredential:
    """
    Get a delegated token (on behalf of the delegated account) with the username/password flow (ROPC),
    authenticating the application as a confidential client with its client secret.

    Unlike `azure.identity.UsernamePasswordCredential` (public client), it doesn't require
    "Allow public client flows" on the app registration.
    The token remains a delegated token: it is NOT an application (client credentials) token.
    """

    def __init__(self, tenant_id: str, client_id: str, client_secret: str, username: str, password: str) -> None:
        self._app = msal.ConfidentialClientApplication(
            client_id,
            client_credential=client_secret,
            authority=f"https://login.microsoftonline.com/{tenant_id}",
        )
        self._username = username
        self._password = password
        self._access_token: AccessToken | None = None

    def get_token(self, *scopes: str, claims: str | None = None, **kwargs: Any) -> AccessToken:
        # A claims challenge requires a new token
        if (
            not claims
            and self._access_token
            and self._access_token.expires_on - EXPIRATION_MARGIN_SECONDS > time.time()
        ):
            return self._access_token

        result = self._app.acquire_token_by_username_password(
            username=self._username,
            password=self._password,
            scopes=list(scopes),
            claims_challenge=claims,
        )
        if "access_token" not in result:
            raise ClientAuthenticationError(message=format_authentication_error(result))

        self._access_token = AccessToken(result["access_token"], int(time.time()) + int(result["expires_in"]))
        return self._access_token
