from requests import PreparedRequest
from requests.auth import AuthBase


class ApiKeyAuthentication(AuthBase):
    """
    Implements a Requests's authentification for Okta API
    """

    def __init__(self, apikey: str) -> None:
        self.__apikey = apikey

    def __call__(self, request: PreparedRequest) -> PreparedRequest:
        request.headers["Authorization"] = f"SSWS {self.__apikey}"
        return request
