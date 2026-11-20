import base64
import json
from functools import cached_property
from typing import TYPE_CHECKING, Any
from urllib.parse import quote, urlsplit

import requests
from sekoia_automation.module import ModuleItem

from easyvista_modules import EasyVistaModule
from easyvista_modules.client import ApiClient, CredentialConfigurationError


def json_body(response: requests.Response) -> Any:
    if not response.content:
        return None
    try:
        return response.json()
    except ValueError:
        return None


def json_body_text(text: str) -> Any:
    try:
        return json.loads(text)
    except ValueError:
        return None


class EasyVistaHttpMixin(ModuleItem):
    module: EasyVistaModule

    if TYPE_CHECKING:

        def error(self, message: str) -> None: ...

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(self.module.configuration)

    def redact(self, message: str) -> str:
        config = self.module.configuration
        secrets = [config.token, config.password]
        if config.username and config.password:
            credentials = f"{config.username}:{config.password}"
            # requests encodes Basic credentials as Latin-1. Also cover UTF-8 echoes.
            for encoding in ("latin-1", "utf-8"):
                try:
                    encoded = credentials.encode(encoding)
                except UnicodeEncodeError:
                    continue
                secrets.append(base64.b64encode(encoded).decode("ascii"))
        for secret in sorted((value for value in secrets if value), key=len, reverse=True):
            message = message.replace(secret, "[REDACTED]")
        return message

    def redact_json(self, data: Any) -> Any:
        """Mask decoded strings before JSON escaping can obscure credentials."""
        if isinstance(data, str):
            return self.redact(data)
        if isinstance(data, list):
            return [self.redact_json(value) for value in data]
        if isinstance(data, dict):
            return {self.redact(key): self.redact_json(value) for key, value in data.items()}
        return data

    def response_error(self, response: requests.Response) -> str:
        data = self.redact_json(json_body(response))
        if isinstance(data, dict) and "error" in data:
            return self.redact(str(data["error"]))
        if isinstance(data, dict) and isinstance(data.get("message"), str):
            # Some 590 responses wrap the useful error in a JSON-encoded message.
            nested = self.redact_json(json_body_text(data["message"]))
            detail = nested["error"] if isinstance(nested, dict) and "error" in nested else data["message"]
            return self.redact(str(detail))[:500]
        if data is not None:
            return self.redact(json.dumps(data, ensure_ascii=False))[:500]
        return self.redact(response.text)[:500]

    def _handle_response(self, response: requests.Response, suffix: str = "", *, file_response: bool = False) -> bool:
        if file_response and 200 <= response.status_code < 300:
            return True
        try:
            data = response.json() if response.content else None
        except ValueError:
            if 200 <= response.status_code < 300:
                self.error("EasyVista API returned a non-JSON response where JSON was expected")
                return False
            data = None
        if 200 <= response.status_code < 300 and not (isinstance(data, dict) and "error" in data):
            return True
        method = str(response.request.method)
        path = urlsplit(str(response.request.url)).path
        detail = self.response_error(response)
        if response.status_code == 401:
            detail = "Authentication failed (check credentials / tenant_id): " + detail
        elif response.status_code == 403:
            detail = f"Permission denied for {method} {path}: {detail}"
        self.error(self.redact(f"EasyVista API error {response.status_code} on {method} {path}: {detail}{suffix}"))
        return False

    def request(
        self, method: str, path: str, *, check: bool = True, file_response: bool = False, **kwargs
    ) -> requests.Response | None:
        config = self.module.configuration
        url = f"{config.base_url}/api/v1/{quote(config.tenant_id, safe='')}{path}"
        try:
            response = self.client.request(method, url, **kwargs)
        except CredentialConfigurationError as exc:
            self.error(str(exc))
            return None
        except ValueError as exc:
            self.error(self.redact(str(exc)))
            return None
        except requests.RequestException as exc:
            self.error(self.redact(f"EasyVista API unreachable: {type(exc).__name__}: {exc}"))
            return None
        if check and not self._handle_response(response, file_response=file_response):
            return None
        return response

    def get(self, path: str, **kwargs) -> Any:
        return self.json_object(self.request("GET", path, **kwargs), path)

    def json_object(self, response: requests.Response | None, path: str) -> Any:
        if response is None:
            return None
        data = json_body(response)
        if not isinstance(data, dict):
            self.error(f"EasyVista API returned an empty or non-object response on GET {path}")
            return None
        return data
