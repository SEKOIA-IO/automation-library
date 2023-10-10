import base64

from requests.auth import AuthBase


class TrendMicroAuthentication(AuthBase):
    def __init__(self, username: str, api_key: str):
        self.__username = username
        self.__api_key = api_key

    def __call__(self, request):
        request.headers["Authorization"] = "Basic %s" % self.get_signature()
        return request

    def get_signature(self) -> str:
        key = f"{self.__username}:{self.__api_key}".encode("utf-8")
        return base64.b64encode(key).decode("utf-8")
