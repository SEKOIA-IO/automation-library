from requests.auth import AuthBase


class TrendMicroVisionAuth(AuthBase):
    def __init__(self, api_key: str):
        self.__api_key = api_key

    def __call__(self, request):
        request.headers["Authorization"] = f"Bearer {self.__api_key}"
        return request
