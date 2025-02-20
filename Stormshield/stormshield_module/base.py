from functools import cached_property
from posixpath import join as urljoin
from typing import Any
import re
import requests
from requests import RequestException, Response
from tenacity import (
    RetryError,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
)

from sekoia_automation.action import GenericAPIAction
from sekoia_automation.exceptions import MissingActionArgumentFileError


class StormshieldAction(GenericAPIAction):
    endpoint: str

    @cached_property
    def api_token(self):  # type: ignore
        return self.module.configuration["api_token"]

    @cached_property
    def base_url(self) -> str:
        config_url = self.module.configuration["url"].rstrip("/")
        api_path = "rest/api/v1"
        return urljoin(config_url, api_path)

    def get_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_token}"}

    def get_body(self, arguments: dict[str, Any]) -> dict[str, Any]:
        res: dict[str, Any] = {}
        for key, value in arguments.items():
            if isinstance(value, dict):
                res[key] = self.get_body(value)
            elif isinstance(value, bool):
                res[key] = str(value).lower()
            else:
                try:
                    new_key = key.replace("_path", "")
                    res[new_key] = self.json_argument(new_key, arguments)
                except MissingActionArgumentFileError:  # pragma: no cover
                    res[key] = value
        return res

    def treat_failed_response(self, response: Response) -> None:
        errors = {
            401: "Authentication failed: Invalid API key provided.",
            403: "Access denied: Insufficient permissions to access this resource.",
            404: "Resource not found: The requested resource could not be located.",
            409: "Conflict detected: The specified agent is not compatible with this feature.",
            500: "Internal server error: Rate limit exceeded.",
        }

        message = errors.get(response.status_code)

        if message:
            raise Exception(f"Error : {message}")

    def get_url(self, arguments: dict[str, Any]) -> str:
        match = re.findall("{(.*?)}", self.endpoint)
        for replacement in match:
            self.endpoint = self.endpoint.replace(f"{{{replacement}}}", str(arguments.pop(replacement)), 1)

        path = urljoin(self.base_url, self.endpoint.lstrip("/"))

        if self.query_parameters:
            query_arguments: list[str] = []

            for k in self.query_parameters:
                if k in arguments:
                    value = arguments.pop(k)
                    if isinstance(value, bool):
                        value = str(value).lower()
                    query_arguments.append(f"{k}={value}")

            if query_arguments:
                path += f"?{'&'.join(query_arguments)}"

        return path

    def get_response(self, url: str, body: dict[str, Any] | None, headers: dict[str, Any], verify: bool) -> Response:
        session = requests.Session()
        request = requests.Request(self.verb, url, json=body, headers=headers)
        prepared_request = request.prepare()
        self.log(
            level="info",
            message=f"Prepared request: url={prepared_request.url} headers={prepared_request.headers} body={prepared_request.body}",
        )
        return session.send(prepared_request, timeout=self.timeout, verify=verify)

    def run(self, arguments: dict[str, Any]) -> dict[str, Any] | None:
        headers = self.get_headers()
        url = self.get_url(arguments)
        body = self.get_body(arguments)

        try:
            for attempt in Retrying(
                stop=stop_after_attempt(10),
                wait=self._wait_param(),
                retry=retry_if_exception_type((RequestException, OSError)),
            ):
                with attempt:
                    response: Response = self.get_response(
                        url, body, headers, arguments.get("verify_certificate", True)
                    )
                    self.log(
                        level="info",
                        message=f"Response: status_code={response.status_code} content={response.content}",
                    )
                    content = response.json()

                    if content.get("errorCode"):
                        raise Exception(f"Error {content['errorCode']}: {content['errorMessage']}")

                    if content.get("status") in ["Pending", "Running"]:
                        continue

        except RetryError:
            self.log_timeout_error(url, arguments)
            return None

        if not response.ok:
            self.treat_failed_response(response)
            return None

        return response.json() if response.status_code != 204 else None
