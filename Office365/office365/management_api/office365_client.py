import asyncio
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from urllib.parse import urlencode, urlparse, urlunsplit

import msal
from aiohttp import ClientError
from aiohttp.client import ClientResponse, ClientSession

from .constants import OFFICE365_ACTIVE_SUBSCRIPTION_STATUS, OFFICE365_AUTHORITY_DEFAULT, OFFICE365_URL_BASE
from .errors import (
    ApplicationAuthenticationFailed,
    FailedToActivateO365Subscription,
    FailedToActivateSomeO365Subscriptions,
    FailedToGetO365AuditContent,
    FailedToGetO365SubscriptionContents,
    FailedToListO365Subscriptions,
    SessionClosedError,
)
from .logging import get_logger

logger = get_logger()

# Content types of the Office 365 Management Activity API collected by the connector
EXPECTED_SUBSCRIPTIONS = {"Audit.AzureActiveDirectory", "Audit.SharePoint", "Audit.General", "Audit.Exchange"}


class Office365API:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        tenant_id: str,
        publisher_id: str | None = None,
    ):
        self.client_id = client_id
        self.tenant_id = tenant_id
        self._app = msal.ConfidentialClientApplication(
            client_id,
            client_credential=client_secret,
            authority=self._normalize_office365_url(),
        )
        self._session = ClientSession()
        self._token_expiration = 0.0
        self._publisher_id = publisher_id

    async def close(self) -> None:
        """
        Close the client
        """
        await self._session.close()

    async def _authenticate_client(self) -> None:
        """
        Authenticate the application
        """
        scopes = ["https://manage.office.com/.default"]
        response = await asyncio.get_event_loop().run_in_executor(None, self._app.acquire_token_for_client, scopes)

        if "access_token" not in response:
            logger.error(
                "Failed to get access token",
                response=response,
            )
            raise ApplicationAuthenticationFailed("Failed to get access token", response=response)

        if response.get("token_type", "").lower() != "bearer":
            logger.error(
                "Bearer Authentication not supported",
                response=response,
            )
            raise ApplicationAuthenticationFailed("Bearer Authentication not supported", response=response)

        self._token_expiration = time.time() + int(response["expires_in"])
        self._session.headers["Authorization"] = "{} {}".format(response["token_type"], response["access_token"])

    @asynccontextmanager
    async def _fresh_session(self) -> AsyncGenerator[ClientSession]:
        """
        Return a fresh authenticated session

        Check the expiration time of the current token and renew it if expired
        """
        if self._session.closed:
            raise SessionClosedError("Office365 client session is already closed")

        if time.time() > self._token_expiration - 10:
            await self._authenticate_client()

        yield self._session

    async def activate_subscriptions(self) -> set[str]:
        """
        Activate the expected subscriptions for a tenant

        Each missing content type is activated independently: a failure on one content type
        does not prevent the activation of the others.

        :return: The content types whose subscription is active
        :raises FailedToActivateSomeO365Subscriptions: if at least one content type failed to activate
        """
        already_enabled_types = set(await self.list_subscriptions())
        missing_types = EXPECTED_SUBSCRIPTIONS - already_enabled_types

        active_types = set(already_enabled_types)
        failures: dict[str, FailedToActivateO365Subscription] = {}

        # Activate missing types
        try:
            async with self._fresh_session() as session:
                for content_type in sorted(missing_types):
                    try:
                        await self._activate_subscription(session, content_type)
                        active_types.add(content_type)
                    except FailedToActivateO365Subscription as error:
                        failures[content_type] = error

        except RuntimeError as exc:
            if "Session is closed" in str(exc):
                raise SessionClosedError(str(exc)) from exc
            raise

        if failures:
            raise FailedToActivateSomeO365Subscriptions(failures=failures, active_content_types=active_types)

        return active_types

    async def _activate_subscription(self, session: ClientSession, content_type: str) -> None:
        """
        Activate the subscription for one content type

        :raises FailedToActivateO365Subscription: if the subscription could not be activated
        """
        base_url = OFFICE365_URL_BASE.format(tenant_id=self.tenant_id)
        try:
            response = await session.post(f"{base_url}/subscriptions/start", params={"contentType": content_type})
        except (ClientError, TimeoutError) as exc:
            # Record the transport error for this content type only, so the other content types are still activated.
            # A closed session (RuntimeError) and the cancellation (BaseException) are propagated.
            raise FailedToActivateO365Subscription(
                content_type=content_type, error_message=f"{type(exc).__name__}: {exc}"
            ) from exc

        try:
            subscription = await response.json(content_type=None)
        except (ClientError, TimeoutError) as exc:
            # The body couldn't be read: the outcome of the activation is unknown
            raise FailedToActivateO365Subscription(
                content_type=content_type, status_code=response.status, error_message=f"{type(exc).__name__}: {exc}"
            ) from exc
        except ValueError:
            # The body is not JSON (json.JSONDecodeError is a ValueError): rely on the HTTP status code
            subscription = None

        if isinstance(subscription, dict) and "error" in subscription:
            # AF20024 means the subscription is already enabled, which is fine
            if subscription["error"].get("code") == "AF20024":
                return

            # Keep the HTTP status code: a 401/403 is classified as a permission error
            raise FailedToActivateO365Subscription(
                content_type=content_type,
                status_code=response.status,
                error_code=subscription["error"].get("code"),
                error_message=subscription["error"].get("message"),
            )

        # check HTTP status code
        if response.status >= 400:
            raise FailedToActivateO365Subscription(
                content_type=content_type, status_code=response.status, body=await response.text()
            )

    @staticmethod
    async def _read_error_body(response: ClientResponse) -> str:
        """Read the body of an error response, without losing the error when the body can't be read"""
        try:
            return await response.text()
        except (ClientError, TimeoutError) as exc:
            return f"<unreadable body: {type(exc).__name__}: {exc}>"

    async def list_subscriptions(self) -> list[str]:
        """
        List the subscriptions for the tenant

        :return: The list of active subscriptions
        :rtype: list
        """
        base_url = OFFICE365_URL_BASE.format(tenant_id=self.tenant_id)

        try:
            async with self._fresh_session() as session:
                # get the list of subscriptions
                response = await session.get(f"{base_url}/subscriptions/list")

                # check HTTP status code
                if response.status >= 400:
                    raise FailedToListO365Subscriptions(
                        status_code=response.status, body=await self._read_error_body(response)
                    )

                # get the body of the response
                subscriptions = await response.json()

                # check business errors
                if "error" in subscriptions:
                    raise FailedToListO365Subscriptions(
                        error_code=subscriptions["error"].get("code"),
                        error_message=subscriptions["error"].get("message"),
                    )

                # select active subscriptions
                active_subscriptions = {
                    subscription["contentType"]
                    for subscription in subscriptions
                    if subscription["status"].lower() == OFFICE365_ACTIVE_SUBSCRIPTION_STATUS
                }

                return list(active_subscriptions)
        except (ClientError, TimeoutError, ValueError) as exc:
            # Transport errors, timeouts and invalid JSON bodies (json.JSONDecodeError is a ValueError)
            raise FailedToListO365Subscriptions(error_message=f"{type(exc).__name__}: {exc}") from exc
        except RuntimeError as exc:
            if "Session is closed" in str(exc):
                raise SessionClosedError(str(exc)) from exc
            raise

    async def get_subscription_contents(
        self,
        content_type: str,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]]]:
        """
        Return the contents from the subscription to a tenant

        :param str content_type: The content type of the subscription
        :param str or datetime start_time: Option to select contents created after the datetime
        :param str or datetime end_time: Option to select contents created before the datetime

        """
        base_url = OFFICE365_URL_BASE.format(tenant_id=self.tenant_id)

        params = {
            "contentType": content_type,
        }

        if self._publisher_id:
            params["PublisherIdentifier"] = self._publisher_id

        # add start_time parameters if defined
        if start_time is not None:
            if isinstance(start_time, datetime):
                start_time = start_time.isoformat("T")

            params["startTime"] = start_time

        # add end_time parameters if defined
        if end_time is not None:
            if isinstance(end_time, datetime):
                end_time = end_time.isoformat("T")

            params["endTime"] = end_time

        # queries contents until the NextPageUri is undefined
        query_string = urlencode(params)
        next_page_uri: str | None = f"{base_url}/subscriptions/content?{query_string}"
        while next_page_uri is not None:
            # queries the contents for the current page
            try:
                async with self._fresh_session() as session:
                    response = await session.get(
                        next_page_uri,
                    )

                    # check HTTP status code
                    if response.status >= 400:
                        raise FailedToGetO365SubscriptionContents(
                            status_code=response.status, body=await response.text()
                        )

                    contents = await response.json()

                    # check business errors
                    if "error" in contents:
                        raise FailedToGetO365SubscriptionContents(
                            error_code=contents["error"].get("code"), error_message=contents["error"].get("message")
                        )

                    # get the uri for the next page if defined
                    next_page_uri = response.headers.get("NextPageUri")
            except RuntimeError as exc:
                if "Session is closed" in str(exc):
                    raise SessionClosedError(str(exc)) from exc
                raise

            yield contents

    async def get_content(self, content_uri: str) -> list[dict[str, Any]]:
        """
        Return a content

        :param str content_uri: The uri of the content to pull
        :return: The list of events from the content
        :rtype: list
        """
        # queries the contents for the current page
        try:
            async with self._fresh_session() as session:
                response = await session.get(
                    content_uri,
                )

                # check HTTP status code
                if response.status >= 400:
                    raise FailedToGetO365AuditContent(status_code=response.status, body=await response.text())

                content = await response.json(content_type=None)

                # check business errors
                if "error" in content:
                    raise FailedToGetO365AuditContent(
                        error_code=content["error"].get("code"), error_message=content["error"].get("message")
                    )

                return content
        except RuntimeError as exc:
            if "Session is closed" in str(exc):
                raise SessionClosedError(str(exc)) from exc
            raise

    def _normalize_office365_url(self) -> str:
        """
        Normalize the url

        :return: The normalized url
        :rtype: str
        """
        uri = urlparse(OFFICE365_AUTHORITY_DEFAULT)

        if self.tenant_id is None:
            # Fallback on the tenant of the default authority (`common`)
            self.tenant_id = uri.path.strip("/") or "common"

        return urlunsplit((uri.scheme, uri.hostname, self.tenant_id, None, None))
