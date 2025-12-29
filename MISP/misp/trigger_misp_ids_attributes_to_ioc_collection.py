from cachetools import TTLCache
from sekoia_automation import Trigger

class MISPIDSAttributesToIOCCollectionTrigger(Trigger):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Cache processed attribute UUIDs for 7 days (configurable)
        self.processed_attributes = TTLCache(maxsize=10000, ttl=7*24*3600)

    def extract_ioc_value(attribute):
        """Extract IOC value from MISP attribute, handling composite types."""
        value = attribute.value
        attr_type = attribute.type

        # Handle composite types
        if '|' in value:
            if attr_type.startswith('filename|'):
                # For filename|hash, take the hash portion
                return value.split('|', 1)[1]
            elif attr_type in ['ip-dst|port', 'domain|ip']:
                # For ip|port or domain|ip, take the first portion
                return value.split('|', 1)[0]

        return value

    def push_to_sekoia(self, attributes):
        """Push a batch of IOCs to Sekoia IOC Collection."""
        # Extract and deduplicate IOC values
        ioc_values = []
        for attr in attributes:
            if attr.uuid not in self.processed_attributes:
                ioc_value = self.extract_ioc_value(attr)
                ioc_values.append(ioc_value)
                self.processed_attributes[attr.uuid] = True

        if not ioc_values:
            return

        # Batch into chunks of 1000
        for i in range(0, len(ioc_values), 1000):
            batch = ioc_values[i:i+1000]
            indicators_text = '\n'.join(batch)

            payload = {
                "indicators": indicators_text,
                "format": "one_per_line"
            }

            response = self.post_to_sekoia(payload)
            self.log(f"Pushed {len(batch)} IOCs to Sekoia", level="info")

    def run(self):
        # Load last checkpoint (timestamp of last successful run)
        last_timestamp = self.load_checkpoint() or self.get_initial_timestamp()

        while self.running:
            try:
                # Fetch new attributes
                attributes = self.fetch_attributes(since=last_timestamp)

                # Filter and process
                new_iocs = self.process_attributes(attributes)

                if new_iocs:
                    # Push to Sekoia
                    self.push_to_sekoia(new_iocs)

                    # Update checkpoint
                    last_timestamp = self.get_latest_timestamp(attributes)
                    self.save_checkpoint(last_timestamp)

                # Sleep until next poll
                time.sleep(self.sleep_time)

            except Exception as e:
                self.log(f"Error: {e}", level="error")
                time.sleep(60)  # Wait before retry

=======================

from sekoia_automation import Trigger
from pymisp import PyMISP, MISPAttribute
from cachetools import TTLCache
import requests
import time
from datetime import datetime

