from abc import ABC

from pydantic import HttpUrl, TypeAdapter
from requests import Response
from requests.exceptions import HTTPError
from sekoia_automation.action import Action


class HTTPActionBase(Action, ABC):
    """Base class for HTTP actions with shared response handling."""

    @staticmethod
    def validate_url(u: str) -> None:
        # Validate URL with pydantic
        url_adapter = TypeAdapter(HttpUrl)
        url_adapter.validate_python(u)

    def handle_response(self, response: Response, url: str, fail_on_http_error: bool = True) -> None:
        status_code = response.status_code

        if 100 <= status_code < 200:
            self.log(
                message=f"HTTP Request returned informational response for {url}: {status_code} - {response.reason}",
                level="info",
            )
            return

        if 200 <= status_code < 300:
            return

        if 300 <= status_code < 400:
            self.log(
                message=f"HTTP Request returned redirection for {url}: {status_code} - {response.reason}",
                level="info",
            )
            return

        if 400 <= status_code < 500:
            self.log(
                message=f"HTTP Request returned client error for {url}: {status_code} - {response.reason}: {response.text}",
                level="error" if fail_on_http_error else "warning",
            )
            if fail_on_http_error:
                response.raise_for_status()
            return

        if 500 <= status_code < 600:
            self.log(
                message=f"HTTP Request returned server error for {url}: {status_code} - {response.reason}: {response.text}",
                level="critical" if fail_on_http_error else "error",
            )
            if fail_on_http_error:
                response.raise_for_status()
            return

        self.log(
            message=f"HTTP Request returned unexpected status for {url}: {status_code} - {response.reason}",
            level="warning",
        )

        if fail_on_http_error:
            raise HTTPError(
                f"Unexpected HTTP status for {url}: {status_code} - {response.reason}",
                response=response,
            )
