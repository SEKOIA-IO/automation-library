"""
This script is for a local debug only
"""

import argparse
import logging
from pathlib import Path

from netskope_modules.connector_pubsub_lite import PubSubLite, PubSubLiteConfig

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s", datefmt="%d-%b-%y %H:%M:%S"
)
logger = logging.getLogger(__name__)


def dumb_log(message: str, level: str = "info", **kwargs):
    log_level = logging.getLevelName(level.upper())
    logger.log(log_level, message)


def dumb_log_exception(exception: Exception, **kwargs):
    message = kwargs.get("message", "An exception occurred")
    logger.exception(message, exc_info=exception)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--subscription_path", type=str, required=True)
    parser.add_argument("--intake_key", type=str, required=True)
    parser.add_argument("--test", action="store_true")

    args = parser.parse_args()

    parts = args.subscription_path.split("/")
    location = parts[3].split("-")

    class DumbConnectorConfiguration(PubSubLiteConfig):
        credentials: dict = {"project_id": parts[1]}
        cloud_region = location[0] + "-" + location[1]
        zone_id = location[2] if len(location) > 2 else None
        subscription_id = parts[5]

        frequency: int = 60
        intake_key = args.intake_key

        # https://intake.test.sekoia.io or https://intake.sekoia.io
        intake_server: str = "https://intake.test.sekoia.io" if args.test else "https://intake.sekoia.io"

    connector_conf = DumbConnectorConfiguration()

    conn = PubSubLite(data_path=Path("."))
    conn.configuration = connector_conf

    # Replace logging methods to make them work locally
    conn.log = dumb_log
    conn.log_exception = dumb_log_exception

    conn.run()
