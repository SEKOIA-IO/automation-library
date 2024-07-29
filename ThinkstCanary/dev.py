"""
This script is for a local debug only
"""

import argparse
import logging
from pathlib import Path

from thinkst_canary_modules import ThinkstCanaryModule, ThinkstCanaryModuleConfiguration
from thinkst_canary_modules.connector_thinkst_canary_alerts import (
    ThinksCanaryAlertsConnectorConfiguration,
    ThinkstCanaryAlertsConnector,
)

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
    parser.add_argument("--base_url", type=str, required=True)
    parser.add_argument("--auth_token", type=str, required=True)
    parser.add_argument("--intake_key", type=str, required=True)
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--ack", action="store_true")

    args = parser.parse_args()

    class DumbModuleConfiguration(ThinkstCanaryModuleConfiguration):
        base_url: str = args.base_url
        auth_token = args.auth_token

    module = ThinkstCanaryModule()
    module.configuration = DumbModuleConfiguration(base_url=args.base_url, auth_token=args.auth_token)

    class DumbConnectorConfiguration(ThinksCanaryAlertsConnectorConfiguration):
        # frequency: int = 60
        intake_key = args.intake_key
        acknowledge = args.ack

        # https://intake.test.sekoia.io or https://intake.sekoia.io
        intake_server: str = "https://intake.test.sekoia.io" if args.test else "https://intake.sekoia.io"

    conn = ThinkstCanaryAlertsConnector(module=module, data_path=Path("."))
    conn.configuration = DumbConnectorConfiguration()

    # Replace logging methods to make them work locally
    conn.log = dumb_log
    conn.log_exception = dumb_log_exception

    conn.run()
