import requests
from requests.auth import AuthBase, HTTPBasicAuth, HTTPDigestAuth
from requests.exceptions import JSONDecodeError
from sekoia_automation.action import Action
from tenacity import Retrying, stop_after_attempt, wait_exponential

from http_module.helpers import params_as_dict


class BearerAuth(AuthBase):
    def __init__(self, token: str) -> None:
        self._token = token

    def __call__(self, r: requests.Request) -> requests.Request:
        r.headers["Authorization"] = f"Bearer {self._token}"
        return r


class RequestAction(Action):
    """
    Action to request an HTTP resource
    """

    def _retry(self):
        return Retrying(
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )

    def run(self, arguments) -> dict:
        method = arguments.get("method")
        data = arguments.get("data")
        json = arguments.get("json")
        params = params_as_dict(arguments.get("params"))
        url = arguments.get("url")
        headers = arguments.get("headers")
        verify = arguments.get("verify_ssl", True)
        fail_on_http_error = arguments.get("fail_on_http_error", True)

        auth_type = arguments.get("auth_type")
        auth_token = arguments.get("auth_token", "")
        auth_username = arguments.get("auth_username", "")
        auth_password = arguments.get("auth_password", "")

        auth = None

        if auth_type == "Token":
            if not auth_token:
                raise ValueError("Token should not be empty for Token auth type")

            auth = BearerAuth(token=auth_token)

        elif auth_type == "Basic":
            if not auth_username or not auth_password:
                raise ValueError("Username/Password should not be empty for Basic auth type")

            auth = HTTPBasicAuth(username=auth_username, password=auth_password)

        elif auth_type == "Digest":
            if not auth_username or not auth_password:
                raise ValueError("Username/Password should not be empty for Digest auth type")

            auth = HTTPDigestAuth(username=auth_username, password=auth_password)

        self.log(message=f"Request URL module started. Target URL: {url}", level="info")

        for attempt in self._retry():
            with attempt:
                response = requests.request(
                    method=method,
                    url=url,
                    auth=auth,
                    data=data,
                    json=json,
                    params=params,
                    headers=headers,
                    verify=verify,
                )

        if fail_on_http_error and not response.ok:
            # Will end action as in error
            self.error(f"HTTP Request failed: {url} with {response.status_code}")

        json_response = None
        if (
            "application/json" in response.headers.get("Content-Type", "").lower()
            and response.status_code != 204
            and response.content
        ):
            try:
                json_response = response.json()
            except JSONDecodeError as e:
                json_response = None

        return {
            "reason": response.reason,
            "status_code": response.status_code,
            "url": response.url,
            "headers": dict(response.headers),
            "encoding": response.encoding,
            "elapsed": response.elapsed.total_seconds(),
            "text": response.text,
            "json": json_response,
        }
