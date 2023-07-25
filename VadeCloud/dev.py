"""
This script is for a local debug only
"""

import argparse
import logging
from pathlib import Path

from vadecloud_modules import VadeCloudModule
from vadecloud_modules.models import VadeCloudModuleConfiguration
from vadecloud_modules.trigger_vade_cloud_logs import VadeCloudConnectorConfiguration, VadeCloudLogsConnector

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
    parser.add_argument("--hostname", type=str, required=True)
    parser.add_argument("--login", type=str, required=True)
    parser.add_argument("--password", type=str, required=True)
    parser.add_argument("--intake_key", type=str, required=True)

    args = parser.parse_args()

    module_conf = VadeCloudModuleConfiguration(hostname=args.hostname, login=args.login, password=args.password)

    class DumbConnectorConfiguration(VadeCloudConnectorConfiguration):
        frequency: int = 60
        intake_key = args.intake_key

        # https://intake.test.sekoia.io or https://intake.sekoia.io
        intake_server: str = "https://intake.sekoia.io"

    connector_conf = DumbConnectorConfiguration()

    module = VadeCloudModule()
    module.configuration = module_conf

    conn = VadeCloudLogsConnector(module=module, data_path=Path("."))
    conn.configuration = connector_conf

    # Replace logging methods to make them work locally
    conn.log = dumb_log
    conn.log_exception = dumb_log_exception

    conn.run()
