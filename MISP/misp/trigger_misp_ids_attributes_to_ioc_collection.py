from __future__ import annotations

import re
import time
from traceback import format_exc
from typing import Any
from urllib.request import getproxies

import requests
from cachetools import TTLCache
from pymisp import MISPAttribute, PyMISP, PyMISPError
from sekoia_automation.trigger import Trigger


class MISPIDSAttributesToIOCCollectionTrigger(Trigger):
    """
    Trigger to retrieve IDS-flagged attributes from MISP and push them
    to a Sekoia.io IOC Collection.
    """

    misp_client: PyMISP | None
    processed_attributes: TTLCache[str, bool] | None
    http_session: requests.Session | None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.misp_client = None
        self.processed_attributes = None
        self.http_session = None

    def initialize_http_session(self) -> None:
        """Initialize the HTTP session used to push IOCs to Sekoia."""
        session = requests.Session()
        session.verify = self.verify_ssl
        session.trust_env = False
        self.http_session = session

    @property
    def sleep_time(self) -> int:
        """Get sleep time between polling cycles."""
        return int(self.configuration.get("sleep_time", 300))

    @property
    def lookback_days(self) -> str:
        """Get the number of days to look back when retrieving attributes."""
        return str(self.configuration.get("lookback_days", "1"))

    @property
    def ioc_collection_server(self) -> str:
        """Get IOC collection server URL."""
        return str(self.configuration.get("ioc_collection_server", "https://api.sekoia.io"))

    @property
    def ioc_collection_uuid(self) -> str:
        """Get IOC collection UUID."""
        return str(self.configuration.get("ioc_collection_uuid", ""))

    @property
    def sekoia_api_key(self) -> str:
        """Get Sekoia API key."""
        return str(self.module.configuration.get("sekoia_api_key", ""))

    @property
    def verify_ssl(self) -> bool:
        """Whether to verify TLS certificates for HTTP requests."""
        return bool(self.configuration.get("verify_ssl", True))

    @property
    def proxies(self) -> dict[str, str] | None:
        """Get proxy configuration for HTTP requests.

        Priority:
        1. Module configuration (http_proxy, https_proxy)
        2. Environment variables (HTTP_PROXY, HTTPS_PROXY, etc.)
        """
        proxies: dict[str, str] = {}
        http_proxy = self.module.configuration.get("http_proxy")
        https_proxy = self.module.configuration.get("https_proxy")
        if http_proxy:
            proxies["http"] = http_proxy
        if https_proxy:
            proxies["https"] = https_proxy

        # Fallback to environment variables if no explicit configuration
        if not proxies:
            proxies = getproxies()
            if "no" in proxies:
                proxies["no_proxy"] = proxies.pop("no").strip()

        return proxies if proxies else None

    def initialize_misp_client(self) -> None:
        """Initialize MISP client with configuration."""
        misp_url = self.module.configuration.get("misp_url")
        misp_api_key = self.module.configuration.get("misp_api_key")

        # Log configuration state (without exposing secrets)
        self.log(
            message=f"Initializing MISP client - URL: {misp_url}, "
            f"API key configured: {bool(misp_api_key)}, "
            f"API key length: {len(misp_api_key) if misp_api_key else 0}",
            level="info",
        )

        # Log proxy configuration
        current_proxies = self.proxies
        if current_proxies:
            # Mask credentials in proxy URLs for logging
            safe_proxies = {}
            for proto, url in current_proxies.items():
                if "@" in url:
                    # URL contains credentials, mask them
                    safe_proxies[proto] = url.split("@")[-1]
                else:
                    safe_proxies[proto] = url
            self.log(
                message=f"Proxy configuration: {safe_proxies}",
                level="info",
            )
        else:
            self.log(
                message="No proxy configured",
                level="info",
            )

        try:
            misp_kwargs: dict[str, Any] = {
                "url": misp_url,
                "key": misp_api_key,
                "ssl": self.verify_ssl,
                "debug": False,
            }
            if current_proxies:
                misp_kwargs["proxies"] = current_proxies

            self.log(
                message=f"Attempting PyMISP connection to {misp_url}...",
                level="info",
            )

            self.misp_client = PyMISP(**misp_kwargs)

            # Test connection by fetching MISP version
            self.log(
                message="PyMISP client instantiated, testing connection...",
                level="info",
            )
            try:
                version_info = self.misp_client.misp_instance_version
                self.log(
                    message=f"MISP connection successful - Instance version: {version_info}",
                    level="info",
                )
            except Exception as version_error:
                self.log(
                    message=f"Warning: Could not fetch MISP version (connection may still work): {version_error}",
                    level="warning",
                )

            self.log(
                message="MISP client initialized successfully",
                level="info",
            )
        except requests.exceptions.ProxyError as error:
            self.log(
                message=f"Proxy error during MISP client initialization: {error}",
                level="error",
            )
            raise
        except requests.exceptions.SSLError as error:
            self.log(
                message=f"SSL error connecting to MISP server: {error}",
                level="error",
            )
            raise
        except requests.exceptions.ConnectionError as error:
            self.log(
                message=f"Connection error to MISP server ({misp_url}): {error}",
                level="error",
            )
            raise
        except requests.exceptions.Timeout as error:
            self.log(
                message=f"Timeout connecting to MISP server ({misp_url}): {error}",
                level="error",
            )
            raise
        except PyMISPError as error:
            self.log(
                message=f"PyMISP error during initialization: {error}",
                level="error",
            )
            raise
        except Exception as error:
            self.log(
                message=f"Failed to initialize MISP client: {type(error).__name__}: {error}",
                level="error",
            )
            raise

    def initialize_cache(self) -> None:
        """Initialize processed attributes cache with TTL."""
        try:
            # TTL = lookback_days * seconds per day
            cache_ttl = abs(int(self.lookback_days)) * 24 * 3600
            self.processed_attributes = TTLCache(maxsize=100000, ttl=cache_ttl)
            self.log(
                message=f"Cache initialized with TTL={cache_ttl}s",
                level="info",
            )
        except Exception as error:
            self.log(
                message=f"Failed to initialize cache: {error}",
                level="error",
            )
            raise

    def fetch_attributes(self, lookback_days: str) -> list[MISPAttribute]:
        """
        Fetch IDS-flagged attributes from MISP.

        Args:
            lookback_days: Number of days to look back (e.g., '1', '7')

        Returns:
            List of MISPAttribute objects
        """
        try:
            self.log(
                message=f"Fetching MISP attributes with to_ids=1, published timestamp and attribute date from less than {lookback_days}d ago",
                level="info",
            )

            if self.misp_client is None:
                raise RuntimeError("MISP client not initialized")

            self.log(
                message="Sending search request to MISP API...",
                level="info",
            )

            start_time = time.time()
            result = self.misp_client.search(
                controller="attributes",
                to_ids=1,  # Only IDS-flagged attributes
                pythonify=True,  # Return Python objects
                publish_timestamp=f"{lookback_days}d",
                timestamp=f"{lookback_days}d",  # Filter on attribute modification date, not just event publication date
            )
            elapsed_time = time.time() - start_time

            # Result is list of MISPAttribute when controller="attributes" and pythonify=True
            attributes: list[Any] = list(result) if isinstance(result, list) else []

            self.log(
                message=f"MISP search completed in {elapsed_time:.2f}s - "
                f"Retrieved {len(attributes)} IDS attributes",
                level="info",
            )
            return attributes

        except requests.exceptions.ProxyError as error:
            self.log(
                message=f"Proxy error during MISP search: {error}",
                level="error",
            )
            raise
        except requests.exceptions.ConnectionError as error:
            self.log(
                message=f"Connection error during MISP search: {error}",
                level="error",
            )
            raise
        except requests.exceptions.Timeout as error:
            self.log(
                message=f"Timeout during MISP search: {error}",
                level="error",
            )
            raise
        except PyMISPError as error:
            self.log(
                message=f"MISP API error: {error}",
                level="error",
            )
            raise
        except Exception as error:
            self.log(
                message=f"Error fetching attributes from MISP: {type(error).__name__}: {error}",
                level="error",
            )
            raise

    def filter_supported_types(self, attributes: list[MISPAttribute]) -> list[MISPAttribute]:
        """
        Filter attributes to only include supported IOC types.

        Args:
            attributes: List of MISPAttribute objects

        Returns:
            List of filtered MISPAttribute objects
        """
        # Supported types (initial scope)
        supported_types = [
            "ip-dst",
            "domain",
            "url",
            "sha256",
            "md5",
            "sha1",
            # Composite types (can be enabled)
            "ip-dst|port",
            "domain|ip",
            "filename|sha256",
            "filename|md5",
            "filename|sha1",
        ]

        filtered = [attr for attr in attributes if attr.type in supported_types]

        self.log(
            message=f"Filtered to {len(filtered)} supported attributes (from {len(attributes)} total)",
            level="info",
        )
        return filtered

    # Validation patterns per IOC category
    _RE_IPV4 = re.compile(r"^((25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(25[0-5]|2[0-4]\d|[01]?\d\d?)$")
    _RE_IPV6 = re.compile(
        r"^("
        r"([0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}"  # full 8-group
        r"|([0-9a-fA-F]{1,4}:){1,7}:"  # trailing ::
        r"|:(:[0-9a-fA-F]{1,4}){1,7}"  # leading ::
        r"|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}"  # one :: in middle
        r"|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}"
        r"|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}"
        r"|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}"
        r"|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}"
        r"|[0-9a-fA-F]{1,4}:(:[0-9a-fA-F]{1,4}){1,6}"
        r"|::"  # all zeros
        r")$"
    )
    # Domain: labels separated by dots, no path/port/scheme, TLD alpha-only, not a pure IP.
    # Explicitly forbids '/', ':', '@', spaces and any other non-domain characters.
    _RE_DOMAIN = re.compile(
        r"^(?!.*\.\d+$)"  # TLD must not be all digits (rejects bare IPs like 1.2.3.4)
        r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}$"
        # Note: character class [a-zA-Z0-9\-] and literal '.' already exclude '/', ':', spaces, etc.
        # The anchors ^ and $ ensure no extra characters are allowed.
    )
    # URL: must start with http(s)://, no bare paths or IP:path combinations allowed.
    _RE_URL = re.compile(r"^https?://[a-zA-Z0-9\-._~:/?#\[\]@!$&'()*+,;=%]{3,}$")
    _RE_MD5 = re.compile(r"^[0-9a-fA-F]{32}$")
    _RE_SHA1 = re.compile(r"^[0-9a-fA-F]{40}$")
    _RE_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")

    # Map MISP types to the validator that applies after value extraction
    _VALIDATORS: dict[str, re.Pattern[str]] = {
        "ip-dst": _RE_IPV4,
        "ip-dst|port": _RE_IPV4,
        "domain": _RE_DOMAIN,
        "domain|ip": _RE_DOMAIN,
        "url": _RE_URL,
        "md5": _RE_MD5,
        "filename|md5": _RE_MD5,
        "sha1": _RE_SHA1,
        "filename|sha1": _RE_SHA1,
        "sha256": _RE_SHA256,
        "filename|sha256": _RE_SHA256,
    }

    def validate_ioc_value(self, value: str, attr_type: str) -> bool:
        """Validate an extracted IOC value against the expected pattern for its type."""
        pattern = self._VALIDATORS.get(attr_type)
        if pattern is None:
            return True
        if bool(pattern.match(value)):
            return True
        # For IP types, also accept valid IPv6 addresses
        if attr_type in ("ip-dst", "ip-dst|port"):
            return bool(self._RE_IPV6.match(value))
        return False

    def extract_ioc_value(self, attribute: MISPAttribute) -> str:
        """
        Extract IOC value from MISP attribute, handling composite types.

        For composite MISP types the value uses '|' as separator (e.g. '1.2.3.4|80',
        'evil.exe|<hash>', 'example.com|1.2.3.4').  The type, not the presence of '|'
        in the value, determines how to split.

        Args:
            attribute: MISPAttribute object

        Returns:
            String containing the extracted IOC value
        """
        value: str = str(attribute.value)
        attr_type: str = str(attribute.type)

        if attr_type.startswith("filename|"):
            # filename|<hash> — keep the hash part (after the first '|')
            if "|" in value:
                return value.split("|", 1)[1]
            # Malformed: no separator — return as-is so validation rejects it
            return value

        if attr_type in ("ip-dst|port", "domain|ip"):
            # Keep the first component (IP or domain) before the separator.
            # MISP standard is '|' but some instances use ':' for ip|port.
            if "|" in value:
                return value.split("|", 1)[0]
            if ":" in value and attr_type == "ip-dst|port":
                return value.split(":", 1)[0]
            return value

        return value

    def push_to_sekoia(self, ioc_values: list[str]) -> int:
        """
        Push batch of IOCs to Sekoia IOC Collection.

        The API endpoint is asynchronous (returns 202 + task_id), so the actual
        created/updated/ignored counts are not available synchronously.

        Args:
            ioc_values: List of IOC value strings

        Returns:
            Number of IOCs successfully submitted (accepted by the API)
        """
        if not ioc_values:
            self.log(
                message="No IOC values to push",
                level="info",
            )
            return 0

        # Validate required parameters before attempting push
        if not self.sekoia_api_key:
            self.log(
                message="Cannot push IOCs: sekoia_api_key is not configured",
                level="error",
            )
            return 0

        if not self.ioc_collection_uuid:
            self.log(
                message="Cannot push IOCs: ioc_collection_uuid is not configured",
                level="error",
            )
            return 0

        # Batch into chunks of 100
        batch_size = 100
        total_batches = (len(ioc_values) + batch_size - 1) // batch_size
        submitted = 0

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

            if self.http_session is None:
                raise RuntimeError("HTTP session not initialized")

            while retry_count < max_retries and not success:
                try:
                    response = self.http_session.post(
                        url,
                        json=payload,
                        headers=headers,
                        timeout=30,
                    )

                    if response.status_code in (200, 202):
                        result = response.json()
                        task_id = result.get("task_id", "unknown")
                        self.log(
                            message=f"Batch {batch_num}/{total_batches} accepted "
                            f"({len(batch)} IOCs, task_id={task_id}). "
                            "Final counts (created/updated/ignored) are reported "
                            "asynchronously via bulk-import-progress events in the websocket.",
                            level="info",
                        )
                        submitted += len(batch)
                        success = True
                        # Brief pause between batches to avoid overwhelming the API
                        if batch_num < total_batches:
                            time.sleep(5)
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
                        raise Exception(f"Sekoia API authentication error: {response.status_code}")
                    elif response.status_code == 404:
                        # Not found - fatal
                        self.log(
                            message=f"IOC Collection not found: {response.status_code} - {response.text}",
                            level="error",
                        )
                        raise Exception(f"IOC Collection not found: {self.ioc_collection_uuid}")
                    elif 400 <= response.status_code < 500:
                        # Other client errors (non-retriable) - fatal
                        self.log(
                            message=f"Client error when pushing IOCs: {response.status_code} - {response.text}",
                            level="error",
                        )
                        raise Exception(f"Sekoia API client error: {response.status_code}")
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

        return submitted

    def run(self) -> None:
        """Main trigger execution loop."""
        self.log(
            message="========== TRIGGER STARTUP ==========",
            level="info",
        )
        self.log(
            message="Starting MISP IDS Attributes to IOC Collection trigger",
            level="info",
        )

        # Log all configuration parameters for debugging
        self.log(
            message=f"Configuration summary: "
            f"sleep_time={self.sleep_time}s, "
            f"lookback_days={self.lookback_days}d, "
            f"ioc_collection_server={self.ioc_collection_server}, "
            f"ioc_collection_uuid={'configured' if self.ioc_collection_uuid else 'MISSING'}",
            level="info",
        )

        try:
            # Validate required configuration parameters
            self.log(
                message="Validating configuration parameters...",
                level="info",
            )

            missing_params = []
            if not self.sekoia_api_key:
                missing_params.append("sekoia_api_key")
            if not self.ioc_collection_uuid:
                missing_params.append("ioc_collection_uuid")
            if not self.module.configuration.get("misp_url"):
                missing_params.append("misp_url")
            if not self.module.configuration.get("misp_api_key"):
                missing_params.append("misp_api_key")

            if missing_params:
                self.log(
                    message=f"Missing required parameters: {', '.join(missing_params)}",
                    level="error",
                )
                self.log(
                    message="Trigger cannot start - configuration incomplete",
                    level="error",
                )
                return

            self.log(
                message="All required configuration parameters are present",
                level="info",
            )

            # Initialize components
            self.log(
                message="Initializing HTTP session...",
                level="info",
            )
            self.initialize_http_session()

            self.log(
                message="Initializing MISP client...",
                level="info",
            )
            self.initialize_misp_client()

            self.log(
                message="Initializing cache...",
                level="info",
            )
            self.initialize_cache()

            self.log(
                message="========== INITIALIZATION COMPLETE ==========",
                level="info",
            )
        except Exception as error:
            self.log(
                message=f"Failed to initialize trigger: {type(error).__name__}: {error}",
                level="error",
            )
            self.log(
                message=f"Full traceback:\n{format_exc()}",
                level="error",
            )
            self.log(
                message="========== INITIALIZATION FAILED ==========",
                level="error",
            )
            return

        # Main loop
        self.log(
            message="Entering main polling loop...",
            level="info",
        )
        while self.running:
            try:
                # Fetch IDS attributes from MISP
                attributes = self.fetch_attributes(self.lookback_days)

                # Filter by supported types
                supported_attributes = self.filter_supported_types(attributes)

                # Filter out already processed attributes (deduplication)
                if self.processed_attributes is None:
                    raise RuntimeError("Cache not initialized")
                new_attributes = [attr for attr in supported_attributes if attr.uuid not in self.processed_attributes]

                if new_attributes:
                    self.log(
                        message=f"Found {len(new_attributes)} new IOCs to process",
                        level="info",
                    )

                    # Extract and validate IOC values
                    ioc_values = []
                    invalid_iocs = []
                    for attr in new_attributes:
                        value = self.extract_ioc_value(attr)
                        if self.validate_ioc_value(value, str(attr.type)):
                            ioc_values.append(value)
                        else:
                            raw = str(attr.value)
                            detail = f"{attr.type}:{value}" if value == raw else f"{attr.type}:{value} (raw: {raw})"
                            invalid_iocs.append(detail)

                    if invalid_iocs:
                        self.log(
                            message=f"Skipping {len(invalid_iocs)} invalid IOC values: {', '.join(invalid_iocs)}",
                            level="warning",
                        )

                    # Push to Sekoia
                    submitted = self.push_to_sekoia(ioc_values)

                    # Mark as processed
                    for attr in new_attributes:
                        self.processed_attributes[attr.uuid] = True

                    self.log(
                        message=(
                            f"Cycle complete: {len(new_attributes)} attributes fetched, "
                            f"{submitted} IOCs submitted to API"
                            + (f", {len(invalid_iocs)} skipped (invalid format)" if invalid_iocs else "")
                        ),
                        level="info",
                    )

                    self.send_event(
                        event_name="MISP IOCs pushed",
                        event={
                            "iocs_submitted": submitted,
                            "iocs_skipped_invalid": len(invalid_iocs),
                            "attributes_processed": len(new_attributes),
                        },
                    )
                else:
                    self.log(
                        message="No new IOCs to process",
                        level="info",
                    )

                # Sleep until next poll
                self.log(
                    message=f"Sleeping for {self.sleep_time} seconds",
                    level="info",
                )
                time.sleep(self.sleep_time)

            except KeyboardInterrupt:
                self.log(
                    message="Trigger stopped by user",
                    level="info",
                )
                break
            except Exception as error:
                self.log(
                    message=f"Error in trigger loop: {error}",
                    level="error",
                )
                self.log(
                    message=format_exc(),
                    level="error",
                )
                # Wait 1 minute before retry on error
                time.sleep(60)

        self.log(
            message="MISP IDS Attributes to IOC Collection trigger stopped",
            level="info",
        )
