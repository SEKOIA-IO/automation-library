from requests import PreparedRequest
from requests.auth import AuthBase


class ThinksCanaryAuth(AuthBase):
    def __init__(self, auth_token: str):
        self.__auth_token = auth_token

    def __call__(self, request: PreparedRequest) -> PreparedRequest:
        request.headers["X-Canary-Auth-Token"] = self.__auth_token
        request.headers["Content-Type"] = "application/json"
        return request
