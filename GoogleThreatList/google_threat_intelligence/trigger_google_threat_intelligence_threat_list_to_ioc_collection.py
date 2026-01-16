"""
GoogleThreatIntelligenceThreatListToIOCCollectionTrigger - GTI Threat List Connector

Retrieves IoCs from Google Threat Intelligence via VirusTotal API
and forwards them to a SEKOIA.IO IOC Collection.

Based on GOOGLE_THREAT_LIST_SOW_SPEC.md specification.
"""

import hashlib
import time
from traceback import format_exc
from typing import Any
from urllib.parse import urlencode

import requests
from cachetools import TTLCache
from sekoia_automation.trigger import Trigger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# Valid threat list IDs per specification
VALID_THREAT_LIST_IDS = [
    "ransomware",
    "malicious-network-infrastructure",
    "malware",
    "threat-actor",
    "trending",
    "mobile",
    "osx",
    "linux",
    "iot",
    "cryptominer",
    "phishing",
    "first-stage-delivery-vectors",
    "vulnerability-weaponization",
    "infostealer",
]

# Valid IOC types per specification
VALID_IOC_TYPES = ["file", "url", "ip_address", "domain"]

# Valid has: filter values per specification
VALID_HAS_VALUES = ["malware_families", "campaigns", "reports", "threat_actors"]


class VirusTotalAPIError(Exception):
    """Base exception for VirusTotal API errors."""

    pass


class QuotaExceededError(VirusTotalAPIError):
    """API rate limit exceeded."""

    retryable = True


class InvalidAPIKeyError(VirusTotalAPIError):
    """Invalid or expired API key."""

    retryable = False


class ThreatListNotFoundError(VirusTotalAPIError):
    """Requested threat list does not exist."""

    retryable = False


class QueryValidationError(Exception):
    """Invalid query syntax."""

    pass


