import logging
import math
import time
from collections.abc import Callable
from typing import Any

import httpx
from sekoia_automation.action import Action
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential
from urlscan import APIError, Client, RateLimitError
from urlscan.error import RateLimitRemainingError

from urlscan_modules import UrlScanModule
from urlscan_modules.models import UrlScanModuleConfiguration

# httpx logs one line per request, which floods the action logs.
logging.getLogger("httpx").setLevel(logging.WARNING)

MAX_RATE_LIMIT_RETRIES = 3
MAX_RATE_LIMIT_WAIT = 60
MAX_MESSAGE_LENGTH = 500


class ActionError(Exception):
    """An error whose message is shown to the playbook as is."""


def new_client(configuration: UrlScanModuleConfiguration) -> Client:
    return Client(configuration.api_key.strip(), base_url=configuration.base_url.rstrip("/"), timeout=30)


def describe_error(error: Exception) -> str:
    if isinstance(error, RateLimitError):
        return (
            f"urlscan.io quota exceeded for this action, retry after {math.ceil(error.rate_limit_reset_after)} seconds"
        )
    if isinstance(error, RateLimitRemainingError):
        return "urlscan.io quota exceeded for this action, retry later"
    if isinstance(error, APIError):
        if error.status == 401:
            return "Invalid urlscan.io API key"
        message = f"urlscan.io API error {error.status}: {error.message}"
        if error.description:
            message += f" - {error.description}"
        return message[:MAX_MESSAGE_LENGTH]
    if isinstance(error, httpx.TransportError):
        return f"urlscan.io could not be reached: {type(error).__name__}"
    return f"urlscan.io error: {type(error).__name__}"


def _is_server_error(error: BaseException) -> bool:
    return isinstance(error, httpx.TransportError) or (isinstance(error, APIError) and error.status >= 500)


class UrlScanAction(Action):
    module: UrlScanModule

    @property
    def base_url(self) -> str:
        return self.module.configuration.base_url.rstrip("/")

    def run(self, arguments: dict[str, Any]) -> dict[str, Any] | None:
        try:
            with new_client(self.module.configuration) as client:
                return self.perform(client, arguments)
        except ActionError as error:
            self.error(str(error))
        except (APIError, RateLimitRemainingError, httpx.TransportError) as error:
            self.error(describe_error(error))
        return None

    def perform(self, client: Client, arguments: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def call[T](self, fn: Callable[..., T], *args: Any, retry_server_errors: bool = True, **kwargs: Any) -> T:
        """Call the SDK, retrying server errors and waiting out rate limits."""
        rate_limit_retries = 0
        just_waited = False
        while True:
            try:
                return self._attempt(fn, args, kwargs, retry_server_errors)
            except KeyError as error:
                # The SDK reads error["message"]: an error body without it raises KeyError.
                raise ActionError("urlscan.io returned an unexpected error response") from error
            except RateLimitError as error:
                if rate_limit_retries >= MAX_RATE_LIMIT_RETRIES or error.rate_limit_reset_after > MAX_RATE_LIMIT_WAIT:
                    raise
                time.sleep(error.rate_limit_reset_after + 1)
                just_waited = True
            except RateLimitRemainingError:
                # The SDK remembers the quota headers of the 429 and may block the first call after the wait.
                if not just_waited or rate_limit_retries >= MAX_RATE_LIMIT_RETRIES:
                    raise
                time.sleep(2)
                just_waited = False
            rate_limit_retries += 1

    def _attempt[T](self, fn: Callable[..., T], args: tuple[Any, ...], kwargs: dict[str, Any], retry: bool) -> T:
        if not retry:
            return fn(*args, **kwargs)
        retrying = Retrying(
            stop=stop_after_attempt(4),
            wait=wait_exponential(multiplier=2, min=2, max=8),
            retry=retry_if_exception(_is_server_error),
            reraise=True,
        )
        return retrying(fn, *args, **kwargs)
