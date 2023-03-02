from requests.auth import AuthBase


class ApiKeyAuthentication(AuthBase):
    """
    Implements a Requests's authentification for Okta API
    """

    def __init__(self, apikey: str):
        self.__apikey = apikey

    def __call__(self, request):
        request.headers["Authorization"] = f"SSWS {self.__apikey}"
        return request
