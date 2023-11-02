from datetime import datetime

from requests.auth import AuthBase

import helpers


class ApiKeyAuthentication(AuthBase):
    """
    Implements a Requests's authentification for Okta API
    """

    def __init__(self, public_key: str, private_key: str):
        self.__public_key = public_key
        self.__private_key = private_key

    def __call__(self, request):
        d = datetime.utcnow()
        now = d.strftime("%Y%m%dT%H%M%S")
        query = helpers.extract_query(request)
        sig = helpers.generate_darktrace_signature(self.__public_key, self.__private_key, query, now)
        request.headers.update({"DTAPI-Token": self.__public_key, "DTAPI-Date": now, "DTAPI-Signature": sig})

        return request
