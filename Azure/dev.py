"""
This script is for a local debug only
"""

import argparse
import logging
from pathlib import Path

from connectors.azure_eventhub import AzureEventsHubConfiguration, AzureEventsHubTrigger

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s", datefmt="%d-%b-%y %H:%M:%S"
)
logger = logging.getLogger(__name__)


def dumb_log(message: str, level: str, **kwargs):
    log_level = logging.getLevelName(level.upper())
    logger.log(log_level, message)


def dumb_log_exception(exception: Exception, **kwargs):
    message = kwargs.get("message", "An exception occurred")
    logger.exception(message, exc_info=exception)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--hub_connection_string", type=str, required=True)
    parser.add_argument("--hub_name", type=str, required=True)
    parser.add_argument("--hub_consumer_group", type=str, required=False)
    parser.add_argument("--storage_connection_string", type=str, required=True)
    parser.add_argument("--storage_container_name", type=str, required=True)
    parser.add_argument("--intake_key", type=str, required=True)

    args = parser.parse_args()

    connector_conf = AzureEventsHubConfiguration(
        hub_connection_string=args.hub_connection_string,
        hub_name=args.hub_name,
        hub_consumer_group=args.hub_consumer_group,
        storage_connection_string=args.storage_connection_string,
        storage_container_name=args.storage_container_name,
        intake_key=args.intake_key,
    )

    conn = AzureEventsHubTrigger()
    conn.configuration = connector_conf

    # Replace logging methods to make them work locally
    conn.log = dumb_log
    conn.log_exception = dumb_log_exception

    conn.run()
