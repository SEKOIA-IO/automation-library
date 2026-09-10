from requests import PreparedRequest
from requests.auth import AuthBase


class HolmSecurityApiAuthentication(AuthBase):
    """Attach the Holm Security bearer token to outgoing requests.

    Holm Security expects the token in the ``Authorization`` header using the
    ``Token <api_token>`` scheme.
    """

    def __init__(self, token: str):
        self.token = token

    def __call__(self, request: PreparedRequest) -> PreparedRequest:
        request.headers["Authorization"] = f"Token {self.token}"
        return request
