from collections.abc import Generator
from typing import Any

import requests
from loguru import logger
from requests.exceptions import RequestException

from nozomi_networks.asset_connector.models import NozomiAsset, NozomiAssetPage


class NozomiQueryError(Exception):
    """Raised when the Guardian/CMC query API returns an error."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


class NozomiQueryClient:
    """
    Synchronous client for the Nozomi Guardian/CMC Open API query endpoint.

    Authentication uses the Guardian/CMC Open API key sign-in flow: the API key
    (``key_name`` / ``key_token``) is exchanged at ``/api/open/sign_in`` for a
    bearer ``access_token`` which is then attached as an ``Authorization`` header
    to every query request.
    """

    SIGN_IN_ENDPOINT: str = "/api/open/sign_in"
    QUERY_ENDPOINT: str = "/api/open/query/do"

    def __init__(
        self,
        key_name: str,
        key_token: str,
        base_url: str,
        page_size: int = 1000,
        default_headers: dict[str, str] | None = None,
        timeout: int = 60,
    ) -> None:
        self.key_name = key_name
        self.key_token = key_token
        self.base_url = base_url.rstrip("/")
        self.page_size = page_size
        self.timeout = timeout
        self._authorization: str | None = None
        self._session = requests.Session()
        if default_headers:
            self._session.headers.update(default_headers)

    def refresh_authorization(self) -> None:
        """
        Sign in to the Guardian/CMC Open API and store the bearer token.

        The endpoint returns a JSON body of the form::

            {"access_token": "<jwt>", "token_type": "Bearer", "expires_in": 1800}

        which is turned into an ``Authorization: Bearer <jwt>`` header.
        """
        response = self._session.post(
            f"{self.base_url}{self.SIGN_IN_ENDPOINT}",
            json={"key_name": self.key_name, "key_token": self.key_token},
            timeout=self.timeout,
        )

        if response.status_code != 200:
            raise NozomiQueryError(response.status_code, f"Sign-in failed: {response.text}")

        payload = response.json()
        access_token = payload.get("access_token")
        if not access_token:
            raise NozomiQueryError(response.status_code, "access_token not found in sign-in response.")

        token_type = payload.get("token_type") or "Bearer"
        self._authorization = f"{token_type} {access_token}"

    @staticmethod
    def build_assets_query(
        from_timestamp_ms: int | None,
        head: int,
        inclusive: bool = False,
    ) -> str:
        """
        Build the N2QL query string for assets, filtered and ordered by ``created_at``.

        Args:
            from_timestamp_ms: Lower bound on ``created_at`` in epoch ms.
            head: Maximum number of records to return (page size).
            inclusive: Use ``>=`` instead of ``>`` for the lower bound.
        """
        query = "assets"
        if from_timestamp_ms is not None:
            operator = ">=" if inclusive else ">"
            query += f" | where created_at {operator} {from_timestamp_ms}"
        query += f" | sort created_at asc | head {head}"
        return query

    @staticmethod
    def build_same_timestamp_query(timestamp_ms: int, skip: int, head: int) -> str:
        """
        Build the N2QL query string for all assets sharing one ``created_at`` value.

        Sorting on the unique ``id`` makes the offset pagination deterministic.
        """
        query = f"assets | where created_at == {timestamp_ms} | sort id asc"
        if skip:
            query += f" | skip {skip}"
        query += f" | head {head}"
        return query

    def _do_query(self, query: str) -> dict[str, Any]:
        if self._authorization is None:
            self.refresh_authorization()

        def _request() -> requests.Response:
            headers = {"Authorization": self._authorization} if self._authorization else {}
            return self._session.get(
                f"{self.base_url}{self.QUERY_ENDPOINT}",
                headers=headers,
                params={"query": query},
                timeout=self.timeout,
            )

        response = _request()

        # Refresh the token once on authentication failure and retry.
        if response.status_code == 401:
            self.refresh_authorization()
            response = _request()

        if response.status_code != 200:
            raise NozomiQueryError(response.status_code, f"Query failed: {response.text}")

        data: dict[str, Any] = response.json()
        return data

    def _query_assets(self, query: str) -> list[NozomiAsset]:
        logger.info("Querying Nozomi assets: {query}", query=query)
        try:
            raw = self._do_query(query)
        except RequestException as error:
            raise NozomiQueryError(0, f"Query request error: {error}") from error
        return NozomiAssetPage.parse_obj(raw).result

    def _fetch_same_timestamp(self, timestamp_ms: int) -> list[NozomiAsset]:
        assets: list[NozomiAsset] = []
        skip = 0
        while True:
            page = self._query_assets(self.build_same_timestamp_query(timestamp_ms, skip, self.page_size))
            assets.extend(page)
            if len(page) < self.page_size:
                return assets
            skip += self.page_size

    @staticmethod
    def _created_at_ms(asset: NozomiAsset) -> int | None:
        try:
            return int(asset.created_at) if asset.created_at else None
        except ValueError:
            return None

    def fetch_assets(
        self,
        from_timestamp_ms: int | None,
        exclude_ids: set[str] | None = None,
    ) -> Generator[list[NozomiAsset], None, None]:
        """
        Fetch assets page by page, yielding parsed assets for each page.

        ``created_at`` is not unique, so a page may end in the middle of a group of
        assets sharing the same timestamp. When a page is full, the whole group for
        its last timestamp is fetched (sorted by ``id``) before moving on with a
        strict ``created_at >`` cursor, so no asset is skipped or duplicated.

        Args:
            from_timestamp_ms: Only assets created at or after this epoch-ms value
                are returned. ``None`` fetches all assets.
            exclude_ids: IDs of assets created exactly at ``from_timestamp_ms`` that
                were already collected and must not be returned again.
        """
        exclude_ids = exclude_ids or set()
        cursor = from_timestamp_ms
        inclusive = from_timestamp_ms is not None

        while True:
            page = self._query_assets(self.build_assets_query(cursor, self.page_size, inclusive))
            if not page:
                return

            is_last_page = len(page) < self.page_size
            timestamps = [ts for ts in (self._created_at_ms(asset) for asset in page) if ts is not None]
            last_timestamp = max(timestamps) if timestamps else None

            if not is_last_page and last_timestamp is None:
                logger.warning("Full page of Nozomi assets without a valid created_at, stopping pagination")

            if not is_last_page and last_timestamp is not None:
                page = [asset for asset in page if self._created_at_ms(asset) != last_timestamp]
                page.extend(self._fetch_same_timestamp(last_timestamp))

            if from_timestamp_ms is not None and exclude_ids:
                page = [
                    asset
                    for asset in page
                    if not (self._created_at_ms(asset) == from_timestamp_ms and asset.id in exclude_ids)
                ]

            if page:
                yield page

            if is_last_page or last_timestamp is None:
                return

            cursor = last_timestamp
            inclusive = False

    def close(self) -> None:  # pragma: no cover
        self._session.close()
