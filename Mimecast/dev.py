"""
This script is for a local debug only
"""

import argparse
import logging
from pathlib import Path
from time import sleep

from mimecast_modules import MimecastModule, MimecastModuleConfiguration
from mimecast_modules.connector_mimecast_siem import MimecastSIEMConfiguration, MimecastSIEMConnector

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
    parser.add_argument("--client_id", type=str, required=True)
    parser.add_argument("--client_secret", type=str, required=True)
    parser.add_argument("--intake_key", type=str, required=True)
    parser.add_argument("--test", action="store_true")

    args = parser.parse_args()

    class DumbModuleConfiguration(MimecastModuleConfiguration):
        client_id = args.client_id
        client_secret = args.client_secret

    module = MimecastModule()
    module.configuration = DumbModuleConfiguration(client_id=args.client_id, client_secret=args.client_secret)

    class DumbConnectorConfiguration(MimecastSIEMConfiguration):
        frequency: int = 60
        chunk_size: int = 100
        intake_key = args.intake_key

        # https://intake.test.sekoia.io or https://intake.sekoia.io
        intake_server: str = "https://intake.test.sekoia.io" if args.test else "https://intake.sekoia.io"

    connector_conf = DumbConnectorConfiguration()
    conn = MimecastSIEMConnector(module=module, data_path=Path("."))
    conn.configuration = connector_conf

    # Replace logging methods to make them work locally
    conn.log = dumb_log
    conn.log_exception = dumb_log_exception

    conn.run()
