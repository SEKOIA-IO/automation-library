from requests.auth import AuthBase


class ApiTokenAuthentication(AuthBase):
    """
    Implements a Requests's authentification for Hornetsecurity Control Panel API
    """

    def __init__(self, api_token: str):
        self.api_token = api_token

    def __call__(self, request):
        request.headers["Authorization"] = f"Token {self.api_token}"
        return request
