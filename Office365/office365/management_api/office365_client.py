import time
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from typing import Any
from urllib.parse import urlparse, urlunsplit

# Third parties
import msal
import requests

from .constants import (
    OFFICE365_ACTIVE_SUBSCRIPTION_STATUS,
    OFFICE365_AUTHORITY_DEFAULT,
    OFFICE365_URL_BASE,
)
from .errors import (
    ApplicationAuthenticationFailed,
    FailedToActivateO365Subscription,
    FailedToGetO365AuditContent,
    FailedToGetO365SubscriptionContents,
    FailedToListO365Subscriptions,
)


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
        self._session = requests.session()
        self._token_expiration = 0
        self._publisher_id = publisher_id

    def _authenticate_client(self):
        """
        Authenticate the application
        """
        scopes = ["https://manage.office.com/.default"]
        response = self._app.acquire_token_for_client(scopes=scopes)

        if "access_token" not in response:
            raise ApplicationAuthenticationFailed("Failed to get access token", response=response)

        if response.get("token_type", "").lower() != "bearer":
            raise ApplicationAuthenticationFailed("Bearer Authentication not supported", response=response)

        self._token_expiration = time.time() + int(response["expires_in"])
        self._session.headers["Authorization"] = "{} {}".format(response["token_type"], response["access_token"])

    @contextmanager
    def _fresh_session(self):
        """
        Return a fresh authenticated session

        Check the expiration time of the current token and renew it if expired
        """
        if time.time() > self._token_expiration - 10:
            self._authenticate_client()

        yield self._session

    def activate_subscriptions(self, content_types: set[str]) -> dict[str, bool]:
        """
        Activate subscriptions for a tenant

        :param set[str] content_types: The content types of the subscriptions
        :return: A dict matching content types to the result of their subscription attempt
        :rtype: dict[str, bool]
        """
        base_url = OFFICE365_URL_BASE.format(tenant_id=self.tenant_id)
        already_enabled_types = set(self.list_subscriptions())
        missing_types = content_types - already_enabled_types
        enabled_types = []
        subscriptions_status = {}

        # Activate missing types
        for content_type in missing_types:
            with self._fresh_session() as session:
                # activate the subscription
                response = session.post(f"{base_url}/subscriptions/start", params={"contentType": content_type})

                # check HTTP status code
                if response.status_code >= 400:
                    raise FailedToActivateO365Subscription(status_code=response.status_code, body=response.text)

                subscription = response.json()

                if "error" in subscription:
                    raise FailedToActivateO365Subscription(
                        error_code=subscription["error"].get("code"),
                        error_message=subscription["error"].get("message"),
                    )
            enabled_types.append(content_type)
            subscriptions_status[content_type] = subscription["status"] == OFFICE365_ACTIVE_SUBSCRIPTION_STATUS

        return subscriptions_status

    def list_subscriptions(self) -> list[str]:
        """
        List the subscriptions for the tenant

        :return: The list of active subscriptions
        :rtype: list
        """
        base_url = OFFICE365_URL_BASE.format(tenant_id=self.tenant_id)

        with self._fresh_session() as session:
            # get the list of subscriptions
            response = session.get(f"{base_url}/subscriptions/list")

            # check HTTP status code
            if response.status_code >= 400:
                raise FailedToListO365Subscriptions(status_code=response.status_code, body=response.text)

            # get the body of the response
            subscriptions = response.json()

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

    def get_subscription_contents(
        self,
        content_type: str,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
    ) -> Generator[list[dict[str, Any]], None, None]:
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
        next_page_uri = f"{base_url}/subscriptions/content"
        while next_page_uri is not None:
            # queries the contents for the current page
            with self._fresh_session() as session:
                response = session.get(
                    next_page_uri,
                    params=params,
                )

                # check HTTP status code
                if response.status_code >= 400:
                    raise FailedToGetO365SubscriptionContents(status_code=response.status_code, body=response.text)

                contents = response.json()

                # check business errors
                if "error" in contents:
                    raise FailedToGetO365SubscriptionContents(
                        error_code=contents["error"].get("code"), error_message=contents["error"].get("message")
                    )

                yield contents

                # get the uri for the next page if defined
                next_page_uri = response.headers.get("NextPageUri")

    def get_content(self, content_uri: str) -> list[dict[str, Any]]:
        """
        Return a content

        :param str content_uri: The uri of the content to pull
        :return: The list of events from the content
        :rtype: list
        """
        # queries the contents for the current page
        with self._fresh_session() as session:
            response = session.get(
                content_uri,
            )

            # check HTTP status code
            if response.status_code >= 400:
                raise FailedToGetO365AuditContent(status_code=response.status_code, body=response.text)

            content = response.json()

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
