import time
from abc import abstractmethod
from datetime import UTC, datetime, timedelta
from functools import cached_property
from typing import Any, ClassVar

import requests
from pydantic import BaseModel, Field
from sekoia_automation.connector import Connector
from sekoia_automation.module import Module
from urllib3.exceptions import HTTPError as BaseHTTPError

from sophos_module.client import SophosApiClient
from sophos_module.client.auth import SophosApiAuthentication
from sophos_module.client.errors import format_http_error, is_configuration_error
from sophos_module.client.exceptions import SophosApiAuthenticationError
from sophos_module.logging import get_logger
from sophos_module.metrics import FORWARD_EVENTS_DURATION

logger = get_logger()


class SophosConfiguration(BaseModel):
    oauth2_authorization_url: str = Field(..., description="The url to the OAuth2 authorization")
    api_host: str = Field(
        ...,
        description="API Url of the Sophos Central API (e.g. 'https://api-{dataRegion}.central.sophos.com')",
    )
    client_id: str = Field(..., description="OAuth2 client identifier")
    client_secret: str = Field(..., description="OAuth2 client secret", json_schema_extra={"secret": True})
    graphql_api_url: str = Field(
        "https://api.taegis.sophos.com", description="URL of the Sophos Fusion GraphQL API (Detections)"
    )


class SophosModule(Module):
    configuration: SophosConfiguration


class SophosConnector(Connector):
    """
    Base of the Sophos triggers: authentication, client, and the collection loop with its error policy.

    - recoverable errors (HTTP errors, network errors): logged with a stable message, the loop goes on;
    - configuration errors (HTTP 401/403: credentials, role, licence): logged at most once per
      `configuration_error_log_period`, since repeating them every cycle does not help the user;
    - authentication refused (SophosApiAuthenticationError): critical, the trigger stops;
    - any other exception: logged with its traceback, then raised.
    """

    module: SophosModule

    # shown in the start and stop messages, e.g. "Sophos events trigger"
    name: ClassVar[str] = "Sophos trigger"
    # what failed, in the error messages of the collection, e.g. "Failed to fetch the Sophos events"
    collect_error_action: ClassVar[str] = "Failed to collect from Sophos"
    configuration_error_log_period: ClassVar[timedelta] = timedelta(hours=1)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._error_logged_at: dict[str, datetime] = {}

    @cached_property
    def authentication(self) -> SophosApiAuthentication:
        return SophosApiAuthentication(
            api_host=self.module.configuration.api_host,
            authorization_url=self.module.configuration.oauth2_authorization_url,
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
        )

    @cached_property
    def client(self) -> SophosApiClient:
        return SophosApiClient(auth=self.authentication, graphql_api_url=self.module.configuration.graphql_api_url)

    @abstractmethod
    def collect(self) -> None:
        """Run one collection cycle."""
        raise NotImplementedError

    def before_collect(self) -> None:
        """Hook run before each collection cycle, outside of the error handling of the collection."""

    def log_error(self, message: str, configuration_error: bool = False) -> None:
        """
        Log an error for the user.

        Configuration errors are logged at most once per period: they last until the customer acts.
        The other errors rely on the deduplication of the SDK (identical messages within 60 seconds).
        """
        if configuration_error:
            now = datetime.now(UTC)
            logged_at = self._error_logged_at.get(message)
            if logged_at is not None and now - logged_at < self.configuration_error_log_period:
                logger.error("Configuration error still present", error=message)
                return
            self._error_logged_at[message] = now

        self.log(message=message, level="error")

    def log_http_error(self, action: str, response: requests.Response) -> None:
        """Log a failed Sophos API call: stable message for the user, full response in the pod logs."""
        self.log_error(
            format_http_error(action, response), configuration_error=is_configuration_error(response.status_code)
        )
        logger.error(action, status_code=response.status_code, url=response.url, response=response.text[:1000])

    def handle_collect_error(self, error: Exception) -> None:
        """Log a recoverable error of a collection cycle."""
        response = getattr(error, "response", None)
        if isinstance(response, requests.Response):
            self.log_http_error(self.collect_error_action, response)
            return

        # network error or HTTP error without response: the exception type only, no request ids
        self.log_error(f"{self.collect_error_action}: {type(error).__name__}")
        logger.error(self.collect_error_action, error=repr(error))

    def run(self) -> None:
        self.log(message=f"{self.name} has started", level="info")

        try:
            while self.running:
                start = time.time()

                try:
                    # Authenticate with the Sophos API (cached token): a temporary failure is retried next cycle,
                    # refused credentials (SophosApiAuthenticationError) stop the trigger
                    self.authentication.get_credentials()
                    self.before_collect()
                    self.collect()
                except (requests.RequestException, BaseHTTPError) as error:
                    self.handle_collect_error(error)
                except SophosApiAuthenticationError:
                    raise
                except Exception as error:
                    self.log_exception(error, message="An unknown exception occurred")
                    raise

                # compute the duration of the last collection
                duration = int(time.time() - start)
                FORWARD_EVENTS_DURATION.labels(intake_key=self.configuration.intake_key).observe(duration)

                # sleep the remaining time of the cycle
                delta_sleep = self.configuration.frequency - duration
                if delta_sleep > 0:
                    time.sleep(delta_sleep)

        except SophosApiAuthenticationError as error:
            # Log a critical message, that will stop the connector, when the authentication fails
            self.log(message=str(error), level="critical")

        finally:
            self.log(message=f"{self.name} has stopped", level="info")
