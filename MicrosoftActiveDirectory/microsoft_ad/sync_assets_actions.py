import json
import math
import time
from datetime import datetime
from functools import cached_property
from itertools import chain
from typing import Any

import requests
from pydantic.v1 import BaseModel, Field
from tenacity import RetryCallState, Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from .actions_base import MicrosoftADAction

DEFAULT_USER_FILTER = "(&(objectCategory=person)(objectClass=user))"
LDAP_PAGE_SIZE = 500
SEARCH_LIMIT = 100  # API maximum
MAX_ATTEMPTS = 5
MAX_RETRY_WAIT = 300.0
RETRYABLE_EXCEPTIONS = (requests.ConnectionError, requests.Timeout)


class AssetSynchronizationConfiguration(BaseModel):
    asset_name_field: str
    detection_properties: dict[str, list[str]] = {}
    contextual_properties: dict[str, str] = {}


class SynchronizeAssetsArguments(BaseModel):
    basedn: str
    search_filter: str = DEFAULT_USER_FILTER
    asset_synchronization_configuration: AssetSynchronizationConfiguration
    community_uuid: str
    sekoia_api_key: str
    sekoia_base_url: str = "https://api.sekoia.io"
    delay_between_requests: float = Field(0.2, ge=0)


class SkipUser(Exception):
    pass


class RetryableResponseError(Exception):
    def __init__(self, response: requests.Response):
        self.response = response
        super().__init__(f"HTTP {response.status_code} on {response.request.method} {response.url}: {response.text}")


def _values(value: Any) -> list[Any]:
    """LDAP attributes are scalars or lists; absent ones are empty lists."""
    return [v for v in (value if isinstance(value, list) else [value]) if v not in (None, "")]


def _json_default(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    return str(value)


def _wait(retry_state: RetryCallState) -> float:
    exception = retry_state.outcome.exception() if retry_state.outcome else None
    retry_after = (
        exception.response.headers.get("Retry-After") if isinstance(exception, RetryableResponseError) else None
    )
    try:
        seconds = float(retry_after) if retry_after is not None else math.nan
    except ValueError:
        seconds = (
            math.nan
        )  # ponytail: HTTP-date Retry-After falls back to backoff, SDK>=1.24 parse_retry_after handles it
    if math.isfinite(seconds):
        return min(max(seconds, 0.0), MAX_RETRY_WAIT)
    return wait_exponential(multiplier=1, max=60)(retry_state)


class SynchronizeAssetsAction(MicrosoftADAction):
    """
    Read users from Active Directory and create, merge or update the matching accounts assets in Sekoia.io.
    Meant to run on an on-premise runner: AD is never exposed to Sekoia.io.
    """

    name = "Synchronize AD assets"
    description = "Synchronize Active Directory users with Sekoia.io assets"

    sync_arguments: SynchronizeAssetsArguments

    @cached_property
    def session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update(
            {"Authorization": f"Bearer {self.sync_arguments.sekoia_api_key}", "Content-Type": "application/json"}
        )
        return session

    def _request(self, method: str, path: str, params: dict | None = None, body: dict | None = None) -> Any:
        url = f"{self.sync_arguments.sekoia_base_url.rstrip('/')}/api/v2/asset-management/assets{path}"
        data = json.dumps(body, default=_json_default) if body is not None else None

        for attempt in Retrying(
            stop=stop_after_attempt(MAX_ATTEMPTS),
            wait=_wait,
            retry=retry_if_exception_type((RetryableResponseError, *RETRYABLE_EXCEPTIONS)),
            reraise=True,
        ):
            with attempt:
                time.sleep(self.sync_arguments.delay_between_requests)
                response = self.session.request(method, url, params=params, data=data, timeout=30)
                if response.status_code == 429 or response.status_code >= 500:
                    self.log(f"HTTP {response.status_code} on {method} {url}, retrying", level="warning")
                    raise RetryableResponseError(response)

        if not response.ok:
            raise Exception(f"HTTP {response.status_code} on {method} {url}: {response.text}")
        return response.json() if response.content else None

    def _search(self, search: str, in_detection_properties: bool = False) -> list[dict]:
        params: dict[str, Any] = {
            "search": search,
            "community_uuids": self.sync_arguments.community_uuid,
            "limit": SEARCH_LIMIT,
        }
        if in_detection_properties:
            params["also_search_in_detection_properties"] = "true"
        return (self._request("GET", "", params=params) or {}).get("items", [])

    def _synchronize_user(self, attributes: Any, counters: dict[str, int]) -> None:
        conf = self.sync_arguments.asset_synchronization_configuration

        names = _values(attributes.get(conf.asset_name_field))
        if not names:
            raise SkipUser(f"missing attribute {conf.asset_name_field}")
        name = str(names[0])

        atoms: dict[str, list[Any]] = {}
        found_assets: set[str] = set()
        for prop, keys in conf.detection_properties.items():
            values = [value for key in keys for value in _values(attributes.get(key))]
            if values:
                atoms[prop] = values
            for value in values:
                found_assets.update(asset["uuid"] for asset in self._search(str(value), in_detection_properties=True))

        props = {
            prop: attributes.get(key)
            for prop, key in conf.contextual_properties.items()
            if _values(attributes.get(key))
        }

        payload: dict[str, Any] = {
            "name": name,
            "description": "",
            "type": "account",
            "category": "user",
            "reviewed": True,
            "source": "manual",
            "props": props,
            "atoms": atoms,
        }

        same_name = [asset for asset in self._search(name) if str(asset.get("name", "")).lower() == name.lower()]
        if len(same_name) > 1:
            raise SkipUser(f"{len(same_name)} assets named {name}")

        if same_name:
            destination = same_name[0]["uuid"]
        else:
            destination = self._request(
                "POST", "", body={**payload, "community_uuid": self.sync_arguments.community_uuid}
            )["uuid"]
            counters["created"] += 1

        sources = sorted(found_assets - {destination})
        if sources:
            self._request("POST", "/merge", body={"destination": destination, "sources": sources})
            counters["merged"] += len(sources)

        if same_name:
            self._request("PUT", f"/{destination}", body=payload)
            counters["updated"] += 1

    def run(self, arguments: SynchronizeAssetsArguments) -> dict:
        self.sync_arguments = arguments
        conf = arguments.asset_synchronization_configuration
        attributes = sorted(
            {
                conf.asset_name_field,
                *chain.from_iterable(conf.detection_properties.values()),
                *conf.contextual_properties.values(),
            }
        )

        counters = {"total": 0, "created": 0, "updated": 0, "merged": 0, "skipped": 0}
        entries = self.client.extend.standard.paged_search(
            search_base=arguments.basedn,
            search_filter=arguments.search_filter,
            attributes=attributes,
            paged_size=LDAP_PAGE_SIZE,
            generator=True,
        )

        for entry in entries:
            if entry.get("type") != "searchResEntry":
                continue

            counters["total"] += 1
            try:
                self._synchronize_user(entry.get("attributes", {}), counters)
            except SkipUser as error:
                counters["skipped"] += 1
                self.log(f"Skipping {entry.get('dn')}: {error}", level="warning")

        self.log(f"Synchronization finished: {counters}", level="info")

        return counters
