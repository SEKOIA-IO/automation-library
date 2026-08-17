import os
import threading
from collections.abc import Generator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import orjson
import requests
from sekoia_automation.checkpoint import CheckpointDatetime
from sekoia_automation.connector import Connector
from sekoia_automation.storage import PersistentJSON

from upwind import (
    UpwindConnectorConfig,
    UpwindModule,
    extract_upwind_detection_datetime,
)


@dataclass
class OAuthTokenProvider:
    access_token: str | None = None
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        self._lock = threading.Lock()

    def get_access_token(
        self,
        *,
        session: requests.Session,
        auth_url: str,
        client_id: str,
        client_secret: str,
        audience: str,
        timeout: int,
    ) -> str:
        with self._lock:
            now = datetime.now(UTC)
            if self.access_token and self.expires_at and now + timedelta(seconds=300) < self.expires_at:
                return self.access_token

            data = {
                "client_id": client_id,
                "client_secret": client_secret,
                "audience": audience,
                "grant_type": "client_credentials",
            }

            response = session.post(url=auth_url, data=data, timeout=timeout)
            response.raise_for_status()
            token_payload = response.json()

            if not isinstance(token_payload, dict):
                raise ValueError("OAuth token response must be a JSON object")

            access_token = token_payload.get("access_token")
            token_type = str(token_payload.get("token_type", "Bearer")).title()
            expires_in = token_payload.get("expires_in")

            if not access_token:
                raise ValueError("OAuth token response did not include access_token")
            if not isinstance(expires_in, int | float) or expires_in <= 0:
                raise ValueError("OAuth token response did not include a valid expires_in")

            self.access_token = f"{token_type} {access_token}"
            self.expires_at = now + timedelta(seconds=int(expires_in))
            return self.access_token


class UpwindDetectionsConnector(Connector):
    name = "UpwindDetectionsConnector"
    configuration: UpwindConnectorConfig
    module: UpwindModule

    def __init__(self, *args: Any, **kwargs: Any | None) -> None:
        super().__init__(*args, **kwargs)
        self.last_detection_date = CheckpointDatetime(
            path=self.data_path,
            start_at=timedelta(days=7),
            ignore_older_than=timedelta(days=30),
        )
        self._context = PersistentJSON("context.json", self.data_path)
        self.request_timeout = int(os.environ.get("UPWIND_CLIENT_TIMEOUT", "60"))
        self._oauth_provider = OAuthTokenProvider()

    @property
    def frequency(self) -> int:
        return self.configuration.frequency

    @staticmethod
    def _derive_oauth_audience(base_url: str) -> str:
        parsed = urlsplit(base_url)
        if not parsed.scheme or not parsed.netloc:
            return base_url.rstrip("/")

        return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))

    @staticmethod
    def _to_rfc3339(value: datetime) -> str:
        # Upwind rejects fractional seconds, so serialize with whole-second precision.
        return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def fetch_detections(self, *, since: datetime) -> list[dict[str, Any]]:
        base_url = str(self.module.configuration.base_url).rstrip("/")
        auth_url = str(self.module.configuration.auth_url)
        audience = self._derive_oauth_audience(base_url)

        authorization = self._oauth_provider.get_access_token(
            session=self._http_session,
            auth_url=auth_url,
            client_id=self.module.configuration.client_id,
            client_secret=self.module.configuration.client_secret,
            audience=audience,
            timeout=self.request_timeout,
        )

        headers = {
            "Authorization": authorization,
            "Accept": "application/json",
        }
        org_id = self.module.configuration.organization_id
        url = f"{base_url}/v1/organizations/{org_id}/threat-detections"
        params = {"min-last-seen-time": self._to_rfc3339(since)}

        response = self._http_session.get(
            url=url,
            params=params,
            headers=headers,
            timeout=self.request_timeout,
        )
        response.raise_for_status()
        payload = response.json()

        if not isinstance(payload, list):
            raise ValueError("Upwind detections response must be a JSON array")

        detections: list[dict[str, Any]] = []
        for event in payload:
            if not isinstance(event, dict):
                raise ValueError("Upwind detections response must contain objects")
            detections.append(event)

        return detections

    def _load_boundary_ids(self) -> set[str]:
        with self._context as cache:
            stored = cache.get("boundary_detection_ids", [])
        return set(stored) if isinstance(stored, list) else set()

    def _save_boundary_ids(self, boundary_ids: set[str]) -> None:
        with self._context as cache:
            cache["boundary_detection_ids"] = sorted(boundary_ids)

    def _select_new_detections(
        self, detections: list[dict[str, Any]], since: datetime, seen_ids: set[str]
    ) -> tuple[list[str], datetime, set[str]]:
        outgoing: list[str] = []
        most_recent = since
        # IDs already forwarded at the ``most_recent`` timestamp, used to dedup the
        # inclusive ``min-last-seen-time`` boundary returned on every request.
        boundary_ids = set(seen_ids)
        for detection in detections:
            last_seen = extract_upwind_detection_datetime(detection)
            if last_seen is None:
                continue

            detection_id = detection.get("id")
            if last_seen < since:
                continue
            if last_seen == since and detection_id in seen_ids:
                continue

            outgoing.append(orjson.dumps(detection).decode("utf-8"))

            if last_seen > most_recent:
                most_recent = last_seen
                boundary_ids = set()
            if last_seen == most_recent and detection_id is not None:
                boundary_ids.add(str(detection_id))

        return outgoing, most_recent, boundary_ids

    def iterate(self) -> Generator[tuple[list[str], datetime | None], None]:
        since = self.last_detection_date.offset
        seen_ids = self._load_boundary_ids()
        detections = self.fetch_detections(since=since)

        outgoing, most_recent, boundary_ids = self._select_new_detections(detections, since, seen_ids)
        if not outgoing:
            return

        # Yield before advancing the checkpoint so events are pushed first.
        yield outgoing, most_recent

        self.last_detection_date.offset = most_recent
        self._save_boundary_ids(boundary_ids)
