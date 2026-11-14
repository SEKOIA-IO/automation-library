from requests.auth import AuthBase
from requests.models import PreparedRequest


class CortexAuthentication(AuthBase):
    """
    Implements a Requests's authentification for Cortex EDR API
    """

    def __init__(self, api_key: str, api_key_id: str):
        self.__api_key = api_key
        self.__api_key_id = api_key_id

    def __call__(self, request: PreparedRequest) -> PreparedRequest:
        """Create the corresponding header for requests"""

        request.headers["x-xdr-auth-id"] = self.__api_key_id
        request.headers["Authorization"] = self.__api_key
        request.headers["Content-Type"] = "application/json"

        return request