class MISPIDSAttributesToIOCCollectionTrigger(Trigger):
    """
    Trigger to retrieve IDS-flagged attributes from MISP and push them
    to a Sekoia.io IOC Collection.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.misp_client = None
        self.processed_attributes = None

    def run(self):
        """Main trigger loop."""
        # Implementation

    def fetch_attributes(self, publish_timestamp):
        """
        Fetch IDS-flagged attributes from MISP.

        Args:
            publish_timestamp: Time window (e.g., '1d', '7d')

        Returns:
            List of MISPAttribute objects
        """
        try:
            self.log(f"Fetching MISP attributes with to_ids=1, publish_timestamp={publish_timestamp}", level="info")

            attributes = self.misp_client.search(
                controller='attributes',
                to_ids=1,  # Only IDS-flagged attributes
                pythonify=True,  # Return Python objects
                publish_timestamp=f'{publish_timestamp}d'
            )

            self.log(f"Retrieved {len(attributes)} IDS attributes from MISP", level="info")
            return attributes

        except Exception as error:
            self.log(f"Error fetching attributes from MISP: {error}", level="error")
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
        supported_types = ['ip-dst', 'domain', 'url', 'sha256', 'md5', 'sha1']

        # Composite types (pending client validation)
        # Uncomment if approved:
        # supported_types.extend(['ip-dst|port', 'domain|ip', 'filename|sha256', 'filename|md5', 'filename|sha1'])

        filtered = [attr for attr in attributes if attr.type in supported_types]

        self.log(f"Filtered to {len(filtered)} supported attributes", level="info")
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

        # Handle composite types (if enabled)
        if '|' in value:
            if attr_type.startswith('filename|'):
                # For filename|hash, extract the hash portion (after |)
                return value.split('|', 1)[1]
            elif attr_type in ['ip-dst|port', 'domain|ip']:
                # For ip|port or domain|ip, extract the first portion (before |)
                return value.split('|', 1)[0]

        return value

    def push_to_sekoia(self, ioc_values):
        """
        Push batch of IOCs to Sekoia IOC Collection.

        Args:
            ioc_values: List of IOC value strings
        """
        if not ioc_values:
            return

        # Configuration
        ioc_collection_server = self.configuration.get('ioc_collection_server')
        ioc_collection_uuid = self.configuration.get('ioc_collection_uuid')
        sekoia_api_key = self.configuration.get('sekoia_api_key')

        # Batch into chunks of 1000
        batch_size = 1000
        for i in range(0, len(ioc_values), batch_size):
            batch = ioc_values[i:i+batch_size]
            indicators_text = '\n'.join(batch)

            # Prepare request
            url = f"{ioc_collection_server}/v2/inthreat/ioc-collections/{ioc_collection_uuid}/indicators/text"

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {sekoia_api_key}"
            }

            payload = {
                "indicators": indicators_text,
                "format": "one_per_line"
            }

            # Send request with retry logic
            retry_count = 0
            max_retries = 3

            while retry_count < max_retries:
                try:
                    response = requests.post(url, json=payload, headers=headers, timeout=30)

                    if response.status_code == 200:
                        result = response.json()
                        self.log(
                            f"Batch pushed successfully: {result.get('created', 0)} created, "
                            f"{result.get('updated', 0)} updated, {result.get('ignored', 0)} ignored",
                            level="info"
                        )
                        break
                    elif response.status_code == 429:
                        # Rate limit - exponential backoff
                        wait_time = 2 ** retry_count * 10
                        self.log(f"Rate limited. Waiting {wait_time} seconds...", level="warning")
                        time.sleep(wait_time)
                        retry_count += 1
                    elif response.status_code in [401, 403, 404]:
                        # Fatal errors - stop trigger
                        self.log(f"Fatal error: {response.status_code} - {response.text}", level="error")
                        raise Exception(f"Sekoia API error: {response.status_code}")
                    else:
                        # Temporary error - retry
                        self.log(f"Error: {response.status_code} - {response.text}", level="error")
                        retry_count += 1
                        time.sleep(5)

                except requests.exceptions.RequestException as error:
                    self.log(f"Request error: {error}", level="error")
                    retry_count += 1
                    time.sleep(5)

            if retry_count >= max_retries:
                self.log(f"Failed to push batch after {max_retries} retries", level="error")

    def run(self):
        """Main trigger execution loop."""
        self.log("Starting MISP IDS Attributes to IOC Collection trigger", level="info")

        # Initialize MISP client
        self.misp_client = PyMISP(
            url=self.module.configuration.get('misp_url'),
            key=self.module.configuration.get('misp_api_key'),
            ssl=True,
            debug=False
        )

        # Initialize processed attributes cache
        cache_ttl = abs(int(self.configuration.get('publish_timestamp', 1))) * 24 * 3600
        self.processed_attributes = TTLCache(maxsize=10000, ttl=cache_ttl)

        # Load configuration
        publish_timestamp = self.configuration.get('publish_timestamp', '1')
        sleep_time = int(self.configuration.get('sleep_time', 300))

        # Main loop
        while self.running:
            try:
                # Fetch IDS attributes from MISP
                attributes = self.fetch_attributes(publish_timestamp)

                # Filter by supported types
                supported_attributes = self.filter_supported_types(attributes)

                # Filter out already processed attributes
                new_attributes = [
                    attr for attr in supported_attributes
                    if attr.uuid not in self.processed_attributes
                ]

                if new_attributes:
                    # Extract IOC values
                    ioc_values = [self.extract_ioc_value(attr) for attr in new_attributes]

                    # Push to Sekoia
                    self.push_to_sekoia(ioc_values)

                    # Mark as processed
                    for attr in new_attributes:
                        self.processed_attributes[attr.uuid] = True

                    self.log(f"Processed {len(new_attributes)} new IOCs", level="info")
                else:
                    self.log("No new IOCs to process", level="info")

                # Sleep until next poll
                time.sleep(sleep_time)

            except Exception as error:
                self.log(f"Error in trigger loop: {error}", level="error")
                self.log_exception(error)
                time.sleep(60)  # Wait 1 minute before retry