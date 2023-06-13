from requests.auth import AuthBase


class ApiKeyAuthentication(AuthBase):
    """
    Implements a Requests's authentification for Jumpcloud Directory Insights API
    """

    def __init__(self, apikey: str):
        self.__apikey = apikey

    def __call__(self, request):
        request.headers["x-api-key"] = f"{self.__apikey}"
        return request
