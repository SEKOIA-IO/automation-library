from requests.auth import AuthBase


class ApiKeyAuthentication(AuthBase):
    def __init__(self, token: str):
        self.__token = token

    def __call__(self, request):
        request.headers["Authorization"] = f"Bearer {self.__token}"
        return request