class GoogleThreatIntelligenceThreatListToIOCCollectionTrigger(Trigger):
    """
    Trigger to retrieve IoCs from Google Threat Intelligence via VirusTotal API
    and forward them to a SEKOIA.IO IOC Collection.
    """

    BASE_URL = "https://www.virustotal.com/api/v3"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = None
        self.processed_events = TTLCache(maxsize=10000, ttl=604800)  # 7 days TTL

    @property
    def sleep_time(self) -> int:
        """Get sleep time between polls in seconds."""
        return int(self.configuration.get("sleep_time", 300))

    @property
    def api_key(self) -> str:
        """Get VirusTotal API key from module configuration."""
        return self.module.configuration.get("virustotal_api_key", "")

    @property
    def threat_list_id(self) -> str:
        """Get the threat list ID to monitor."""
        return self.configuration.get("threat_list_id", "malware")

    @property
    def ioc_types(self) -> list[str]:
        """Get IOC types to retrieve."""
        types = self.configuration.get("ioc_types", VALID_IOC_TYPES)
        if isinstance(types, str):
            types = [t.strip() for t in types.split(",")]
        return [t for t in types if t in VALID_IOC_TYPES]

    @property
    def max_iocs(self) -> int:
        """Get maximum number of IoCs per request."""
        return min(int(self.configuration.get("max_iocs", 4000)), 4000)

    @property
    def extra_query_params(self) -> str:
        """Get extra query parameters for advanced filtering."""
        return self.configuration.get("extra_query_params", "")

    @property
    def ioc_collection_server(self) -> str:
        """Get IOC collection server URL."""
        return self.configuration.get("ioc_collection_server", "https://api.sekoia.io")

    @property
    def ioc_collection_uuid(self) -> str:
        """Get IOC collection UUID."""
        return self.configuration.get("ioc_collection_uuid", "")

    @property
    def sekoia_api_key(self) -> str:
        """Get Sekoia API key."""
        return self.module.configuration.get("sekoia_api_key", "")

    def initialize_client(self) -> None:
        """Initialize HTTP session with authentication headers."""
        if not self.api_key:
            raise InvalidAPIKeyError("VirusTotal API key is required")

        if len(self.api_key) < 64:
            raise InvalidAPIKeyError("Invalid VirusTotal API key format")

        self.session = requests.Session()
        self.session.headers.update(
            {"X-Apikey": self.api_key, "Accept": "application/json"}
        )
        self.session.verify = True

        self.log(message="VirusTotal client initialized", level="info")

    def validate_threat_list_id(self, threat_list_id: str) -> bool:
        """Validate threat list ID against allowed values."""
        if threat_list_id not in VALID_THREAT_LIST_IDS:
            raise ThreatListNotFoundError(
                f"Invalid threat_list_id: {threat_list_id}. "
                f"Must be one of: {', '.join(VALID_THREAT_LIST_IDS)}"
            )
        return True

    def validate_query(self, query: str) -> bool:
        """
        Validate GTI query syntax.

        Returns:
            True if valid, raises QueryValidationError if invalid
        """
        if not query:
            return True

        # Split query by 'and' operator
        parts = [p.strip() for p in query.lower().split(" and ")]

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Check for valid filter prefixes
            if part.startswith("gti_score:"):
                # Validate gti_score filter
                value_part = part[10:]  # Remove 'gti_score:'
                if not self._validate_numeric_filter(value_part):
                    raise QueryValidationError(f"Invalid gti_score filter: {part}")
            elif part.startswith("positives:"):
                # Validate positives filter
                value_part = part[10:]  # Remove 'positives:'
                if not self._validate_numeric_filter(value_part):
                    raise QueryValidationError(f"Invalid positives filter: {part}")
            elif part.startswith("has:"):
                # Validate has: filter
                value_part = part[4:]  # Remove 'has:'
                if value_part not in VALID_HAS_VALUES:
                    raise QueryValidationError(
                        f"Invalid has: filter value: {value_part}. "
                        f"Must be one of: {', '.join(VALID_HAS_VALUES)}"
                    )
            else:
                raise QueryValidationError(
                    f"Invalid query filter: {part}. "
                    "Must start with 'gti_score:', 'positives:', or 'has:'"
                )

        return True

    def _validate_numeric_filter(self, value: str) -> bool:
        """Validate numeric filter value (e.g., '60+', '30-', '75')."""
        if not value:
            return False

        # Remove trailing operator if present
        if value.endswith("+") or value.endswith("-"):
            value = value[:-1]

        try:
            num = int(value)
            return num >= 0
        except ValueError:
            return False

    def build_query_url(self, threat_list_id: str, cursor: str | None = None) -> str:
        """Build the API URL with query parameters."""
        endpoint = f"{self.BASE_URL}/threat_lists/{threat_list_id}/latest"

        params: dict[str, str | int] = {"limit": self.max_iocs}

        # Add IOC types filter
        if self.ioc_types:
            params["ioc_types"] = ",".join(self.ioc_types)

        # Add extra query params
        if self.extra_query_params:
            params["query"] = self.extra_query_params

        # Add pagination cursor
        if cursor:
            params["cursor"] = cursor

        return f"{endpoint}?{urlencode(params)}"

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=120),
        retry=retry_if_exception_type(QuotaExceededError),
        reraise=True,
    )
    def _make_request(self, url: str) -> dict[str, Any]:
        """Make HTTP request with retry logic."""
        response = self.session.get(url, timeout=30)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            raise QuotaExceededError("API rate limit exceeded")
        elif response.status_code == 401:
            raise InvalidAPIKeyError("Invalid or expired API key")
        elif response.status_code == 403:
            raise InvalidAPIKeyError("API key does not have access")
        elif response.status_code == 404:
            raise ThreatListNotFoundError(f"Threat list not found: {url}")
        elif response.status_code >= 500:
            raise VirusTotalAPIError(f"Server error: {response.status_code}")
        else:
            raise VirusTotalAPIError(
                f"API error: {response.status_code} - {response.text}"
            )

    def fetch_events(self, cursor: str | None = None) -> dict[str, Any]:
        """
        Fetch IoCs from VirusTotal Threat List API.

        Args:
            cursor: Pagination cursor from previous response

        Returns:
            API response containing IoCs and metadata
        """
        self.log(
            message=f"Fetching events from threat list: {self.threat_list_id}",
            level="info",
        )

        # Validate configuration
        self.validate_threat_list_id(self.threat_list_id)
        self.validate_query(self.extra_query_params)

        # Build URL and make request
        url = self.build_query_url(self.threat_list_id, cursor)
        response = self._make_request(url)

        data = response.get("data", [])
        self.log(message=f"Retrieved {len(data)} IoCs", level="info")

        return response

    def transform_ioc(self, ioc: dict[str, Any]) -> dict[str, Any]:
        """
        Transform VirusTotal IoC to internal format.

        Args:
            ioc: Raw IoC from VirusTotal API

        Returns:
            Transformed IoC with normalized fields
        """
        ioc_type = ioc.get("type", "unknown")
        ioc_id = ioc.get("id", "")
        attributes = ioc.get("attributes", {})

        # Determine the IOC value based on type
        if ioc_type == "file":
            value = attributes.get("sha256", ioc_id)
        elif ioc_type == "url":
            value = attributes.get("url", ioc_id)
        elif ioc_type == "ip_address":
            value = ioc_id
        elif ioc_type == "domain":
            value = ioc_id
        else:
            value = ioc_id

        # Create hash for deduplication
        ioc_hash = self._compute_ioc_hash(ioc_type, value)

        return {
            "ioc_hash": ioc_hash,
            "type": ioc_type,
            "value": value,
            "gti_score": attributes.get("gti_score"),
            "positives": attributes.get("positives"),
            "total_engines": attributes.get("total_engines"),
            "malware_families": attributes.get("malware_families", []),
            "campaigns": attributes.get("campaigns", []),
            "threat_actors": attributes.get("threat_actors", []),
            "raw": ioc,
        }

    def _compute_ioc_hash(self, ioc_type: str, value: str) -> str:
        """Generate deterministic hash for IoC deduplication."""
        normalized_value = value.lower().strip()
        hash_input = f"{ioc_type}:{normalized_value}"
        return hashlib.sha256(hash_input.encode()).hexdigest()

    def filter_new_events(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Filter out already processed events using LRU cache.

        Args:
            events: List of transformed IoCs

        Returns:
            List of new (not previously seen) IoCs
        """
        new_events = []
        for event in events:
            event_id = event.get("ioc_hash")
            if event_id and event_id not in self.processed_events:
                new_events.append(event)
                self.processed_events[event_id] = True

        self.log(
            message=f"Filtered to {len(new_events)} new events "
            f"(deduplicated {len(events) - len(new_events)})",
            level="info",
        )
        return new_events

    def push_to_sekoia(self, ioc_values: list[str]) -> None:
        """
        Push batch of IOCs to Sekoia IOC Collection.

        Args:
            ioc_values: List of IOC value strings
        """
        if not ioc_values:
            self.log(
                message="No IOC values to push",
                level="info",
            )
            return

        # Validate required parameters before attempting push
        if not self.sekoia_api_key:
            self.log(
                message="Cannot push IOCs: sekoia_api_key is not configured",
                level="error",
            )
            return

        if not self.ioc_collection_uuid:
            self.log(
                message="Cannot push IOCs: ioc_collection_uuid is not configured",
                level="error",
            )
            return

        # Batch into chunks of 1000
        batch_size = 1000
        total_batches = (len(ioc_values) + batch_size - 1) // batch_size

        self.log(
            message=f"Pushing {len(ioc_values)} IOCs in {total_batches} batch(es)",
            level="info",
        )

        for batch_num, i in enumerate(range(0, len(ioc_values), batch_size), 1):
            batch = ioc_values[i : i + batch_size]
            indicators_text = "\n".join(batch)

            # Prepare request
            url = (
                f"{self.ioc_collection_server}/v2/inthreat/ioc-collections/"
                f"{self.ioc_collection_uuid}/indicators/text"
            )

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.sekoia_api_key}",
            }

            payload = {"indicators": indicators_text, "format": "one_per_line"}

            # Send request with retry logic
            retry_count = 0
            max_retries = 3
            success = False

            while retry_count < max_retries and not success:
                try:
                    response = requests.post(
                        url, json=payload, headers=headers, timeout=30
                    )

                    if response.status_code == 200:
                        result = response.json()
                        self.log(
                            message=f"Batch {batch_num}/{total_batches} pushed successfully: "
                            f"{result.get('created', 0)} created, "
                            f"{result.get('updated', 0)} updated, "
                            f"{result.get('ignored', 0)} ignored",
                            level="info",
                        )
                        success = True
                        break
                    elif response.status_code == 429:
                        # Rate limit - exponential backoff
                        retry_after = response.headers.get("Retry-After", None)
                        if retry_after:
                            wait_time = int(retry_after)
                        else:
                            wait_time = 2**retry_count * 10

                        self.log(
                            message=f"Rate limited. Waiting {wait_time} seconds...",
                            level="info",
                        )
                        time.sleep(wait_time)
                        retry_count += 1
                    elif response.status_code in [401, 403]:
                        # Authentication/Authorization errors - fatal
                        self.log(
                            message=f"Authentication error: {response.status_code} - {response.text}",
                            level="error",
                        )
                        raise InvalidAPIKeyError(
                            f"Sekoia API authentication error: {response.status_code}"
                        )
                    elif response.status_code == 404:
                        # Not found - fatal
                        self.log(
                            message=f"IOC Collection not found: {response.status_code} - {response.text}",
                            level="error",
                        )
                        raise VirusTotalAPIError(
                            f"IOC Collection not found: {self.ioc_collection_uuid}"
                        )
                    elif 400 <= response.status_code < 500:
                        # Other client errors (non-retriable) - fatal
                        self.log(
                            message=f"Client error when pushing IOCs: {response.status_code} - {response.text}",
                            level="error",
                        )
                        raise VirusTotalAPIError(
                            f"Sekoia API client error: {response.status_code}"
                        )
                    else:
                        # Server errors (5xx) - temporary, retry
                        self.log(
                            message=f"Server error {response.status_code}: {response.text}",
                            level="error",
                        )
                        retry_count += 1
                        time.sleep(5)

                except requests.exceptions.Timeout:
                    self.log(
                        message="Request timeout",
                        level="error",
                    )
                    retry_count += 1
                    time.sleep(5)
                except requests.exceptions.RequestException as error:
                    self.log(
                        message=f"Request error: {error}",
                        level="error",
                    )
                    retry_count += 1
                    time.sleep(5)

            if not success:
                self.log(
                    message=f"Failed to push batch {batch_num}/{total_batches} after {max_retries} retries",
                    level="error",
                )

    def run(self) -> None:
        """Main trigger loop."""
        self.log(message="Starting GTI Threat List trigger", level="info")

        try:
            self.initialize_client()
        except Exception as error:
            self.log(message=f"Failed to initialize client: {error}", level="error")
            return

        cursor = None

        while self.running:
            try:
                # Fetch IoCs from VirusTotal
                response = self.fetch_events(cursor)
                raw_iocs = response.get("data", [])

                # Transform IoCs
                transformed = [self.transform_ioc(ioc) for ioc in raw_iocs]

                # Filter out duplicates
                new_iocs = self.filter_new_events(transformed)

                if new_iocs:
                    self.log(
                        message=f"Processing {len(new_iocs)} new IoCs",
                        level="info",
                    )
                    # Extract IOC values and push to Sekoia IOC Collection
                    ioc_values = [ioc["value"] for ioc in new_iocs]
                    self.push_to_sekoia(ioc_values)

                # Update cursor for pagination
                meta = response.get("meta", {})
                cursor = meta.get("continuation_cursor")

                # If no more pages, reset cursor and sleep
                if not cursor:
                    cursor = None
                    time.sleep(self.sleep_time)

            except KeyboardInterrupt:
                self.log(message="Trigger stopped by user", level="info")
                break

            except (InvalidAPIKeyError, ThreatListNotFoundError) as error:
                # Non-retryable errors - stop the trigger
                self.log(message=f"Fatal error: {error}", level="error")
                break

            except Exception as error:
                self.log(message=f"Error in loop: {error}", level="error")
                self.log(message=format_exc(), level="error")
                cursor = None  # Reset cursor on error
                time.sleep(60)

        self.log(message="GTI Threat List trigger stopped", level="info")
