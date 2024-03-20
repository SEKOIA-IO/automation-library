"""
This script is for a local debug only
"""

import argparse
import logging
from pathlib import Path

from fastly.connector_fastly_waf import FastlyWAFConnector, FastlyWAFConnectorConfiguration

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
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
    parser.add_argument("--email", type=str, required=True)
    parser.add_argument("--token", type=str, required=True)
    parser.add_argument("--corp", type=str, required=True)
    parser.add_argument("--site", type=str, required=True)
    parser.add_argument("--intake_key", type=str, required=True)
    parser.add_argument("--test", action="store_true")

    args = parser.parse_args()

    class DumbConnectorConfiguration(FastlyWAFConnectorConfiguration):
        intake_key = args.intake_key
        intake_server: str = "https://intake.test.sekoia.io" if args.test else "https://intake.sekoia.io"

        email = args.email
        token = args.token
        corp = args.corp
        site = args.site

    connector_conf = DumbConnectorConfiguration()

    conn = FastlyWAFConnector(data_path=Path("."))
    conn.configuration = connector_conf

    # Replace logging methods to make them work locally
    conn.log = dumb_log
    conn.log_exception = dumb_log_exception

    conn.run()
