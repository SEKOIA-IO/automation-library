"""
This script is for a local debug only
"""

import argparse
import logging
from pathlib import Path

from ubika_modules import UbikaModule
from ubika_modules.connector_ubika_cloud_protector_alerts import UbikaCloudProtectorAlertsConnector
from ubika_modules.connector_ubika_cloud_protector_base import UbikaCloudProtectorConnectorConfiguration
from ubika_modules.connector_ubika_cloud_protector_traffic import UbikaCloudProtectorTrafficConnector

logging.basicConfig(
    level=logging.DEBUG,
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
    parser.add_argument("--provider", type=str, required=True)
    parser.add_argument("--tenant", type=str, required=True)
    parser.add_argument("--token", type=str, required=True)
    parser.add_argument("--intake_key", type=str, required=True)

    args = parser.parse_args()

    class DumbConnectorConfiguration(UbikaCloudProtectorConnectorConfiguration):
        frequency: int = 60
        intake_key = args.intake_key

        # https://intake.test.sekoia.io or https://intake.sekoia.io
        intake_server: str = "https://intake.sekoia.io"

    connector_conf = DumbConnectorConfiguration(provider=args.provider, tenant=args.tenant, token=args.token)

    module = UbikaModule()

    # conn = UbikaCloudProtectorAlertsConnector(data_path=Path("."))
    conn = UbikaCloudProtectorTrafficConnector(data_path=Path("."))
    conn.configuration = connector_conf

    # Replace logging methods to make them work locally
    conn.log = dumb_log
    conn.log_exception = dumb_log_exception

    conn.run()
