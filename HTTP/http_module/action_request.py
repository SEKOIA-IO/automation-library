import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import requests
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator
from requests.auth import AuthBase, HTTPBasicAuth, HTTPDigestAuth
from requests.exceptions import JSONDecodeError
from tenacity import Retrying, stop_after_attempt, wait_exponential

from .action_base import HTTPActionBase
from .helpers import params_as_dict


@lru_cache(maxsize=1)
def _load_action_request_enums() -> tuple[set[str], set[str]]:
    """Load enum values from the JSON schema to keep schema and Python validation in sync.

    This avoids duplicating enum definitions in code and schema by using the schema
    as the single source of truth.
    """
    schema_path = Path(__file__).resolve().parent.parent / "action_request.json"
    with schema_path.open("r", encoding="utf-8") as f:
        schema = json.load(f)

    properties = schema["arguments"]["properties"]
    methods = set(properties["method"].get("enum", []))
    auth_types = set(properties["auth_type"].get("enum", []))
    return methods, auth_types


class RequestActionArguments(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    url: HttpUrl
    method: str
    data: Any = None
    json_: dict[str, Any] | None = Field(default=None, alias="json")
    params: dict[str, Any] | str | None = None
    headers: dict[str, Any] | None = None
    verify_ssl: bool = True
    fail_on_http_error: bool = True
    auth_type: str | None = None
    auth_token: str = ""
    auth_username: str = ""
    auth_password: str = ""

    @field_validator("method")
    @classmethod
    def validate_method(cls, value: str) -> str:
        methods, _ = _load_action_request_enums()
        if value not in methods:
            raise ValueError(f"Invalid method '{value}', expected one of: {sorted(methods)}")
        return value

    @field_validator("auth_type")
    @classmethod
    def validate_auth_type(cls, value: str | None) -> str | None:
        if value is None:
            return value

        _, auth_types = _load_action_request_enums()
        if value not in auth_types:
            raise ValueError(f"Invalid auth_type '{value}', expected one of: {sorted(auth_types)}")
        return value


class RequestActionResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    reason: str | None
    status_code: int
    url: str
    headers: dict[str, Any]
    encoding: str | None
    elapsed: float
    text: str
    json_: Any = Field(default=None, alias="json")


class HTTPBearerAuth(AuthBase):
    def __init__(self, token: str) -> None:
        self._token = token

    def __call__(self, r: requests.PreparedRequest) -> requests.PreparedRequest:
        r.headers["Authorization"] = f"Bearer {self._token}"
        return r


class RequestAction(HTTPActionBase):
    """
    Action to request an HTTP resource
    """

    def _retry(self):
        return Retrying(
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )

    @staticmethod
    def _get_auth(arguments: RequestActionArguments) -> AuthBase | None:
        auth: AuthBase | None = None

        if arguments.auth_type == "Bearer":
            if not arguments.auth_token:
                raise ValueError("Token should not be empty for Bearer auth type")

            auth = HTTPBearerAuth(token=arguments.auth_token)

        elif arguments.auth_type == "Basic":
            if not arguments.auth_username or not arguments.auth_password:
                raise ValueError("Username/Password should not be empty for Basic auth type")

            auth = HTTPBasicAuth(username=arguments.auth_username, password=arguments.auth_password)

        elif arguments.auth_type == "Digest":
            if not arguments.auth_username or not arguments.auth_password:
                raise ValueError("Username/Password should not be empty for Digest auth type")

            auth = HTTPDigestAuth(username=arguments.auth_username, password=arguments.auth_password)

        return auth

    def run(self, arguments) -> dict:
        payload = dict(arguments)
        payload["params"] = params_as_dict(payload.get("params"))
        validated_arguments = RequestActionArguments.model_validate(payload)
        url = str(validated_arguments.url)

        auth = self._get_auth(validated_arguments)

        self.log(message=f"Request URL module started. Target URL: {url}", level="info")

        for attempt in self._retry():
            with attempt:
                response = requests.request(
                    method=validated_arguments.method,
                    url=url,
                    auth=auth,
                    data=validated_arguments.data,
                    json=validated_arguments.json_,
                    params=validated_arguments.params,
                    headers=validated_arguments.headers,
                    verify=validated_arguments.verify_ssl,
                )

        self.handle_response(response=response, url=url, fail_on_http_error=validated_arguments.fail_on_http_error)

        json_response = None
        if (
            "application/json" in response.headers.get("Content-Type", "").lower()
            and response.status_code != 204
            and response.content
        ):
            try:
                json_response = response.json()
            except JSONDecodeError:
                json_response = None

        result = RequestActionResult(
            reason=response.reason,
            status_code=response.status_code,
            url=response.url,
            headers=dict(response.headers),
            encoding=response.encoding,
            elapsed=response.elapsed.total_seconds(),
            text=response.text,
            json=json_response,
        )

        return result.model_dump(by_alias=True)
