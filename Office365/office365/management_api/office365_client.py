import asyncio
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from urllib.parse import urlencode, urlparse, urlunsplit

import msal
from aiohttp.client import ClientSession

from .constants import OFFICE365_ACTIVE_SUBSCRIPTION_STATUS, OFFICE365_AUTHORITY_DEFAULT, OFFICE365_URL_BASE
from .errors import (
    ApplicationAuthenticationFailed,
    FailedToActivateO365Subscription,
    FailedToGetO365AuditContent,
    FailedToGetO365SubscriptionContents,
    FailedToListO365Subscriptions,
)
from .logging import get_logger

logger = get_logger()


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
        self._token_expiration = 0
        self._publisher_id = publisher_id

    async def close(self):
        """
        Close the client
        """
        await self._session.close()

    async def _authenticate_client(self):
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
    async def _fresh_session(self) -> AsyncGenerator[ClientSession, None]:
        """
        Return a fresh authenticated session

        Check the expiration time of the current token and renew it if expired
        """
        if time.time() > self._token_expiration - 10:
            await self._authenticate_client()

        yield self._session

    async def activate_subscriptions(self) -> None:
        """
        Activate subscriptions for a tenant

        :param set[str] content_types: The content types of the subscriptions
        :return: A dict matching content types to the result of their subscription attempt
        :rtype: dict[str, bool]
        """
        EXPECTED_SUBSCRIPTIONS = {"Audit.AzureActiveDirectory", "Audit.SharePoint", "Audit.General", "Audit.Exchange"}

        already_enabled_types = set(await self.list_subscriptions())
        missing_types = EXPECTED_SUBSCRIPTIONS - already_enabled_types

        # Activate missing types
        async with self._fresh_session() as session:
            for content_type in missing_types:
                # activate the subscription
                base_url = OFFICE365_URL_BASE.format(tenant_id=self.tenant_id)
                response = await session.post(f"{base_url}/subscriptions/start", params={"contentType": content_type})

                # check HTTP status code
                if response.status >= 400:
                    raise FailedToActivateO365Subscription(status_code=response.status, body=await response.text())

                subscription = await response.json()

                if "error" in subscription:
                    raise FailedToActivateO365Subscription(
                        error_code=subscription["error"].get("code"),
                        error_message=subscription["error"].get("message"),
                    )

    async def list_subscriptions(self) -> list[str]:
        """
        List the subscriptions for the tenant

        :return: The list of active subscriptions
        :rtype: list
        """
        base_url = OFFICE365_URL_BASE.format(tenant_id=self.tenant_id)

        async with self._fresh_session() as session:
            # get the list of subscriptions
            response = await session.get(f"{base_url}/subscriptions/list")

            # check HTTP status code
            if response.status >= 400:
                raise FailedToListO365Subscriptions(status_code=response.status, body=await response.text())

            # get the body of the response
            subscriptions = await response.json()

            # check business errors
            if "error" in subscriptions:
                raise FailedToListO365Subscriptions(
                    error_code=subscriptions["error"].get("code"), error_message=subscriptions["error"].get("message")
                )

            # select active subscriptions
            active_subscriptions = {
                subscription["contentType"]
                for subscription in subscriptions
                if subscription["status"].lower() == OFFICE365_ACTIVE_SUBSCRIPTION_STATUS
            }

            return list(active_subscriptions)

    async def get_subscription_contents(
        self,
        content_type: str,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
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
            async with self._fresh_session() as session:
                response = await session.get(
                    next_page_uri,
                )

                # check HTTP status code
                if response.status >= 400:
                    raise FailedToGetO365SubscriptionContents(status_code=response.status, body=await response.text())

                contents = await response.json()

                # check business errors
                if "error" in contents:
                    raise FailedToGetO365SubscriptionContents(
                        error_code=contents["error"].get("code"), error_message=contents["error"].get("message")
                    )

                yield contents

                # get the uri for the next page if defined
                next_page_uri = response.headers.get("NextPageUri")

    async def get_content(self, content_uri: str) -> list[dict[str, Any]]:
        """
        Return a content

        :param str content_uri: The uri of the content to pull
        :return: The list of events from the content
        :rtype: list
        """
        # queries the contents for the current page
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

    def _normalize_office365_url(self) -> str:
        """
        Normalize the url

        :return: The normalized url
        :rtype: str
        """
        uri = urlparse(OFFICE365_AUTHORITY_DEFAULT)

        if self.tenant_id is None:
            parts = uri.path.split("/")
            if len(parts) > 0:
                self.tenant_id = parts[1]
            else:
                self.tenant_id = "common"

        return urlunsplit((uri.scheme, uri.hostname, self.tenant_id, None, None))
