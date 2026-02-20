from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp
from aiolimiter import AsyncLimiter
from sekoia_automation.trigger import Trigger

from anozrway_modules.client.errors import AnozrwayAuthError, AnozrwayError, AnozrwayRateLimitError
from anozrway_modules.client.token_refresher import AnozrwayTokenRefresher


class AnozrwayClient:
    def __init__(
        self,
        base_url: str,
        token_url: str,
        client_id: str,
        client_secret: str,
        x_restrict_access: Optional[str] = None,
        timeout_seconds: int = 30,
        trigger: Optional[Trigger] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.x_restrict_access = x_restrict_access
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.trigger = trigger

        self._session: Optional[aiohttp.ClientSession] = None
        self._rate_limiter = AsyncLimiter(max_rate=1, time_period=1)
        self._token_refresher = AnozrwayTokenRefresher(
            client_id=client_id,
            client_secret=client_secret,
            token_url=token_url,
            timeout=timeout_seconds,
        )

    def log(self, message: str, level: str = "info") -> None:
        if self.trigger:
            self.trigger.log(message=message, level=level)

    async def _get_access_token(self) -> str:
        async with self._token_refresher.with_access_token() as refreshed:
            return refreshed.token.access_token

    @staticmethod
    def _to_iso(dt: datetime) -> str:
        return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    async def _post_with_retry(
        self,
        path: str,
        payload: Dict[str, Any],
        *,
        result_key: str,
        unauthorized_msg: str,
        generic_error_msg: str,
    ) -> List[Dict[str, Any]]:
        if not self._session:
            raise AnozrwayError("HTTP session not initialized")

        access_token = await self._get_access_token()

        url = f"{self.base_url}{path}"
        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {access_token}",
        }

        if self.x_restrict_access:
            headers["x-restrict-access"] = str(self.x_restrict_access)

        max_attempts = 3
        attempt = 0
        backoff = 1

        while attempt < max_attempts:
            attempt += 1

            async with self._rate_limiter:
                async with self._session.post(
                    url, json=payload, headers=headers, timeout=self.timeout, raise_for_status=False
                ) as resp:
                    status = resp.status

                    if status == 401:
                        self._token_refresher._token = None  # force token refresh on retry
                        if attempt < max_attempts:
                            continue
                        raise AnozrwayAuthError(unauthorized_msg)

                    if status == 429:
                        await asyncio.sleep(60 * backoff)
                        backoff *= 2
                        continue

                    if status != 200:
                        text = await resp.text()
                        raise AnozrwayError(f"{generic_error_msg} ({status}): {text}")

                    data = await resp.json()

            results = data.get(result_key) or []
            if not isinstance(results, list):
                return []
            return results

        raise AnozrwayRateLimitError(f"Exceeded maximum retry attempts while calling {generic_error_msg}")

    async def search_domain_v1(
        self,
        context: str,
        domain: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List[Dict[str, Any]]:
        payload = {
            "context": context,
            "domain": domain,
            "start_date": self._to_iso(start_date),
            "end_date": self._to_iso(end_date),
        }
        return await self._post_with_retry(
            "/v1/domain/searches",
            payload,
            result_key="results",
            unauthorized_msg="Unauthorized when calling Anozrway v1 domain search",
            generic_error_msg="v1 domain search failed",
        )

    async def fetch_events(
        self,
        context: str,
        domain: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List[Dict[str, Any]]:
        """Fetch leak detection events from the Balise Pipeline /events endpoint."""
        payload = {
            "context": context,
            "domain": domain,
            "start_date": self._to_iso(start_date),
            "end_date": self._to_iso(end_date),
        }
        return await self._post_with_retry(
            "/events",
            payload,
            result_key="events",
            unauthorized_msg="Unauthorized when calling Balise Pipeline /events",
            generic_error_msg="Balise Pipeline /events failed",
        )

    async def __aenter__(self) -> "AnozrwayClient":
        self._session = aiohttp.ClientSession(trust_env=True)
        try:
            await self._get_access_token()
        except Exception:
            await self._session.close()
            self._session = None
            raise
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self._session:
            await self._session.close()
            self._session = None
        await self._token_refresher.close()
