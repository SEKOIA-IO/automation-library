import logging
import os
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
        logging.basicConfig(
            level=logging.getLevelName(os.environ.get("LOG_LEVEL", "INFO")),
            format=FORMAT,
        )
        self._logger = logging.getLogger(__name__)

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
        return self.configuration.get("ioc_collection_server")

    @property
    def ioc_collection_uuid(self):
        """Get IOC collection UUID."""
        return self.configuration.get("ioc_collection_uuid")

    @property
    def sekoia_api_key(self):
        """Get Sekoia API key."""
        return self.configuration.get("sekoia_api_key")

    def initialize_misp_client(self):
        """Initialize MISP client with configuration."""
        try:
            self.misp_client = PyMISP(
                url=self.module.configuration.get("misp_url"),
                key=self.module.configuration.get("misp_api_key"),
                ssl=True,
                debug=False,
            )
            self._logger.info("MISP client initialized successfully")
        except Exception as error:
            self._logger.error(f"Failed to initialize MISP client: {error}")
            raise

    def initialize_cache(self):
        """Initialize processed attributes cache with TTL."""
        try:
            # TTL = publish_timestamp in days * seconds per day
            cache_ttl = abs(int(self.publish_timestamp)) * 24 * 3600
            self.processed_attributes = TTLCache(maxsize=10000, ttl=cache_ttl)
            self._logger.info(f"Cache initialized with TTL={cache_ttl}s")
        except Exception as error:
            self._logger.error(f"Failed to initialize cache: {error}")
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
            self._logger.info(f"Fetching MISP attributes with to_ids=1, " f"publish_timestamp={publish_timestamp}d")

            attributes = self.misp_client.search(
                controller="attributes",
                to_ids=1,  # Only IDS-flagged attributes
                pythonify=True,  # Return Python objects
                publish_timestamp=f"{publish_timestamp}d",
            )

            self._logger.info(f"Retrieved {len(attributes)} IDS attributes from MISP")
            return attributes

        except PyMISPError as error:
            self._logger.error(f"MISP API error: {error}")
            raise
        except Exception as error:
            self._logger.error(f"Error fetching attributes from MISP: {error}")
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

        self._logger.info(f"Filtered to {len(filtered)} supported attributes " f"(from {len(attributes)} total)")
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
            self._logger.info("No IOC values to push")
            return

        # Batch into chunks of 1000
        batch_size = 1000
        total_batches = (len(ioc_values) + batch_size - 1) // batch_size

        self._logger.info(f"Pushing {len(ioc_values)} IOCs in {total_batches} batch(es)")

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
                        self._logger.info(
                            f"Batch {batch_num}/{total_batches} pushed successfully: "
                            f"{result.get('created', 0)} created, "
                            f"{result.get('updated', 0)} updated, "
                            f"{result.get('ignored', 0)} ignored"
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

                        self._logger.warning(f"Rate limited. Waiting {wait_time} seconds...")
                        time.sleep(wait_time)
                        retry_count += 1
                    elif response.status_code in [401, 403]:
                        # Authentication/Authorization errors - fatal
                        self._logger.error(f"Authentication error: {response.status_code} - " f"{response.text}")
                        raise Exception(f"Sekoia API authentication error: {response.status_code}")
                    elif response.status_code == 404:
                        # Not found - fatal
                        self._logger.error(f"IOC Collection not found: {response.status_code} - " f"{response.text}")
                        raise Exception(f"IOC Collection not found: {self.ioc_collection_uuid}")
                    else:
                        # Temporary error - retry
                        self._logger.error(f"Error {response.status_code}: {response.text}")
                        retry_count += 1
                        time.sleep(5)

                except requests.exceptions.Timeout:
                    self._logger.error("Request timeout")
                    retry_count += 1
                    time.sleep(5)
                except requests.exceptions.RequestException as error:
                    self._logger.error(f"Request error: {error}")
                    retry_count += 1
                    time.sleep(5)

            if not success:
                self._logger.error(f"Failed to push batch {batch_num}/{total_batches} " f"after {max_retries} retries")

    def run(self):
        """Main trigger execution loop."""
        self._logger.info("Starting MISP IDS Attributes to IOC Collection trigger")

        try:
            # Initialize components
            self.initialize_misp_client()
            self.initialize_cache()
        except Exception as error:
            self._logger.error(f"Failed to initialize trigger: {error}")
            self._logger.error(format_exc())
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
                    self._logger.info(f"Found {len(new_attributes)} new IOCs to process")

                    # Extract IOC values
                    ioc_values = [self.extract_ioc_value(attr) for attr in new_attributes]

                    # Push to Sekoia
                    self.push_to_sekoia(ioc_values)

                    # Mark as processed
                    for attr in new_attributes:
                        self.processed_attributes[attr.uuid] = True

                    self._logger.info(f"Successfully processed {len(new_attributes)} new IOCs")
                else:
                    self._logger.info("No new IOCs to process")

                # Sleep until next poll
                self._logger.info(f"Sleeping for {self.sleep_time} seconds")
                time.sleep(self.sleep_time)

            except KeyboardInterrupt:
                self._logger.info("Trigger stopped by user")
                break
            except Exception as error:
                self._logger.error(f"Error in trigger loop: {error}")
                self._logger.error(format_exc())
                # Wait 1 minute before retry on error
                time.sleep(60)

        self._logger.info("MISP IDS Attributes to IOC Collection trigger stopped")
