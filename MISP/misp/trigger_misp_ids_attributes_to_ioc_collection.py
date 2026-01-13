import time
from traceback import format_exc

import requests
from cachetools import TTLCache
from pymisp import PyMISP, PyMISPError
from sekoia_automation.trigger import Trigger


class MISPIDSAttributesToIOCCollectionTrigger(Trigger):
    """
    Trigger to retrieve IDS-flagged attributes from MISP and push them
    to a Sekoia.io IOC Collection.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        FORMAT = "%(asctime)s %(name)s %(levelname)s %(message)s"

        self.misp_client = None
        self.processed_attributes = None

    @property
    def sleep_time(self):
        """Get sleep time between polling cycles."""
        return int(self.configuration.get("sleep_time", 300))

    @property
    def publish_timestamp(self):
        """Get publish timestamp window in days."""
        return self.configuration.get("publish_timestamp", "1")

    @property
    def ioc_collection_server(self):
        """Get IOC collection server URL."""
        return self.configuration.get("ioc_collection_server", "https://api.sekoia.io")

    @property
    def ioc_collection_uuid(self):
        """Get IOC collection UUID."""
        return self.configuration.get("ioc_collection_uuid", "")

    @property
    def sekoia_api_key(self):
        """Get Sekoia API key."""
        return self.module.configuration.get("sekoia_api_key", "")

    def initialize_misp_client(self):
        """Initialize MISP client with configuration."""
        try:
            self.misp_client = PyMISP(
                url=self.module.configuration.get("misp_url"),
                key=self.module.configuration.get("misp_api_key"),
                ssl=False,
                debug=False,
            )
            self.log(
                message="MISP client initialized successfully",
                level="info",
            )
        except Exception as error:
            self.log(
                message=f"Failed to initialize MISP client: {error}",
                level="error",
            )
            raise

    def initialize_cache(self):
        """Initialize processed attributes cache with TTL."""
        try:
            # TTL = publish_timestamp in days * seconds per day
            cache_ttl = abs(int(self.publish_timestamp)) * 24 * 3600
            self.processed_attributes = TTLCache(maxsize=10000, ttl=cache_ttl)
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

    def fetch_attributes(self, publish_timestamp):
        """
        Fetch IDS-flagged attributes from MISP.

        Args:
            publish_timestamp: Time window (e.g., '1', '7' for days)

        Returns:
            List of MISPAttribute objects
        """
        try:
            self.log(
                message=f"Fetching MISP attributes with to_ids=1, publish_timestamp={publish_timestamp}d",
                level="info",
            )

            attributes = self.misp_client.search(
                controller="attributes",
                to_ids=1,  # Only IDS-flagged attributes
                pythonify=True,  # Return Python objects
                publish_timestamp=f"{publish_timestamp}d",
            )

            self.log(
                message=f"Retrieved {len(attributes)} IDS attributes from MISP",
                level="info",
            )
            return attributes

        except PyMISPError as error:
            self.log(
                message=f"MISP API error: {error}",
                level="error",
            )
            raise
        except Exception as error:
            self.log(
                message=f"Error fetching attributes from MISP: {error}",
                level="error",
            )
            raise

    def filter_supported_types(self, attributes):
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

    def extract_ioc_value(self, attribute):
        """
        Extract IOC value from MISP attribute, handling composite types.

        Args:
            attribute: MISPAttribute object

        Returns:
            String containing the IOC value
        """
        value = attribute.value
        attr_type = attribute.type

        # Handle composite types
        if "|" in value:
            if attr_type.startswith("filename|"):
                # For filename|hash, extract the hash portion (after |)
                return value.split("|", 1)[1]
            elif attr_type in ["ip-dst|port", "domain|ip"]:
                # For ip|port or domain|ip, extract the first portion (before |)
                return value.split("|", 1)[0]

        return value

    def push_to_sekoia(self, ioc_values):
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

            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.sekoia_api_key}"}

            payload = {"indicators": indicators_text, "format": "one_per_line"}

            # Send request with retry logic
            retry_count = 0
            max_retries = 3
            success = False

            while retry_count < max_retries and not success:
                try:
                    response = requests.post(url, json=payload, headers=headers, timeout=30)

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

    def run(self):
        """Main trigger execution loop."""
        self.log(
            message="Starting MISP IDS Attributes to IOC Collection trigger",
            level="info",
        )

        try:
            # Validate required configuration parameters
            if not self.sekoia_api_key:
                self.log(
                    message="Missing required parameter: sekoia_api_key",
                    level="error",
                )
                return

            if not self.ioc_collection_uuid:
                self.log(
                    message="Missing required parameter: ioc_collection_uuid",
                    level="error",
                )
                return

            if not self.module.configuration.get("misp_url"):
                self.log(
                    message="Missing required parameter: misp_url",
                    level="error",
                )
                return

            if not self.module.configuration.get("misp_api_key"):
                self.log(
                    message="Missing required parameter: misp_api_key",
                    level="error",
                )
                return

            # Initialize components
            self.initialize_misp_client()
            self.initialize_cache()
        except Exception as error:
            self.log(
                message=f"Failed to initialize trigger: {error}",
                level="error",
            )
            self.log(
                message=format_exc(),
                level="error",
            )
            return

        # Main loop
        while self.running:
            try:
                # Fetch IDS attributes from MISP
                attributes = self.fetch_attributes(self.publish_timestamp)

                # Filter by supported types
                supported_attributes = self.filter_supported_types(attributes)

                # Filter out already processed attributes (deduplication)
                new_attributes = [attr for attr in supported_attributes if attr.uuid not in self.processed_attributes]

                if new_attributes:
                    self.log(
                        message=f"Found {len(new_attributes)} new IOCs to process",
                        level="info",
                    )

                    # Extract IOC values
                    ioc_values = [self.extract_ioc_value(attr) for attr in new_attributes]

                    # Push to Sekoia
                    self.push_to_sekoia(ioc_values)

                    # Mark as processed
                    for attr in new_attributes:
                        self.processed_attributes[attr.uuid] = True

                    self.log(
                        message=f"Successfully processed {len(new_attributes)} new IOCs",
                        level="info",
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