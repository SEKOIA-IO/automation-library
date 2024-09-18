from requests.auth import AuthBase


class ApiKeyAuthentication(AuthBase):
    def __init__(self, api_token: str):
        self.__api_token = api_token

    def __call__(self, request):
        request.headers["Authorization"] = f"Bearer {self.__api_token}"
        return request
