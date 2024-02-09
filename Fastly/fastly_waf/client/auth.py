from requests.auth import AuthBase


class ApiKeyAuthentication(AuthBase):
    def __init__(self, email: str, token: str):
        self.__email = email
        self.__token = token

    def __call__(self, request):
        request.headers["X-Api-User"] = self.__email
        request.headers["X-Api-Token"] = self.__token
        return request
