from requests import PreparedRequest
from requests.auth import AuthBase


class MoknApiKeyAuth(AuthBase):
    def __init__(self, api_token: str):
        self._api_token = api_token

    def __call__(self, request: PreparedRequest) -> PreparedRequest:
        request.headers["Accept"] = "application/json"
        request.headers["Content-Type"] = "application/json"
        request.headers["X-MOKN-API-KEY"] = self._api_token
        return request
