from __future__ import annotations

import asyncio
import aiohttp
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from aiolimiter import AsyncLimiter

from sekoia_automation.trigger import Trigger

from anozrway_modules.client.errors import AnozrwayAuthError, AnozrwayError, AnozrwayRateLimitError


class AnozrwayClient:
    def __init__(self, module_config: Dict[str, Any], trigger: Optional[Trigger] = None):
        self.cfg = module_config
        self.trigger = trigger

        self.base_url = str(self.cfg.get("anozrway_base_url", "https://balise.anozrway.com")).rstrip("/")
        self.token_url = str(self.cfg.get("anozrway_token_url", "https://auth.anozrway.com/oauth2/token"))
        self.client_id = self.cfg.get("anozrway_client_id")
        self.client_secret = self.cfg.get("anozrway_client_secret")
        self.x_restrict_access = self.cfg.get("anozrway_x_restrict_access_token")  # may be None for now
        self.timeout = int(self.cfg.get("timeout_seconds", 30))

        self._session: Optional[aiohttp.ClientSession] = None
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

        # spec recommends 1 req/sec
        self._rate_limiter = AsyncLimiter(max_rate=1, time_period=1)

    def log(self, message: str, level: str = "info") -> None:
        if self.trigger:
            self.trigger.log(message=message, level=level)

    async def _get_access_token(self) -> str:
        if not self._session:
            raise AnozrwayError("HTTP session not initialized")

        if self._access_token and self._token_expires_at:
            now = datetime.now(timezone.utc)
            if now < self._token_expires_at:
                return self._access_token

        if not self.client_id or not self.client_secret:
            raise AnozrwayAuthError("Missing anozrway_client_id / anozrway_client_secret in module configuration")

        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        async with self._rate_limiter:
            async with self._session.post(
                self.token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=self.timeout,
                raise_for_status=False,
            ) as resp:
                status = resp.status
                text = await resp.text()

                if status == 401:
                    raise AnozrwayAuthError(f"Token exchange unauthorized: {text}")

                if status != 200:
                    raise AnozrwayError(f"Token request failed ({status}): {text}")

                token_data = await resp.json()

        token = token_data.get("access_token")
        if not token:
            raise AnozrwayError(f"OAuth2 response missing access_token: {token_data}")

        expires_in = int(token_data.get("expires_in", 3600))
        self._access_token = token
        # refresh 5 min before
        self._token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(60, expires_in - 300))
        return token

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
                        self._access_token = None
                        self._token_expires_at = None
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

    async def __aenter__(self):
        self._session = aiohttp.ClientSession(trust_env=True)
        try:
            # validate token once
            await self._get_access_token()
        except Exception:
            await self._session.close()
            self._session = None
            raise
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._session:
            await self._session.close()
            self._session = None
